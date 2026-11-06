# gui/scan_panel.py
"""
Scan Panel — Sequential motion scan with configurable measurement triggers.

Features:
  - PathLog: ordered list of motion entries, reorderable with ↑ ↓ buttons
  - Each motion row is two-line for readability
  - µm target field: if the selected speed has a calibration, auto-computes pulses
  - Measurement blocks (Scope / PM) with trigger rules, shown via dropdown
  - ScanWorker executes motions sequentially off the UI thread
"""

from __future__ import annotations

import csv
import numpy as np
from pathlib   import Path
from datetime  import datetime
from typing    import List, Optional

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QGroupBox, QLineEdit, QFileDialog, QCheckBox, QFrame,
    QStackedWidget, QSizePolicy,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import gui.style as S
from gui.widgets import SectionTitle, HLine, make_button


#Calibration helper

def _load_calibration() -> dict:
    """Calibration is now provided by HelpPanel via signal. Returns empty dict."""
    return {}


def _um_to_pulses(speed: int, um_target: float, cal: dict) -> Optional[int]:
    """
    Given a speed and a µm target, interpolate the calibration table
    and return the nearest integer pulse count.
    Returns None if the speed is not calibrated.
    """
    if speed not in cal:
        return None
    data = cal[speed]
    try:
        pulses = int(round(float(np.interp(
            um_target, data["means"], data["pulses"]
        ))))
        return max(1, pulses)
    except Exception:
        return None


# Data classes

class MotionEntry:
    def __init__(self, axis="x", pulses=1000, speed=5000,
                 steps=1, delay_s=0.0, forward=True):
        self.axis    = axis
        self.pulses  = pulses
        self.speed   = speed
        self.steps   = steps
        self.delay_s = delay_s
        self.forward = forward


class TriggerRule:
    def __init__(self, kind="every_step_any", motion_index=1, output_dir=None):
        self.kind         = kind
        self.motion_index = motion_index
        self.output_dir   = output_dir   # None = use global folder

    def matches(self, motion_idx_1based: int, step: int, total_steps: int) -> bool:
        if self.kind == "every_step_any":
            return True
        if self.kind == "every_step_of":
            return motion_idx_1based == self.motion_index
        if self.kind == "last_step_of":
            return (motion_idx_1based == self.motion_index
                    and step == total_steps)
        return False


# Execution worker

class ScanWorker(QThread):
    progress         = pyqtSignal(int, int, int)
    step_done        = pyqtSignal(int, int, int)
    measurement_done = pyqtSignal(int, int, str)
    finished         = pyqtSignal()
    error            = pyqtSignal(str)

    def __init__(self, motors, motions, scope, scope_enabled, scope_cfg,
                 pm, pm_enabled, pm_cfg):
        super().__init__()
        self._motors    = motors
        self._motions   = motions
        self._scope     = scope
        self._scope_en  = scope_enabled
        self._scope_cfg = scope_cfg
        self._pm        = pm
        self._pm_en     = pm_enabled
        self._pm_cfg    = pm_cfg
        self._running   = False

    def stop(self):
        self._running = False

    @staticmethod
    def _ts():
        t = datetime.now()
        return t.strftime("%Y%m%d_%H%M%S_") + f"{t.microsecond // 1000:03d}"

    def _save_scope(self, motion_idx, step, output_dir_override=None):
        cfg     = self._scope_cfg
        channel = cfg.get("channel", 1)
        out_dir = output_dir_override or cfg.get("output_dir", "data/scan/scope")
        prefix  = cfg.get("prefix", "")
        channels = [1, 2] if channel == "both" else [channel]
        for ch in channels:
            t, v, meta = self._scope.read_waveform_meta(ch)
            base = (f"{prefix}_m{motion_idx:02d}_s{step:03d}_CH{ch}_{self._ts()}"
                    if prefix else
                    f"scope_m{motion_idx:02d}_s{step:03d}_CH{ch}_{self._ts()}")
            p = Path(out_dir) / f"{base}.csv"
            p.parent.mkdir(parents=True, exist_ok=True)
            with open(p, "w", newline="") as f:
                import csv as _csv
                w = _csv.writer(f)
                # Metadata header
                for key, value in meta.items():
                    w.writerow([f"# {key}", value])
                w.writerow([])
                # Data
                w.writerow(["time_s", "voltage_V"])
                for ti, vi in zip(t, v):
                    w.writerow([f"{ti:.9e}", f"{vi:.6e}"])
            self.measurement_done.emit(motion_idx, step, f"scope {p.name}")

    def _save_pm(self, motion_idx, step, output_dir_override=None):
        cfg = self._pm_cfg
        out_dir = output_dir_override or cfg.get("output_dir", "data/scan/power")
        prefix  = cfg.get("prefix", "")
        wl  = cfg.get("wavelength", 1550.0)
        n   = cfg.get("n_samples", 10)
        avg = cfg.get("averaging", 5)
        self._pm.set_wavelength(wl)
        self._pm.set_auto_range(True)
        stats = self._pm.read_average(n_samples=n, averaging=avg)
        base = (f"{prefix}_m{motion_idx:02d}_s{step:03d}_{self._ts()}"
                if prefix else
                f"power_m{motion_idx:02d}_s{step:03d}_{self._ts()}")
        p = Path(out_dir) / f"{base}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["timestamp", datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            w.writerow(["wavelength_nm", f"{wl:.1f}"])
            w.writerow(["n_samples", n])
            w.writerow(["averaging", avg])
            w.writerow([])
            w.writerow(["mean_W","std_W","min_W","max_W","mean_mW"])
            w.writerow([f"{stats['mean_w']:.6E}", f"{stats['std_w']:.6E}",
                        f"{stats['min_w']:.6E}",  f"{stats['max_w']:.6E}",
                        f"{stats['mean_mw']:.6f}"])
        self.measurement_done.emit(motion_idx, step, f"power {p.name}")

    def _matching_rules(self, cfg, motion_idx, step, total):
        """Return list of rules that match this step (may be empty)."""
        return [r for r in cfg.get("triggers", [])
                if r.matches(motion_idx, step, total)]

    def run(self):
        self._running = True
        try:
            for m_idx, motion in enumerate(self._motions, start=1):
                if not self._running:
                    break
                motor = self._motors.get(motion.axis)
                if motor is None:
                    self.error.emit(
                        f"Motion {m_idx}: axis '{motion.axis.upper()}' not connected.")
                    return
                speed = (1 if motion.forward else -1) * abs(motion.speed)
                for step in range(1, motion.steps + 1):
                    if not self._running:
                        break
                    self.progress.emit(m_idx, step, motion.steps)
                    motor.move(pulses=motion.pulses, speed=speed, wait=True)
                    self.step_done.emit(m_idx, step, motion.steps)

                    # Oscilloscope — one save per matching rule (each with its folder)
                    if self._scope_en:
                        for rule in self._matching_rules(
                                self._scope_cfg, m_idx, step, motion.steps):
                            self._save_scope(m_idx, step,
                                             output_dir_override=rule.output_dir)

                    # Power meter — same
                    if self._pm_en:
                        for rule in self._matching_rules(
                                self._pm_cfg, m_idx, step, motion.steps):
                            self._save_pm(m_idx, step,
                                          output_dir_override=rule.output_dir)

                    if motion.delay_s > 0 and step < motion.steps:
                        elapsed = 0.0
                        while self._running and elapsed < motion.delay_s:
                            self.msleep(100)
                            elapsed += 0.1
            if self._running:
                self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


# Return home worker

class ReturnHomeWorker(QThread):
    """
    Executes the reverse of a snapshotted motion list to return to home.

    Algorithm
    ---------
    - Iterate motions in REVERSE order
    - Each motion: opposite direction, steps = max(1, steps // 2)
    - Same pulses and speed as original (backlash compensation via half-steps)
    """
    progress = pyqtSignal(int, int, int)   # (motion_idx, step, total_steps)
    finished = pyqtSignal()
    error    = pyqtSignal(str)

    def __init__(self, motors: dict, snapshot: list):
        super().__init__()
        self._motors   = motors
        self._snapshot = snapshot
        self._running  = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        try:
            # Build reversed motion list
            return_motions = []
            for m in reversed(self._snapshot):
                return_motions.append(MotionEntry(
                    axis    = m.axis,
                    pulses  = m.pulses,
                    speed   = m.speed,
                    steps   = max(1, m.steps // 2),  # half steps - backlash compensation
                    delay_s = m.delay_s,
                    forward = not m.forward,          # reverse direction
                ))

            total = len(return_motions)
            for m_idx, motion in enumerate(return_motions, start=1):
                if not self._running:
                    break

                motor = self._motors.get(motion.axis)
                if motor is None:
                    self.error.emit(
                        f"Return {m_idx}: axis '{motion.axis.upper()}' not connected.")
                    return

                speed = (1 if motion.forward else -1) * abs(motion.speed)
                for step in range(1, motion.steps + 1):
                    if not self._running:
                        break
                    self.progress.emit(m_idx, step, motion.steps)
                    motor.move(pulses=motion.pulses, speed=speed, wait=True)

                    if motion.delay_s > 0 and step < motion.steps:
                        elapsed = 0.0
                        while self._running and elapsed < motion.delay_s:
                            self.msleep(100)
                            elapsed += 0.1

            if self._running:
                self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))



# Motion row - two-line layout with optional µm target


class MotionRow(QFrame):
    remove_requested  = pyqtSignal(object)
    move_up_requested = pyqtSignal(object)
    move_dn_requested = pyqtSignal(object)

    def __init__(self, index: int, available_axes: list,
                 calibration: dict, parent=None):
        super().__init__(parent)
        self._calibration = calibration
        self._build_ui(index, available_axes)

    def _build_ui(self, index: int, axes: list):
        self.setStyleSheet(f"""
            QFrame {{
                background:{S.BG_PANEL};
                border:1px solid {S.BORDER};
                border-radius:6px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 10, 12, 10)
        root.setSpacing(6)

        #  Row 1: index / axis / direction / pulses / speed 
        row1 = QHBoxLayout()
        row1.setSpacing(10)

        # Badge
        self._badge = QLabel(f"{index}")
        self._badge.setFixedWidth(26)
        self._badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._badge.setStyleSheet(
            f"color:{S.AMBER}; font-size:14px; font-weight:800; background:transparent;"
        )
        row1.addWidget(self._badge)

        # Axis
        self._axis_combo = QComboBox()
        self._axis_combo.addItems([a.upper() for a in axes])
        self._axis_combo.setFixedWidth(70)
        row1.addWidget(self._axis_combo)

        # Direction
        self._dir_combo = QComboBox()
        self._dir_combo.addItems(["▶ Fwd", "◀ Bwd"])
        self._dir_combo.setFixedWidth(90)
        row1.addWidget(self._dir_combo)

        # Pulses
        row1.addWidget(self._lbl("Pulses"))
        self._pulses = QSpinBox()
        self._pulses.setRange(1, 999_999)
        self._pulses.setValue(1000)
        self._pulses.setFixedWidth(100)
        row1.addWidget(self._pulses)

        # Speed
        row1.addWidget(self._lbl("Speed"))
        self._speed = QSpinBox()
        self._speed.setRange(1, 500_000)
        self._speed.setValue(5000)
        self._speed.setFixedWidth(100)
        self._speed.valueChanged.connect(self._on_speed_changed)
        row1.addWidget(self._speed)

        row1.addStretch()

        # Reorder buttons
        btn_up = QPushButton("UP")
        btn_dn = QPushButton("DN")
        for btn in (btn_up, btn_dn):
            btn.setFixedSize(36, 28)
            btn.setStyleSheet(f"""
                QPushButton {{
                    background:{S.BG_WIDGET}; color:{S.TEXT_DIM};
                    border:1px solid {S.BORDER}; border-radius:4px;
                    font-size:10px; font-weight:800; letter-spacing:0.5px;
                }}
                QPushButton:hover {{ color:{S.ACCENT}; border-color:{S.ACCENT};
                                     background:{S.BG_HOVER}; }}
            """)
        btn_up.setToolTip("Move this motion up")
        btn_dn.setToolTip("Move this motion down")
        btn_up.clicked.connect(lambda: self.move_up_requested.emit(self))
        btn_dn.clicked.connect(lambda: self.move_dn_requested.emit(self))

        # Remove button
        btn_rm = QPushButton("DEL")
        btn_rm.setFixedSize(36, 28)
        btn_rm.setStyleSheet(f"""
            QPushButton {{
                background:{S.BG_WIDGET}; color:{S.TEXT_DIM};
                border:1px solid {S.BORDER}; border-radius:4px;
                font-size:10px; font-weight:800;
            }}
            QPushButton:hover {{ color:{S.RED}; border-color:{S.RED};
                                 background:{S.BG_HOVER}; }}
        """)
        btn_rm.setToolTip("Remove this motion")
        btn_rm.clicked.connect(lambda: self.remove_requested.emit(self))

        row1.addWidget(btn_up)
        row1.addWidget(btn_dn)
        row1.addWidget(btn_rm)
        root.addLayout(row1)

        #  Row 2: steps / delay / µm target 
        row2 = QHBoxLayout()
        row2.setSpacing(10)
        row2.addSpacing(36)   # indent to align with row1 content

        # Steps
        row2.addWidget(self._lbl("Steps"))
        self._steps = QSpinBox()
        self._steps.setRange(1, 10_000)
        self._steps.setValue(1)
        self._steps.setFixedWidth(100)
        row2.addWidget(self._steps)

        # Delay
        row2.addWidget(self._lbl("Delay (s)"))
        self._delay = QDoubleSpinBox()
        self._delay.setRange(0.0, 3600.0)
        self._delay.setValue(0.0)
        self._delay.setSingleStep(0.5)
        self._delay.setDecimals(1)
        self._delay.setFixedWidth(100)
        row2.addWidget(self._delay)

        # µm target (visible only when speed is calibrated)
        self._um_lbl = self._lbl("µm target")
        self._um_spin = QDoubleSpinBox()
        self._um_spin.setRange(0.001, 10_000.0)
        self._um_spin.setValue(1.0)
        self._um_spin.setSingleStep(0.1)
        self._um_spin.setDecimals(3)
        self._um_spin.setFixedWidth(110)
        self._um_spin.setToolTip(
            "Set the desired displacement in µm - pulses are calculated automatically"
        )
        self._um_spin.valueChanged.connect(self._on_um_changed)

        self._um_lbl.setVisible(False)
        self._um_spin.setVisible(False)

        row2.addWidget(self._um_lbl)
        row2.addWidget(self._um_spin)
        row2.addStretch()
        root.addLayout(row2)

        # Trigger initial check
        self._on_speed_changed(self._speed.value())

    @staticmethod
    def _lbl(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:12px; background:transparent;"
        )
        return l

    def _on_speed_changed(self, speed: int):
        """Show/hide µm target depending on whether speed is calibrated."""
        calibrated = speed in self._calibration
        self._um_lbl.setVisible(calibrated)
        self._um_spin.setVisible(calibrated)
        if calibrated:
            self._on_um_changed(self._um_spin.value())

    def _on_um_changed(self, um: float):
        """Auto-compute pulses from µm target using calibration table."""
        speed = self._speed.value()
        pulses = _um_to_pulses(speed, um, self._calibration)
        if pulses is not None:
            self._pulses.blockSignals(True)
            self._pulses.setValue(pulses)
            self._pulses.blockSignals(False)

    def set_index(self, idx: int):
        self._badge.setText(str(idx))

    def update_calibration(self, cal: dict):
        """Called when HelpPanel loads a new calibration file."""
        self._calibration = cal
        self._on_speed_changed(self._speed.value())

    def to_motion_entry(self) -> MotionEntry:
        return MotionEntry(
            axis    = self._axis_combo.currentText().lower(),
            pulses  = self._pulses.value(),
            speed   = self._speed.value(),
            steps   = self._steps.value(),
            delay_s = self._delay.value(),
            forward = self._dir_combo.currentIndex() == 0,
        )


# Trigger rule

class TriggerRow(QFrame):
    remove_requested = pyqtSignal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        self.setStyleSheet(f"""
            QFrame {{
                background:{S.BG_WIDGET};
                border:1px solid {S.BORDER};
                border-radius:4px;
            }}
        """)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 6, 8, 6)
        root.setSpacing(4)

        #  Row 1: kind / motion number / remove 
        top = QHBoxLayout()
        top.setSpacing(8)

        self._kind_combo = QComboBox()
        self._kind_combo.addItems([
            "After every step (any motion)",
            "After every step of motion #",
            "After last step of motion #",
        ])
        self._kind_combo.setMinimumWidth(260)
        self._kind_combo.currentIndexChanged.connect(self._on_kind_changed)
        top.addWidget(self._kind_combo)

        self._motion_spin = QSpinBox()
        self._motion_spin.setRange(1, 99)
        self._motion_spin.setValue(1)
        self._motion_spin.setFixedWidth(80)
        self._motion_spin.setVisible(False)
        top.addWidget(self._motion_spin)

        # Custom folder checkbox
        self._custom_check = QCheckBox("Custom folder")
        self._custom_check.setStyleSheet(f"""
            QCheckBox {{
                color:{S.TEXT_SUB}; font-size:12px;
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
        self._custom_check.toggled.connect(self._on_custom_toggled)
        top.addWidget(self._custom_check)

        top.addStretch()

        btn_rm = QPushButton("×")
        btn_rm.setFixedSize(26, 26)
        btn_rm.setStyleSheet(f"""
            QPushButton {{
                background:transparent; color:{S.TEXT_DIM};
                border:1px solid {S.BORDER}; border-radius:4px;
                font-size:15px; font-weight:700;
            }}
            QPushButton:hover {{ color:{S.RED}; border-color:{S.RED}; }}
        """)
        btn_rm.clicked.connect(lambda: self.remove_requested.emit(self))
        top.addWidget(btn_rm)
        root.addLayout(top)

        #  Row 2: custom folder (hidden by default) 
        self._folder_widget = QWidget()
        self._folder_widget.setStyleSheet("background:transparent;")
        folder_row = QHBoxLayout(self._folder_widget)
        folder_row.setContentsMargins(0, 0, 0, 0)
        folder_row.setSpacing(6)

        lbl = QLabel("Folder:")
        lbl.setStyleSheet(f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;")
        folder_row.addWidget(lbl)

        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Custom output folder for this rule …")
        folder_row.addWidget(self._dir_edit, stretch=1)

        btn_browse = QPushButton("Browse")
        btn_browse.setFixedHeight(26)
        btn_browse.setStyleSheet(f"""
            QPushButton {{
                background:{S.BG_WIDGET}; color:{S.TEXT_SUB};
                border:1px solid {S.BORDER}; border-radius:4px;
                font-size:11px; padding:2px 8px;
            }}
            QPushButton:hover {{ border-color:{S.ACCENT}; color:{S.TEXT}; }}
        """)
        btn_browse.clicked.connect(self._on_browse)
        folder_row.addWidget(btn_browse)

        self._folder_widget.setVisible(False)
        root.addWidget(self._folder_widget)

    def _on_kind_changed(self, idx: int):
        self._motion_spin.setVisible(idx > 0)

    def _on_custom_toggled(self, checked: bool):
        self._folder_widget.setVisible(checked)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select folder for this trigger", self._dir_edit.text()
        )
        if folder:
            self._dir_edit.setText(folder)

    def to_trigger_rule(self) -> TriggerRule:
        kinds = ["every_step_any", "every_step_of", "last_step_of"]
        custom_dir = None
        if self._custom_check.isChecked():
            d = self._dir_edit.text().strip()
            if d:
                custom_dir = d
        return TriggerRule(
            kind         = kinds[self._kind_combo.currentIndex()],
            motion_index = self._motion_spin.value(),
            output_dir   = custom_dir,
        )


# Measurement block

class MeasurementBlock(QGroupBox):
    def __init__(self, title: str, extra_widgets: list = None, parent=None):
        super().__init__(title, parent)
        self._trigger_rows: list[TriggerRow] = []
        self._build_ui(extra_widgets or [])

    def _build_ui(self, extra_widgets: list):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 16, 10, 12)

        self._enable_check = QCheckBox("Enable")
        self._enable_check.setStyleSheet(f"""
            QCheckBox {{
                color:{S.TEXT}; font-size:13px;
                background:transparent; spacing:8px;
            }}
            QCheckBox::indicator {{
                width:14px; height:14px; border-radius:3px;
                border:2px solid {S.BORDER_LT}; background:{S.BG_WIDGET};
            }}
            QCheckBox::indicator:checked {{
                background:{S.ACCENT}; border-color:{S.ACCENT};
            }}
        """)
        self._enable_check.toggled.connect(self._on_enable_toggled)
        root.addWidget(self._enable_check)

        self._settings = QWidget()
        self._settings.setStyleSheet("background:transparent;")
        sl = QVBoxLayout(self._settings)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.setSpacing(8)

        folder_row = QHBoxLayout()
        self._dir_edit = QLineEdit()
        self._dir_edit.setPlaceholderText("Output folder")
        btn_browse = make_button("Browse …")
        btn_browse.setFixedHeight(30)
        btn_browse.clicked.connect(self._on_browse)
        folder_row.addWidget(self._dir_edit)
        folder_row.addWidget(btn_browse)
        sl.addLayout(folder_row)

        lbl = QLabel("Filename prefix (optional):")
        lbl.setStyleSheet("background:transparent;")
        sl.addWidget(lbl)
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText("e.g.  scan_001")
        sl.addWidget(self._prefix_edit)

        for w in extra_widgets:
            sl.addWidget(w)

        sl.addWidget(HLine())
        sl.addWidget(SectionTitle("Trigger Rules"))

        self._trigger_container = QWidget()
        self._trigger_container.setStyleSheet("background:transparent;")
        self._trigger_layout = QVBoxLayout(self._trigger_container)
        self._trigger_layout.setContentsMargins(0, 0, 0, 0)
        self._trigger_layout.setSpacing(4)
        sl.addWidget(self._trigger_container)

        btn_add = make_button("+ Add Trigger")
        btn_add.setFixedHeight(30)
        btn_add.clicked.connect(self._add_trigger)
        sl.addWidget(btn_add)

        root.addWidget(self._settings)
        self._settings.setEnabled(False)
        self._settings.setVisible(False)

    def _on_enable_toggled(self, checked: bool):
        self._settings.setEnabled(checked)
        self._settings.setVisible(checked)

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select output folder", self._dir_edit.text())
        if folder:
            self._dir_edit.setText(folder)

    def _add_trigger(self):
        row = TriggerRow()
        row.remove_requested.connect(self._remove_trigger)
        self._trigger_rows.append(row)
        self._trigger_layout.addWidget(row)

    def _remove_trigger(self, row):
        if row in self._trigger_rows:
            self._trigger_rows.remove(row)
            self._trigger_layout.removeWidget(row)
            row.deleteLater()

    @property
    def enabled(self) -> bool:
        return self._enable_check.isChecked()

    @property
    def output_dir(self) -> str:
        return self._dir_edit.text().strip()

    @property
    def prefix(self) -> str:
        return self._prefix_edit.text().strip()

    @property
    def triggers(self) -> list:
        return [r.to_trigger_rule() for r in self._trigger_rows]

# Path log

class PathLog(QWidget):
    def __init__(self, available_axes: list, calibration: dict, parent=None):
        super().__init__(parent)
        self._axes        = available_axes
        self._calibration = calibration
        self._motion_rows: list[MotionRow] = []
        self._build_ui()

    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(8)

        title = QLabel("Path Log")
        title.setStyleSheet(
            f"color:{S.TEXT}; font-size:18px; font-weight:700; background:transparent;"
        )
        outer.addWidget(title)
        outer.addWidget(HLine())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background:transparent;")

        self._list_widget = QWidget()
        self._list_widget.setStyleSheet("background:transparent;")
        self._list_layout = QVBoxLayout(self._list_widget)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()

        scroll.setWidget(self._list_widget)
        outer.addWidget(scroll, stretch=1)

        btn_add = make_button("＋  Add Motion")
        btn_add.setMinimumHeight(38)
        btn_add.clicked.connect(self._add_motion)
        outer.addWidget(btn_add)

    def _add_motion(self):
        idx = len(self._motion_rows) + 1
        row = MotionRow(idx, self._axes, self._calibration)
        row.remove_requested.connect(self._remove_motion)
        row.move_up_requested.connect(self._move_up)
        row.move_dn_requested.connect(self._move_dn)
        self._motion_rows.append(row)
        self._list_layout.insertWidget(self._list_layout.count() - 1, row)

    def _remove_motion(self, row: MotionRow):
        if row in self._motion_rows:
            self._motion_rows.remove(row)
            self._list_layout.removeWidget(row)
            row.deleteLater()
            self._renumber()

    def _move_up(self, row: MotionRow):
        idx = self._motion_rows.index(row)
        if idx == 0:
            return
        self._swap(idx, idx - 1)

    def _move_dn(self, row: MotionRow):
        idx = self._motion_rows.index(row)
        if idx == len(self._motion_rows) - 1:
            return
        self._swap(idx, idx + 1)

    def _swap(self, i: int, j: int):
        rows = self._motion_rows
        rows[i], rows[j] = rows[j], rows[i]

        # Remove all from layout and re-insert in new order
        for r in rows:
            self._list_layout.removeWidget(r)
        for k, r in enumerate(rows):
            self._list_layout.insertWidget(k, r)

        self._renumber()

    def _renumber(self):
        for i, r in enumerate(self._motion_rows, start=1):
            r.set_index(i)

    def get_motions(self) -> list:
        return [r.to_motion_entry() for r in self._motion_rows]

    def update_calibration(self, cal: dict):
        """Refresh calibration in all existing motion rows."""
        self._calibration = cal
        for row in self._motion_rows:
            row.update_calibration(cal)


# Main Scan Panel

class ScanPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, motors: dict, scope, pm, parent=None):
        super().__init__(parent)
        self._motors      = motors
        self._scope       = scope
        self._pm          = pm
        self._worker      = None
        self._calibration = _load_calibration()
        self._home_snapshot: list = []   # snapshotted motions for Return Home
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

        #  Right: measurements + run 
        right = QVBoxLayout()
        right.setSpacing(12)

        right.addWidget(SectionTitle("Measurements"))

        # Dropdown
        instr_row = QHBoxLayout()
        lbl_instr = QLabel("Instrument:")
        lbl_instr.setStyleSheet("background:transparent;")
        instr_row.addWidget(lbl_instr)
        self._instr_combo = QComboBox()
        self._instr_combo.addItems(["Oscilloscope", "Power Meter"])
        self._instr_combo.setFixedWidth(170)
        self._instr_combo.setStyleSheet(f"""
            QComboBox {{
                background:{S.BG_WIDGET}; color:{S.ACCENT};
                border:1px solid {S.BORDER}; border-radius:4px;
                padding:6px 10px; font-size:13px; font-weight:600;
            }}
            QComboBox:focus {{ border-color:{S.ACCENT}; }}
            QComboBox::drop-down {{
                border:none; background:{S.BG_HOVER};
                width:24px; border-radius:0 4px 4px 0;
            }}
            QComboBox QAbstractItemView {{
                background:{S.BG_PANEL}; color:{S.TEXT};
                border:1px solid {S.BORDER_LT};
                selection-background-color:{S.BG_HOVER}; padding:4px;
            }}
        """)
        instr_row.addWidget(self._instr_combo)
        instr_row.addStretch()
        right.addLayout(instr_row)

        # Stacked pages
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._instr_combo.currentIndexChanged.connect(self._stack.setCurrentIndex)

        # Page 0 - Oscilloscope
        ch_widget = QWidget()
        ch_widget.setStyleSheet("background:transparent;")
        ch_l = QHBoxLayout(ch_widget)
        ch_l.setContentsMargins(0, 0, 0, 0)
        lbl_ch = QLabel("Channel:")
        lbl_ch.setStyleSheet("background:transparent;")
        ch_l.addWidget(lbl_ch)
        self._scope_ch_combo = QComboBox()
        self._scope_ch_combo.addItems(["CH1", "CH2", "Both"])
        self._scope_ch_combo.setFixedWidth(90)
        ch_l.addWidget(self._scope_ch_combo)
        ch_l.addStretch()
        self._scope_block = MeasurementBlock("Oscilloscope",
                                             extra_widgets=[ch_widget])
        self._scope_block._dir_edit.setText("data/scan/scope")
        self._stack.addWidget(self._scope_block)

        # Page 1 - Power Meter
        pm_extra = QWidget()
        pm_extra.setStyleSheet("background:transparent;")
        pg = QGridLayout(pm_extra)
        pg.setContentsMargins(0, 0, 0, 0)
        pg.setSpacing(6)
        for row_i, (lbl_txt, attr, rng, val, dec) in enumerate([
            ("Wavelength (nm)", "_pm_wl",      (200, 3500), 1550, 1),
            ("Samples",         "_pm_samples", (1, 1000),   10,   0),
            ("Averaging",       "_pm_avg",     (1, 300),    5,    0),
        ]):
            l = QLabel(lbl_txt); l.setStyleSheet("background:transparent;")
            pg.addWidget(l, row_i, 0)
            if dec > 0:
                w = QDoubleSpinBox()
                w.setDecimals(dec); w.setSingleStep(10)
            else:
                w = QSpinBox()
            w.setRange(*rng); w.setValue(val)
            setattr(self, attr, w)
            pg.addWidget(w, row_i, 1)

        self._pm_block = MeasurementBlock("Power Meter",
                                          extra_widgets=[pm_extra])
        self._pm_block._dir_edit.setText("data/scan/power")
        self._stack.addWidget(self._pm_block)

        # Scroll wrapper
        stack_scroll = QScrollArea()
        stack_scroll.setWidget(self._stack)
        stack_scroll.setWidgetResizable(True)
        stack_scroll.setFrameShape(QFrame.Shape.NoFrame)
        stack_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        stack_scroll.setStyleSheet("background:transparent;")
        right.addWidget(stack_scroll, stretch=1)

        right.addWidget(HLine())

        # Relative homing
        right.addWidget(SectionTitle("Relative Homing"))

        self._home_info = QLabel("No home set.")
        self._home_info.setWordWrap(True)
        self._home_info.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        right.addWidget(self._home_info)

        home_row = QHBoxLayout()
        self._btn_set_home = make_button("📍  Set Home", role="default")
        self._btn_set_home.setMinimumHeight(38)
        self._btn_set_home.setToolTip(
            "Snapshot the current PathLog as the home reference"
        )
        self._btn_set_home.clicked.connect(self._on_set_home)

        self._btn_return_home = make_button("⟵  Return Home", role="default")
        self._btn_return_home.setMinimumHeight(38)
        self._btn_return_home.setEnabled(False)
        self._btn_return_home.setToolTip(
            "Return to home: reverse motions, opposite direction, half steps"
        )
        self._btn_return_home.setStyleSheet(f"""
            QPushButton {{
                background:{S.BG_WIDGET}; color:{S.CYAN};
                border:1px solid {S.CYAN}; border-radius:4px;
                font-size:13px; font-weight:600; padding:8px 22px;
            }}
            QPushButton:hover  {{ background:#0A1A2A; }}
            QPushButton:pressed {{ background:{S.BG_DEEP}; }}
            QPushButton:disabled {{
                color:{S.TEXT_DIM}; border-color:{S.BORDER};
                background:{S.BG_PANEL};
            }}
        """)
        self._btn_return_home.clicked.connect(self._on_return_home)

        home_row.addWidget(self._btn_set_home)
        home_row.addWidget(self._btn_return_home)
        right.addLayout(home_row)

        right.addWidget(HLine())

        # Scan log
        right.addWidget(SectionTitle("Scan Log"))
        self._log = QLabel("-")
        self._log.setWordWrap(True)
        self._log.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:11px; background:{S.BG_PANEL};"
            f"border:1px solid {S.BORDER}; border-radius:4px; padding:8px;"
        )
        self._log.setMinimumHeight(80)
        self._log.setAlignment(Qt.AlignmentFlag.AlignTop)
        right.addWidget(self._log, stretch=1)

        # Run / Stop
        self._btn_run = make_button("▶  RUN SCAN", role="primary")
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

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_run)
        btn_row.addWidget(self._btn_stop)
        right.addLayout(btn_row)

        right_widget = QWidget()
        right_widget.setLayout(right)
        right_widget.setMinimumWidth(360)
        root.addWidget(right_widget, stretch=2)

    #  Helpers 

    def update_calibration(self, cal: dict):
        """Receive calibration data from HelpPanel and propagate to all rows."""
        self._calibration = cal
        self._pathlog.update_calibration(cal)

    def _log_msg(self, text: str):
        self._log.setText(text)
        self.status_message.emit(f"[Scan]  {text}")

    def _set_running(self, running: bool):
        self._btn_run.setEnabled(not running)
        self._btn_stop.setEnabled(running)
        self._btn_return_home.setEnabled(
            not running and bool(self._home_snapshot)
        )

    def _channel_value(self):
        txt = self._scope_ch_combo.currentText()
        return 1 if txt == "CH1" else 2 if txt == "CH2" else "both"

    #  Slots  

    def _on_set_home(self):
        motions = self._pathlog.get_motions()
        if not motions:
            self._home_info.setText("No motions in PathLog — add at least one first.")
            self._home_info.setStyleSheet(
                f"color:{S.RED}; font-size:11px; background:transparent;"
            )
            return
        self._home_snapshot = motions
        self._btn_return_home.setEnabled(True)
        axes = ", ".join(sorted({m.axis.upper() for m in motions}))
        info = (f"Home set  ·  {len(motions)} motion(s)  ·  axes: {axes}\n"
                f"Return will use reversed order, opposite direction, half steps.")
        self._home_info.setText(info)
        self._home_info.setStyleSheet(
            f"color:{S.GREEN}; font-size:11px; background:transparent;"
        )
        self._log_msg(f"Home set  ·  {len(motions)} motion(s) snapshotted")

    def _on_return_home(self):
        if not self._home_snapshot:
            return
        self._set_running(True)
        self._btn_set_home.setEnabled(False)
        self._log_msg("Returning to home …")

        self._worker = ReturnHomeWorker(
            motors   = self._motors,
            snapshot = self._home_snapshot,
        )
        self._worker.progress.connect(
            lambda m, s, t: self._log_msg(
                f"Return  motion {m}  ·  step {s}/{t} …"
            )
        )
        self._worker.finished.connect(self._on_return_home_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_return_home_done(self):
        self._set_running(False)
        self._btn_set_home.setEnabled(True)
        self._log_msg("Return to home complete ✓")

    def _on_run(self):
        motions = self._pathlog.get_motions()
        if not motions:
            self._log_msg("No motions in Path Log — add at least one.")
            return

        scope_cfg = {
            "channel"   : self._channel_value(),
            "output_dir": self._scope_block.output_dir or "data/scan/scope",
            "prefix"    : self._scope_block.prefix,
            "triggers"  : self._scope_block.triggers,
        }
        pm_cfg = {
            "wavelength": self._pm_wl.value(),
            "n_samples" : self._pm_samples.value(),
            "averaging" : self._pm_avg.value(),
            "output_dir": self._pm_block.output_dir or "data/scan/power",
            "prefix"    : self._pm_block.prefix,
            "triggers"  : self._pm_block.triggers,
        }

        self._worker = ScanWorker(
            motors        = self._motors,
            motions       = motions,
            scope         = self._scope,
            scope_enabled = self._scope_block.enabled,
            scope_cfg     = scope_cfg,
            pm            = self._pm,
            pm_enabled    = self._pm_block.enabled,
            pm_cfg        = pm_cfg,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.measurement_done.connect(self._on_measurement_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._set_running(True)
        self._log_msg(f"Scan started  ·  {len(motions)} motion(s)")
        self._worker.start()

    def _on_stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(5000)
        self._set_running(False)
        self._log_msg("Scan stopped by user.")

    def _on_progress(self, m_idx, step, total):
        self._log_msg(f"Motion {m_idx}  ·  step {step}/{total}  running …")

    def _on_step_done(self, m_idx, step, total):
        self._log_msg(f"Motion {m_idx}  ·  step {step}/{total}  done")

    def _on_measurement_done(self, m_idx, step, label):
        self._log_msg(f"Motion {m_idx}  ·  step {step}  →  saved {label}")

    def _on_finished(self):
        self._set_running(False)
        self._log_msg("Scan complete ✓")

    def _on_error(self, message: str):
        self._set_running(False)
        self._log_msg(f"ERROR: {message}")
