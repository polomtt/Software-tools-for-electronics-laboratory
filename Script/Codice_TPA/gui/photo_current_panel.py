# gui/photo_current_panel.py
"""
Photo Current Panel — Oscilloscope-integrated charge vs position scan.

For each motor step:
  1. Reads the oscilloscope waveform (single channel)
  2. Integrates V(t) over a user-defined time window → charge (V·s)
  3. Plots the point on a live Charge vs Position chart

Position axis:
  - µm  if the motion speed is calibrated in TestSpeed.xlsx
  - step number otherwise

Multiple cycles are overlaid as separate colored curves.
The live plot opens in a floating window when RUN is pressed.

Save policy: identical to ScanPanel (trigger rules, custom folders per rule).
"""

from __future__ import annotations

import numpy as np
from pathlib  import Path
from datetime import datetime
from typing   import List, Optional, Set

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QGroupBox, QLineEdit, QFileDialog, QCheckBox, QFrame,
    QDialog, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui  import QColor

import gui.style as S
from gui.widgets  import SectionTitle, HLine, make_button

from gui.scan_panel import (
    MotionEntry, TriggerRule,
    _load_calibration, _um_to_pulses,
    MotionRow, TriggerRow, MeasurementBlock, PathLog,
)

try:
    import pyqtgraph as pg
    PYQTGRAPH_OK = True
except ImportError:
    PYQTGRAPH_OK = False


#  Cycle colors 

CYCLE_COLORS = [
    "#FF6B35",   # orange
    "#00D2FF",   # cyan
    "#39FF14",   # green
    "#FFB800",   # amber
    "#FF4560",   # red
    "#BF5FFF",   # purple
    "#00FFD1",   # teal
    "#FF8FBF",   # pink
]

def _cycle_color(cycle: int) -> str:
    return CYCLE_COLORS[(cycle - 1) % len(CYCLE_COLORS)]


#  Calibration helpers 

def _pulses_to_um(speed: int, pulses: int, cal: dict) -> Optional[float]:
    """
    Inverse of _um_to_pulses: given pulses, find µm via interpolation.
    Returns None if speed is not calibrated.
    """
    if speed not in cal:
        return None
    data = cal[speed]
    try:
        return float(np.interp(pulses, data["pulses"], data["means"]))
    except Exception:
        return None


# Live plot window

class LivePlotWindow(QDialog):
    """
    Floating window showing Charge vs Position in real time.
    Each cycle is plotted as a separate colored curve.
    """

    def __init__(self, x_label: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Photo Current — Live Plot")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.WindowMinimizeButtonHint |
            Qt.WindowType.WindowMaximizeButtonHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        self.resize(800, 500)
        self.setStyleSheet(f"background:{S.BG_MAIN}; color:{S.TEXT};")

        self._x_label  = x_label
        self._curves   = {}    # {cycle: ScatterPlotItem}
        self._x_data   = {}    # {cycle: [x values]}
        self._y_data   = {}    # {cycle: [y values]}

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        if not PYQTGRAPH_OK:
            lbl = QLabel(
                "pyqtgraph not installed.\npip install pyqtgraph\n\n"
                "Data is still being acquired and saved."
            )
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(
                f"color:{S.TEXT_DIM}; font-size:14px; background:{S.BG_DEEP};"
                f"border:1px solid {S.BORDER}; border-radius:4px;"
            )
            layout.addWidget(lbl)
            return

        pg.setConfigOptions(antialias=True,
                            background=S.BG_DEEP,
                            foreground=S.TEXT_SUB)

        self._plot = pg.PlotWidget()
        self._plot.setLabel("bottom", self._x_label,
                            **{"color": S.TEXT_SUB, "font-size": "12px"})
        self._plot.setLabel("left", "Charge (V·s)",
                            **{"color": S.TEXT_SUB, "font-size": "12px"})
        self._plot.showGrid(x=True, y=True, alpha=0.15)
        self._plot.getPlotItem().getAxis("bottom").setPen(
            pg.mkPen(color=S.BORDER_LT))
        self._plot.getPlotItem().getAxis("left").setPen(
            pg.mkPen(color=S.BORDER_LT))
        self._legend = self._plot.addLegend(offset=(10, 10))
        self._legend.setLabelTextColor(S.TEXT_SUB)

        layout.addWidget(self._plot)

        # Clear button
        btn_clear = make_button("Clear Plot")
        btn_clear.setFixedHeight(30)
        btn_clear.clicked.connect(self.clear)
        layout.addWidget(btn_clear, alignment=Qt.AlignmentFlag.AlignRight)

    def add_point(self, cycle: int, x: float, charge: float):
        """Add a single data point for the given cycle."""
        if not PYQTGRAPH_OK:
            return

        # Initialize curve for this cycle if first point
        if cycle not in self._curves:
            color = _cycle_color(cycle)
            scatter = self._plot.plot(
                [], [],
                pen=pg.mkPen(color=color, width=1.5),
                symbol='o',
                symbolSize=7,
                symbolBrush=pg.mkBrush(color),
                symbolPen=pg.mkPen(None),
                name=f"Cycle {cycle}",
            )
            self._curves[cycle] = scatter
            self._x_data[cycle] = []
            self._y_data[cycle] = []

        self._x_data[cycle].append(x)
        self._y_data[cycle].append(charge)
        self._curves[cycle].setData(self._x_data[cycle], self._y_data[cycle])

    def clear(self):
        """Remove all curves."""
        if not PYQTGRAPH_OK:
            return
        for curve in self._curves.values():
            self._plot.removeItem(curve)
        self._curves.clear()
        self._x_data.clear()
        self._y_data.clear()

    def update_x_label(self, label: str):
        """Update horizontal axis label (called when calibration state changes)."""
        self._x_label = label
        if PYQTGRAPH_OK:
            self._plot.setLabel("bottom", label,
                                **{"color": S.TEXT_SUB, "font-size": "12px"})


# Worker

class PhotoCurrentWorker(QThread):
    """
    Executes the photo current scan off the UI thread.

    For each step:
      - moves the motor
      - reads the oscilloscope waveform
      - integrates V(t) over [t_start, t_end]
      - emits point_ready with position and charge
      - optionally saves the waveform to CSV
    """

    point_ready      = pyqtSignal(int, float, float)  # (cycle, position, charge)
    cycle_started    = pyqtSignal(int, int)            # (cycle, total)
    cycle_done       = pyqtSignal(int, int)
    step_info        = pyqtSignal(str)                 # log message
    measurement_done = pyqtSignal(int, int, int, str)  # (cycle, m_idx, step, label)
    finished         = pyqtSignal()
    error            = pyqtSignal(str)

    def __init__(
        self,
        motors        : dict,
        motions       : List[MotionEntry],
        n_cycles      : int,          # 0 = infinite
        pause_s       : float,
        scope,
        channel       : int,          # 1 or 2
        t_start_s     : float,
        t_end_s       : float,
        calibration   : dict,
        scope_enabled : bool,
        scope_cfg     : dict,
    ):
        super().__init__()
        self._motors      = motors
        self._motions     = motions
        self._n_cycles    = n_cycles
        self._pause_s     = pause_s
        self._scope       = scope
        self._channel     = channel
        self._t_start     = t_start_s
        self._t_end       = t_end_s
        self._cal         = calibration
        self._scope_en    = scope_enabled
        self._scope_cfg   = scope_cfg
        self._running     = False

    def stop(self):
        self._running = False

    @staticmethod
    def _ts() -> str:
        t = datetime.now()
        return t.strftime("%Y%m%d_%H%M%S_") + f"{t.microsecond // 1000:03d}"

    def _integrate(self, time_arr, volt_arr) -> float:
        """Integrate V(t) over [t_start, t_end] using the trapezoidal rule."""
        i0 = int(np.searchsorted(time_arr, self._t_start))
        i1 = int(np.searchsorted(time_arr, self._t_end))
        i0 = max(0, min(i0, len(time_arr) - 1))
        i1 = max(i0 + 1, min(i1, len(time_arr)))
        return float(np.trapz(volt_arr[i0:i1], time_arr[i0:i1]))

    def _um_per_step(self, motion: MotionEntry) -> Optional[float]:
        """Return µm per step if speed is calibrated, else None."""
        return _pulses_to_um(motion.speed, motion.pulses, self._cal)

    def _matching_rules(self, cfg, motion_idx, step, total):
        return [r for r in cfg.get("triggers", [])
                if r.matches(motion_idx, step, total)]

    def _save_scope(self, cycle, motion_idx, step, t, v, meta,
                    output_dir_override=None):
        import csv as _csv
        cfg     = self._scope_cfg
        out_dir = output_dir_override or cfg.get("output_dir", "data/photo/scope")
        prefix  = cfg.get("prefix", "")
        base = (f"{prefix}_c{cycle:03d}_m{motion_idx:02d}"
                f"_s{step:03d}_CH{self._channel}_{self._ts()}"
                if prefix else
                f"photo_c{cycle:03d}_m{motion_idx:02d}"
                f"_s{step:03d}_CH{self._channel}_{self._ts()}")
        p = Path(out_dir) / f"{base}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", newline="") as f:
            w = _csv.writer(f)
            w.writerow(["# cycle", cycle])
            for key, value in meta.items():
                w.writerow([f"# {key}", value])
            w.writerow([])
            w.writerow(["time_s", "voltage_V"])
            for ti, vi in zip(t, v):
                w.writerow([f"{ti:.9e}", f"{vi:.6e}"])
        self.measurement_done.emit(cycle, motion_idx, step, f"scope {p.name}")

    def run(self):
        self._running = True
        cycle = 0

        try:
            while self._running:
                cycle += 1
                if self._n_cycles > 0 and cycle > self._n_cycles:
                    break

                total = self._n_cycles
                self.cycle_started.emit(cycle, total)

                # Cumulative position within this cycle
                position = 0.0
                use_um   = None   # determined on first calibrated motion

                for m_idx, motion in enumerate(self._motions, start=1):
                    if not self._running:
                        break

                    motor = self._motors.get(motion.axis)
                    if motor is None:
                        self.error.emit(
                            f"Cycle {cycle}, Motion {m_idx}: "
                            f"axis '{motion.axis.upper()}' not connected.")
                        return

                    speed     = (1 if motion.forward else -1) * abs(motion.speed)
                    um_step   = self._um_per_step(motion)
                    is_um     = um_step is not None
                    if use_um is None:
                        use_um = is_um

                    for step in range(1, motion.steps + 1):
                        if not self._running:
                            break

                        # Move motor
                        motor.move(pulses=motion.pulses,
                                   speed=speed, wait=True)

                        # Update position
                        if is_um:
                            sign = 1 if motion.forward else -1
                            position += sign * um_step
                        else:
                            position += 1   # step count

                        # Read waveform + integrate
                        t_arr, v_arr, meta = self._scope.read_waveform_meta(
                            self._channel)
                        charge = self._integrate(t_arr, v_arr)

                        self.point_ready.emit(cycle, float(position), charge)
                        total_str = "∞" if total == 0 else str(total)
                        self.step_info.emit(
                            f"Cycle {cycle}/{total_str}  ·  "
                            f"Motion {m_idx}  ·  step {step}/{motion.steps}  ·  "
                            f"pos={'%.3f µm' % position if is_um else '%d steps' % int(position)}  ·  "
                            f"Q={charge:.4e} V·s"
                        )

                        # Save waveform if triggered
                        if self._scope_en:
                            for rule in self._matching_rules(
                                    self._scope_cfg, m_idx, step, motion.steps):
                                self._save_scope(
                                    cycle, m_idx, step, t_arr, v_arr, meta,
                                    output_dir_override=rule.output_dir
                                )

                        # Inter-step delay
                        if motion.delay_s > 0 and step < motion.steps:
                            elapsed = 0.0
                            while self._running and elapsed < motion.delay_s:
                                self.msleep(100)
                                elapsed += 0.1

                self.cycle_done.emit(cycle, total)

                # Pause between cycles
                if self._running and self._pause_s > 0:
                    if self._n_cycles == 0 or cycle < self._n_cycles:
                        elapsed = 0.0
                        while self._running and elapsed < self._pause_s:
                            self.msleep(100)
                            elapsed += 0.1

            if self._running:
                self.finished.emit()

        except Exception as exc:
            self.error.emit(str(exc))


# Integration interval widget

class IntegrationWidget(QGroupBox):
    """
    Compact widget for setting t_start and t_end with unit selector.
    """

    _UNITS = {"ns": 1e-9, "µs": 1e-6, "ms": 1e-3, "s": 1.0}

    def __init__(self, parent=None):
        super().__init__("Integration Window", parent)
        self._build_ui()

    def _build_ui(self):
        root = QGridLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 16, 10, 12)

        def _lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"color:{S.TEXT_SUB}; background:transparent;")
            return l

        root.addWidget(_lbl("t start"), 0, 0)
        self._t_start = QDoubleSpinBox()
        self._t_start.setRange(-1e9, 1e9)
        self._t_start.setValue(-50.0)
        self._t_start.setDecimals(3)
        self._t_start.setSingleStep(1.0)
        self._t_start.setFixedWidth(100)
        root.addWidget(self._t_start, 0, 1)

        root.addWidget(_lbl("t end"), 1, 0)
        self._t_end = QDoubleSpinBox()
        self._t_end.setRange(-1e9, 1e9)
        self._t_end.setValue(50.0)
        self._t_end.setDecimals(3)
        self._t_end.setSingleStep(1.0)
        self._t_end.setFixedWidth(100)
        root.addWidget(self._t_end, 1, 1)

        root.addWidget(_lbl("Unit"), 2, 0)
        self._unit_combo = QComboBox()
        self._unit_combo.addItems(list(self._UNITS.keys()))
        self._unit_combo.setCurrentText("ns")
        self._unit_combo.setFixedWidth(70)
        root.addWidget(self._unit_combo, 2, 1)

    @property
    def t_start_s(self) -> float:
        mult = self._UNITS[self._unit_combo.currentText()]
        return self._t_start.value() * mult

    @property
    def t_end_s(self) -> float:
        mult = self._UNITS[self._unit_combo.currentText()]
        return self._t_end.value() * mult


# Main panel

class PhotoCurrentPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, motors: dict, scope, parent=None):
        super().__init__(parent)
        self._motors      = motors
        self._scope       = scope
        self._worker      = None
        self._calibration = _load_calibration()
        self._plot_win    = None   # LivePlotWindow instance
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        #  Left: PathLog 
        axes = sorted(self._motors.keys()) or ["x", "y", "z"]
        self._pathlog = PathLog(available_axes=axes,
                                calibration=self._calibration)
        self._pathlog.setMinimumWidth(750)
        root.addWidget(self._pathlog, stretch=3)

        #  Right: scrollable settings + fixed bottom
        settings_widget = QWidget()
        settings_widget.setStyleSheet("background:transparent;")
        right = QVBoxLayout(settings_widget)
        right.setSpacing(12)
        right.setContentsMargins(0, 0, 8, 0)

        # Title
        title = QLabel("Photo Current")
        title.setStyleSheet(
            f"color:{S.TEXT}; font-size:20px; font-weight:700; background:transparent;"
        )
        subtitle = QLabel(
            "Integrate the oscilloscope signal at each step and plot "
            "Charge vs Position in real time."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:12px; background:transparent;"
        )
        right.addWidget(title)
        right.addWidget(subtitle)
        right.addWidget(HLine())

        #  Acquisition settings 
        acq_box = QGroupBox("Acquisition Settings")
        ag = QGridLayout(acq_box)
        ag.setSpacing(10)
        ag.setContentsMargins(10, 16, 10, 12)

        def _lbl(t):
            l = QLabel(t)
            l.setStyleSheet(f"color:{S.TEXT_SUB}; background:transparent;")
            return l

        # Channel
        ag.addWidget(_lbl("Channel"), 0, 0)
        self._ch_combo = QComboBox()
        self._ch_combo.addItems(["CH1", "CH2"])
        self._ch_combo.setFixedWidth(80)
        ag.addWidget(self._ch_combo, 0, 1)

        # Cycles
        ag.addWidget(_lbl("Cycles"), 1, 0)
        cycle_row = QHBoxLayout()
        self._cycles_spin = QSpinBox()
        self._cycles_spin.setRange(1, 999_999)
        self._cycles_spin.setValue(1)
        self._cycles_spin.setFixedWidth(80)
        self._inf_check = QCheckBox("∞")
        self._inf_check.setStyleSheet(f"""
            QCheckBox {{
                color:{S.TEXT}; font-size:13px;
                background:transparent; spacing:6px;
            }}
            QCheckBox::indicator {{
                width:13px; height:13px; border-radius:3px;
                border:2px solid {S.BORDER_LT}; background:{S.BG_WIDGET};
            }}
            QCheckBox::indicator:checked {{
                background:{S.ACCENT}; border-color:{S.ACCENT};
            }}
        """)
        self._inf_check.toggled.connect(
            lambda c: self._cycles_spin.setEnabled(not c))
        cycle_row.addWidget(self._cycles_spin)
        cycle_row.addWidget(self._inf_check)
        cycle_row.addStretch()
        ag.addLayout(cycle_row, 1, 1)

        # Pause
        ag.addWidget(_lbl("Pause between cycles (s)"), 2, 0)
        self._pause_spin = QDoubleSpinBox()
        self._pause_spin.setRange(0.0, 3600.0)
        self._pause_spin.setValue(0.0)
        self._pause_spin.setSingleStep(0.5)
        self._pause_spin.setDecimals(1)
        self._pause_spin.setFixedWidth(80)
        ag.addWidget(self._pause_spin, 2, 1)

        right.addWidget(acq_box)

        #  Integration window 
        self._integration = IntegrationWidget()
        right.addWidget(self._integration)

        #  Save settings 
        right.addWidget(SectionTitle("Save Waveforms  (optional)"))
        self._scope_block = MeasurementBlock("Oscilloscope Save")
        self._scope_block._dir_edit.setText("data/photo/scope")
        right.addWidget(self._scope_block)

        right.addStretch()

        # Wrap in scroll area
        scroll = QScrollArea()
        scroll.setWidget(settings_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;")

        #  Fixed bottom 
        self._log = QLabel("—")
        self._log.setWordWrap(True)
        self._log.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:11px; background:{S.BG_PANEL};"
            f"border:1px solid {S.BORDER}; border-radius:4px; padding:8px;"
        )
        self._log.setMinimumHeight(70)
        self._log.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._btn_run = make_button("▶  RUN", role="primary")
        self._btn_run.setStyleSheet(f"""
            QPushButton {{
                background-color:{S.ACCENT}; color:#07090E;
                border:none; border-radius:4px;
                font-size:14px; font-weight:700; padding:10px 22px;
            }}
            QPushButton:hover   {{ background-color:#FF855A; }}
            QPushButton:pressed {{ background-color:#D94E18; }}
            QPushButton:disabled {{ background-color:#3A2010; color:#6A4030; }}
        """)
        self._btn_run.setMinimumHeight(44)
        self._btn_run.clicked.connect(self._on_run)

        self._btn_stop = make_button("■  STOP", role="danger")
        self._btn_stop.setMinimumHeight(44)
        self._btn_stop.setEnabled(False)
        self._btn_stop.clicked.connect(self._on_stop)

        self._btn_plot = make_button("📈  Show Plot", role="default")
        self._btn_plot.setMinimumHeight(36)
        self._btn_plot.setToolTip("Re-open the live plot window if closed")
        self._btn_plot.clicked.connect(self._on_show_plot)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_stop)

        bottom = QWidget()
        bottom.setStyleSheet("background:transparent;")
        bl = QVBoxLayout(bottom)
        bl.setContentsMargins(0, 8, 8, 0)
        bl.setSpacing(8)
        bl.addWidget(HLine())
        bl.addWidget(SectionTitle("Log"))
        bl.addWidget(self._log)
        bl.addLayout(btn_row)
        bl.addWidget(self._btn_plot)

        # Assemble right column
        right_widget = QWidget()
        right_widget.setMinimumWidth(380)
        ro = QVBoxLayout(right_widget)
        ro.setContentsMargins(0, 0, 0, 0)
        ro.setSpacing(0)
        ro.addWidget(scroll, stretch=1)
        ro.addWidget(bottom)

        root.addWidget(right_widget, stretch=2)

    #  Helpers 

    def _log_msg(self, text: str):
        self._log.setText(text)
        self.status_message.emit(f"[Photo Current]  {text}")

    def _set_running(self, running: bool):
        self._btn_run.setEnabled(not running)
        self._btn_stop.setEnabled(running)

    def _x_label(self) -> str:
        """Return axis label depending on whether any motion is calibrated."""
        for m in self._pathlog.get_motions():
            if m.speed in self._calibration:
                return "Position (µm)"
        return "Step #"

    def _ensure_plot_window(self):
        if self._plot_win is None or not self._plot_win.isVisible():
            self._plot_win = LivePlotWindow(
                x_label=self._x_label(), parent=None
            )
        self._plot_win.show()
        self._plot_win.raise_()

    def update_calibration(self, cal: dict):
        self._calibration = cal
        self._pathlog.update_calibration(cal)

    #  Slots 

    def _on_show_plot(self):
        self._ensure_plot_window()

    def _on_run(self):
        motions = self._pathlog.get_motions()
        if not motions:
            self._log_msg("No motions in Path Log — add at least one.")
            return

        if self._integration.t_start_s >= self._integration.t_end_s:
            self._log_msg("t start must be less than t end.")
            return

        # Open / clear the plot window
        self._ensure_plot_window()
        self._plot_win.clear()
        self._plot_win.update_x_label(self._x_label())

        n_cycles = 0 if self._inf_check.isChecked() \
                   else self._cycles_spin.value()
        channel  = 1 if self._ch_combo.currentText() == "CH1" else 2

        scope_cfg = {
            "output_dir": self._scope_block.output_dir or "data/photo/scope",
            "prefix"    : self._scope_block.prefix,
            "triggers"  : self._scope_block.triggers,
        }

        self._worker = PhotoCurrentWorker(
            motors        = self._motors,
            motions       = motions,
            n_cycles      = n_cycles,
            pause_s       = self._pause_spin.value(),
            scope         = self._scope,
            channel       = channel,
            t_start_s     = self._integration.t_start_s,
            t_end_s       = self._integration.t_end_s,
            calibration   = self._calibration,
            scope_enabled = self._scope_block.enabled,
            scope_cfg     = scope_cfg,
        )
        self._worker.point_ready.connect(self._on_point_ready)
        self._worker.cycle_started.connect(self._on_cycle_started)
        self._worker.cycle_done.connect(self._on_cycle_done)
        self._worker.step_info.connect(self._log_msg)
        self._worker.measurement_done.connect(
            lambda c, m, s, lbl: self._log_msg(
                f"Cycle {c}  ·  motion {m}  ·  step {s}  →  saved {lbl}"
            )
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._set_running(True)
        total_str = "∞" if n_cycles == 0 else str(n_cycles)
        self._log_msg(
            f"Started  ·  {total_str} cycle(s)  ·  {len(motions)} motion(s)  ·  "
            f"CH{channel}  ·  "
            f"∫[{self._integration.t_start_s:.2e} → {self._integration.t_end_s:.2e}] s"
        )
        self._worker.start()

    def _on_stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(5000)
        self._set_running(False)
        self._log_msg("Stopped by user.")

    def _on_point_ready(self, cycle: int, position: float, charge: float):
        if self._plot_win and self._plot_win.isVisible():
            self._plot_win.add_point(cycle, position, charge)

    def _on_cycle_started(self, cycle: int, total: int):
        total_str = "∞" if total == 0 else str(total)
        self._log_msg(f"Cycle {cycle}/{total_str}  starting …")

    def _on_cycle_done(self, cycle: int, total: int):
        total_str = "∞" if total == 0 else str(total)
        self._log_msg(f"Cycle {cycle}/{total_str}  complete ✓")

    def _on_finished(self):
        self._set_running(False)
        self._log_msg("Scan complete ✓")

    def _on_error(self, message: str):
        self._set_running(False)
        self._log_msg(f"ERROR: {message}")
