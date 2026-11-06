# gui/loop_scan_panel.py
"""
Loop Scan Panel — Repeated motion scan with configurable cycle filter.

Structure
---------
Left  : PathLog  — identical to ScanPanel (reuses MotionRow from scan_panel)
Right : Loop Settings + Measurement Policy + Cycle Filter + Log + Run/Stop

Loop Settings
  - Number of cycles (N or infinite)
  - Pause between cycles (seconds, can be 0)

Measurement Policy
  - Identical to ScanPanel (Oscilloscope / Power Meter with trigger rules)

Cycle Filter (applies to both instruments equally)
  - Every cycle
  - Every N cycles
  - Specific cycles (comma-separated list)
  - First and last only
"""

from __future__ import annotations

import csv
import numpy as np
from pathlib  import Path
from datetime import datetime
from typing   import List, Optional, Set

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QComboBox,
    QGroupBox, QLineEdit, QFileDialog, QCheckBox, QFrame,
    QStackedWidget, QButtonGroup, QRadioButton,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import gui.style as S
from gui.widgets  import SectionTitle, HLine, make_button

# Reuse everything from scan_panel — no duplication
from gui.scan_panel import (
    MotionEntry, TriggerRule,
    _load_calibration, _um_to_pulses,
    MotionRow, TriggerRow, MeasurementBlock, PathLog,
)


# ══════════════════════════════════════════════════════════════════════════════
# Cycle filter helpers
# ══════════════════════════════════════════════════════════════════════════════

def _parse_specific_cycles(text: str) -> Set[int]:
    """
    Parse a comma-separated list of cycle numbers.
    "1, 3, 5-8, 10" → {1, 3, 5, 6, 7, 8, 10}
    Ranges with dash are supported.
    """
    result = set()
    for part in text.split(','):
        part = part.strip()
        if '-' in part:
            try:
                a, b = part.split('-', 1)
                result.update(range(int(a.strip()), int(b.strip()) + 1))
            except ValueError:
                pass
        else:
            try:
                result.add(int(part))
            except ValueError:
                pass
    return result


def _cycle_matches(cycle: int, total: int, mode: str,
                   every_n: int, specific: Set[int]) -> bool:
    """
    Returns True if measurements should be saved on this cycle.

    Parameters
    ----------
    cycle   : current cycle number (1-based)
    total   : total number of cycles (0 = infinite)
    mode    : "every" | "every_n" | "specific" | "first_last"
    every_n : N for "every_n" mode
    specific: set of cycle numbers for "specific" mode
    """
    if mode == "every":
        return True
    if mode == "every_n":
        return (cycle % every_n) == 1   # cycles 1, 1+N, 1+2N, ...
    if mode == "specific":
        return cycle in specific
    if mode == "first_last":
        if total == 0:
            return cycle == 1           # infinite: only first
        return cycle == 1 or cycle == total
    return False


# ══════════════════════════════════════════════════════════════════════════════
# Loop Scan Worker
# ══════════════════════════════════════════════════════════════════════════════

class LoopScanWorker(QThread):
    """
    Executes the full loop scan off the UI thread.

    Signals
    -------
    cycle_started(cycle, total)
    progress(cycle, total, motion_idx, step, total_steps)
    step_done(cycle, total, motion_idx, step, total_steps)
    measurement_done(cycle, motion_idx, step, label)
    cycle_done(cycle, total)
    finished()
    error(str)
    """
    cycle_started    = pyqtSignal(int, int)
    progress         = pyqtSignal(int, int, int, int, int)
    step_done        = pyqtSignal(int, int, int, int, int)
    measurement_done = pyqtSignal(int, int, int, str)
    cycle_done       = pyqtSignal(int, int)
    finished         = pyqtSignal()
    error            = pyqtSignal(str)

    def __init__(
        self,
        motors        : dict,
        motions       : List[MotionEntry],
        n_cycles      : int,          # 0 = infinite
        pause_s       : float,
        scope,
        scope_enabled : bool,
        scope_cfg     : dict,
        pm,
        pm_enabled    : bool,
        pm_cfg        : dict,
        cycle_mode    : str,          # "every"|"every_n"|"specific"|"first_last"
        cycle_every_n : int,
        cycle_specific: Set[int],
    ):
        super().__init__()
        self._motors         = motors
        self._motions        = motions
        self._n_cycles       = n_cycles
        self._pause_s        = pause_s
        self._scope          = scope
        self._scope_en       = scope_enabled
        self._scope_cfg      = scope_cfg
        self._pm             = pm
        self._pm_en          = pm_enabled
        self._pm_cfg         = pm_cfg
        self._cycle_mode     = cycle_mode
        self._cycle_every_n  = cycle_every_n
        self._cycle_specific = cycle_specific
        self._running        = False

    def stop(self):
        self._running = False

    # ── Helpers ───────────────────────────────────────────────────

    @staticmethod
    def _ts() -> str:
        t = datetime.now()
        return t.strftime("%Y%m%d_%H%M%S_") + f"{t.microsecond // 1000:03d}"

    def _should_measure_this_cycle(self, cycle: int) -> bool:
        return _cycle_matches(
            cycle, self._n_cycles,
            self._cycle_mode, self._cycle_every_n, self._cycle_specific
        )

    def _matching_rules(self, cfg: dict, motion_idx: int,
                         step: int, total: int) -> list:
        return [r for r in cfg.get("triggers", [])
                if r.matches(motion_idx, step, total)]

    def _save_scope(self, cycle: int, motion_idx: int, step: int,
                    output_dir_override=None):
        cfg      = self._scope_cfg
        channel  = cfg.get("channel", 1)
        out_dir  = output_dir_override or cfg.get("output_dir", "data/loop/scope")
        prefix   = cfg.get("prefix", "")
        channels = [1, 2] if channel == "both" else [channel]
        for ch in channels:
            t, v, meta = self._scope.read_waveform_meta(ch)
            base = (f"{prefix}_c{cycle:03d}_m{motion_idx:02d}"
                    f"_s{step:03d}_CH{ch}_{self._ts()}"
                    if prefix else
                    f"loop_c{cycle:03d}_m{motion_idx:02d}"
                    f"_s{step:03d}_CH{ch}_{self._ts()}")
            p = Path(out_dir) / f"{base}.csv"
            p.parent.mkdir(parents=True, exist_ok=True)
            import csv as _csv
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

    def _save_pm(self, cycle: int, motion_idx: int, step: int,
                 output_dir_override=None):
        cfg     = self._pm_cfg
        out_dir = output_dir_override or cfg.get("output_dir", "data/loop/power")
        prefix  = cfg.get("prefix", "")
        wl      = cfg.get("wavelength", 1550.0)
        n       = cfg.get("n_samples", 10)
        avg     = cfg.get("averaging", 5)
        self._pm.set_wavelength(wl)
        self._pm.set_auto_range(True)
        stats = self._pm.read_average(n_samples=n, averaging=avg)
        base = (f"{prefix}_c{cycle:03d}_m{motion_idx:02d}_s{step:03d}_{self._ts()}"
                if prefix else
                f"loop_c{cycle:03d}_m{motion_idx:02d}_s{step:03d}_{self._ts()}")
        p = Path(out_dir) / f"{base}.csv"
        p.parent.mkdir(parents=True, exist_ok=True)
        import csv as _csv
        with open(p, "w", newline="") as f:
            w = _csv.writer(f)
            w.writerow(["# cycle",       cycle])
            w.writerow(["timestamp",     datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            w.writerow(["wavelength_nm", f"{wl:.1f}"])
            w.writerow(["n_samples",     n])
            w.writerow(["averaging",     avg])
            w.writerow([])
            w.writerow(["mean_W", "std_W", "min_W", "max_W", "mean_mW"])
            w.writerow([f"{stats['mean_w']:.6E}", f"{stats['std_w']:.6E}",
                        f"{stats['min_w']:.6E}",  f"{stats['max_w']:.6E}",
                        f"{stats['mean_mw']:.6f}"])
        self.measurement_done.emit(cycle, motion_idx, step, f"power {p.name}")

    # ── Main loop ─────────────────────────────────────────────────

    def run(self):
        self._running = True
        cycle = 0

        try:
            while self._running:
                cycle += 1

                # Check cycle limit (0 = infinite)
                if self._n_cycles > 0 and cycle > self._n_cycles:
                    break

                total = self._n_cycles   # 0 if infinite
                self.cycle_started.emit(cycle, total)
                measure_this_cycle = self._should_measure_this_cycle(cycle)

                # ── Execute all motions ───────────────────────────
                for m_idx, motion in enumerate(self._motions, start=1):
                    if not self._running:
                        break

                    motor = self._motors.get(motion.axis)
                    if motor is None:
                        self.error.emit(
                            f"Cycle {cycle}, Motion {m_idx}: "
                            f"axis '{motion.axis.upper()}' not connected.")
                        return

                    speed = (1 if motion.forward else -1) * abs(motion.speed)

                    for step in range(1, motion.steps + 1):
                        if not self._running:
                            break

                        self.progress.emit(cycle, total, m_idx, step, motion.steps)
                        motor.move(pulses=motion.pulses, speed=speed, wait=True)
                        self.step_done.emit(cycle, total, m_idx, step, motion.steps)

                        # Triggered measurements (only if this cycle qualifies)
                        if measure_this_cycle:
                            if self._scope_en:
                                for rule in self._matching_rules(
                                        self._scope_cfg, m_idx, step, motion.steps):
                                    self._save_scope(cycle, m_idx, step,
                                                     output_dir_override=rule.output_dir)
                            if self._pm_en:
                                for rule in self._matching_rules(
                                        self._pm_cfg, m_idx, step, motion.steps):
                                    self._save_pm(cycle, m_idx, step,
                                                  output_dir_override=rule.output_dir)

                        # Inter-step delay
                        if motion.delay_s > 0 and step < motion.steps:
                            elapsed = 0.0
                            while self._running and elapsed < motion.delay_s:
                                self.msleep(100)
                                elapsed += 0.1

                self.cycle_done.emit(cycle, total)

                # ── Pause between cycles ──────────────────────────
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


# ══════════════════════════════════════════════════════════════════════════════
# Cycle Filter Widget
# ══════════════════════════════════════════════════════════════════════════════

class CycleFilterWidget(QGroupBox):
    """
    Radio-button selector for the cycle filter policy.
    All four modes in one compact widget.
    """

    def __init__(self, parent=None):
        super().__init__("Cycle Filter", parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(8)
        root.setContentsMargins(10, 16, 10, 12)

        self._btn_group = QButtonGroup(self)
        rb_style = f"""
            QRadioButton {{
                color:{S.TEXT}; font-size:13px;
                background:transparent; spacing:8px;
            }}
            QRadioButton::indicator {{
                width:14px; height:14px; border-radius:7px;
                border:2px solid {S.BORDER_LT}; background:{S.BG_WIDGET};
            }}
            QRadioButton::indicator:checked {{
                background:{S.ACCENT}; border-color:{S.ACCENT};
            }}
        """

        # Option A — Every cycle
        self._rb_every = QRadioButton("Every cycle")
        self._rb_every.setStyleSheet(rb_style)
        self._rb_every.setChecked(True)
        self._btn_group.addButton(self._rb_every)
        root.addWidget(self._rb_every)

        # Option B — Every N cycles
        row_n = QHBoxLayout()
        self._rb_every_n = QRadioButton("Every")
        self._rb_every_n.setStyleSheet(rb_style)
        self._btn_group.addButton(self._rb_every_n)
        self._every_n_spin = QSpinBox()
        self._every_n_spin.setRange(2, 9999)
        self._every_n_spin.setValue(2)
        self._every_n_spin.setFixedWidth(70)
        self._every_n_spin.setEnabled(False)
        lbl_n = QLabel("cycles")
        lbl_n.setStyleSheet(f"color:{S.TEXT_SUB}; background:transparent;")
        row_n.addWidget(self._rb_every_n)
        row_n.addWidget(self._every_n_spin)
        row_n.addWidget(lbl_n)
        row_n.addStretch()
        root.addLayout(row_n)

        # Option C — Specific cycles
        row_sp = QHBoxLayout()
        self._rb_specific = QRadioButton("Cycles:")
        self._rb_specific.setStyleSheet(rb_style)
        self._btn_group.addButton(self._rb_specific)
        self._specific_edit = QLineEdit()
        self._specific_edit.setPlaceholderText("e.g.  1, 3, 5-8, 10")
        self._specific_edit.setEnabled(False)
        self._specific_edit.setToolTip(
            "Comma-separated cycle numbers or ranges (e.g. 1, 3, 5-8, 10)"
        )
        row_sp.addWidget(self._rb_specific)
        row_sp.addWidget(self._specific_edit, stretch=1)
        root.addLayout(row_sp)

        # Option D — First and last only
        self._rb_fl = QRadioButton("First and last only")
        self._rb_fl.setStyleSheet(rb_style)
        self._btn_group.addButton(self._rb_fl)
        root.addWidget(self._rb_fl)

        # Connect radio buttons to enable/disable dependent widgets
        self._rb_every.toggled.connect(lambda _: self._refresh_state())
        self._rb_every_n.toggled.connect(lambda _: self._refresh_state())
        self._rb_specific.toggled.connect(lambda _: self._refresh_state())
        self._rb_fl.toggled.connect(lambda _: self._refresh_state())

    def _refresh_state(self):
        self._every_n_spin.setEnabled(self._rb_every_n.isChecked())
        self._specific_edit.setEnabled(self._rb_specific.isChecked())

    # ── Public interface ──────────────────────────────────────────

    @property
    def mode(self) -> str:
        if self._rb_every.isChecked():    return "every"
        if self._rb_every_n.isChecked():  return "every_n"
        if self._rb_specific.isChecked(): return "specific"
        return "first_last"

    @property
    def every_n(self) -> int:
        return self._every_n_spin.value()

    @property
    def specific_cycles(self) -> Set[int]:
        return _parse_specific_cycles(self._specific_edit.text())


# ══════════════════════════════════════════════════════════════════════════════
# Main Loop Scan Panel
# ══════════════════════════════════════════════════════════════════════════════

class LoopScanPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, motors: dict, scope, pm, parent=None):
        super().__init__(parent)
        self._motors      = motors
        self._scope       = scope
        self._pm          = pm
        self._worker      = None
        self._calibration = _load_calibration()
        self._build_ui()

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        # ── Left: PathLog ──────────────────────────────────────────
        axes = sorted(self._motors.keys()) or ["x", "y", "z"]
        self._pathlog = PathLog(available_axes=axes,
                                calibration=self._calibration)
        self._pathlog.setMinimumWidth(750)
        root.addWidget(self._pathlog, stretch=3)

        # ── Right: settings + run ──────────────────────────────────
        right = QVBoxLayout()
        right.setSpacing(12)

        # Title
        title = QLabel("Loop Scan")
        title.setStyleSheet(
            f"color:{S.TEXT}; font-size:20px; font-weight:700; background:transparent;"
        )
        subtitle = QLabel("Repeat a motion sequence N times with configurable measurement policy.")
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:12px; background:transparent;"
        )
        right.addWidget(title)
        right.addWidget(subtitle)
        right.addWidget(HLine())

        # ── Loop settings ─────────────────────────────────────────
        loop_box = QGroupBox("Loop Settings")
        lg = QGridLayout(loop_box)
        lg.setSpacing(10)
        lg.setContentsMargins(10, 16, 10, 12)

        # Number of cycles
        lg.addWidget(self._lbl("Cycles"), 0, 0)
        cycle_row = QHBoxLayout()
        self._cycles_spin = QSpinBox()
        self._cycles_spin.setRange(1, 999_999)
        self._cycles_spin.setValue(10)
        self._cycles_spin.setFixedWidth(90)
        self._infinite_check = QCheckBox("∞  Infinite")
        self._infinite_check.setStyleSheet(f"""
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
        self._infinite_check.toggled.connect(
            lambda checked: self._cycles_spin.setEnabled(not checked)
        )
        cycle_row.addWidget(self._cycles_spin)
        cycle_row.addWidget(self._infinite_check)
        cycle_row.addStretch()
        lg.addLayout(cycle_row, 0, 1)

        # Pause between cycles
        lg.addWidget(self._lbl("Pause between cycles (s)"), 1, 0)
        self._pause_spin = QDoubleSpinBox()
        self._pause_spin.setRange(0.0, 3600.0)
        self._pause_spin.setValue(0.0)
        self._pause_spin.setSingleStep(0.5)
        self._pause_spin.setDecimals(1)
        self._pause_spin.setFixedWidth(90)
        self._pause_spin.setToolTip("Pause between loop cycles (0 = no pause)")
        lg.addWidget(self._pause_spin, 1, 1)

        right.addWidget(loop_box)

        # ── Cycle filter ──────────────────────────────────────────
        self._cycle_filter = CycleFilterWidget()
        right.addWidget(self._cycle_filter)

        # ── Measurement policy ────────────────────────────────────
        right.addWidget(SectionTitle("Measurements"))

        # Instrument dropdown + stacked pages
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

        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background:transparent;")
        self._instr_combo.currentIndexChanged.connect(self._stack.setCurrentIndex)

        # Page 0 — Oscilloscope
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
        self._scope_block._dir_edit.setText("data/loop/scope")
        self._stack.addWidget(self._scope_block)

        # Page 1 — Power Meter
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
            l = QLabel(lbl_txt)
            l.setStyleSheet("background:transparent;")
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
        self._pm_block._dir_edit.setText("data/loop/power")
        self._stack.addWidget(self._pm_block)

        # Scroll wrapper for measurement block
        stack_scroll = QScrollArea()
        stack_scroll.setWidget(self._stack)
        stack_scroll.setWidgetResizable(True)
        stack_scroll.setFrameShape(QFrame.Shape.NoFrame)
        stack_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        stack_scroll.setStyleSheet("background:transparent;")
        right.addWidget(stack_scroll, stretch=1)

        right.addWidget(HLine())

        # ── Scan log ──────────────────────────────────────────────
        right.addWidget(SectionTitle("Loop Log"))
        self._log = QLabel("—")
        self._log.setWordWrap(True)
        self._log.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:11px; background:{S.BG_PANEL};"
            f"border:1px solid {S.BORDER}; border-radius:4px; padding:8px;"
        )
        self._log.setMinimumHeight(90)
        self._log.setAlignment(Qt.AlignmentFlag.AlignTop)
        right.addWidget(self._log, stretch=1)

        # ── Run / Stop ────────────────────────────────────────────
        self._btn_run = make_button("▶  RUN LOOP", role="primary")
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
        right_widget.setMinimumWidth(380)
        root.addWidget(right_widget, stretch=2)

    # ── Helpers ────────────────────────────────────────────────────

    @staticmethod
    def _lbl(text: str) -> QLabel:
        l = QLabel(text)
        l.setStyleSheet(f"color:{S.TEXT_SUB}; background:transparent;")
        return l

    def _log_msg(self, text: str):
        self._log.setText(text)
        self.status_message.emit(f"[Loop Scan]  {text}")

    def _set_running(self, running: bool):
        self._btn_run.setEnabled(not running)
        self._btn_stop.setEnabled(running)

    def _channel_value(self):
        txt = self._scope_ch_combo.currentText()
        return 1 if txt == "CH1" else 2 if txt == "CH2" else "both"

    def update_calibration(self, cal: dict):
        """Receive calibration data from HelpPanel."""
        self._calibration = cal
        self._pathlog.update_calibration(cal)

    # ── Slots ──────────────────────────────────────────────────────

    def _on_run(self):
        motions = self._pathlog.get_motions()
        if not motions:
            self._log_msg("No motions in Path Log — add at least one.")
            return

        n_cycles = 0 if self._infinite_check.isChecked() \
                   else self._cycles_spin.value()

        scope_cfg = {
            "channel"   : self._channel_value(),
            "output_dir": self._scope_block.output_dir or "data/loop/scope",
            "prefix"    : self._scope_block.prefix,
            "triggers"  : self._scope_block.triggers,
        }
        pm_cfg = {
            "wavelength": self._pm_wl.value(),
            "n_samples" : self._pm_samples.value(),
            "averaging" : self._pm_avg.value(),
            "output_dir": self._pm_block.output_dir or "data/loop/power",
            "prefix"    : self._pm_block.prefix,
            "triggers"  : self._pm_block.triggers,
        }

        self._worker = LoopScanWorker(
            motors         = self._motors,
            motions        = motions,
            n_cycles       = n_cycles,
            pause_s        = self._pause_spin.value(),
            scope          = self._scope,
            scope_enabled  = self._scope_block.enabled,
            scope_cfg      = scope_cfg,
            pm             = self._pm,
            pm_enabled     = self._pm_block.enabled,
            pm_cfg         = pm_cfg,
            cycle_mode     = self._cycle_filter.mode,
            cycle_every_n  = self._cycle_filter.every_n,
            cycle_specific = self._cycle_filter.specific_cycles,
        )
        self._worker.cycle_started.connect(self._on_cycle_started)
        self._worker.progress.connect(self._on_progress)
        self._worker.step_done.connect(self._on_step_done)
        self._worker.measurement_done.connect(self._on_measurement_done)
        self._worker.cycle_done.connect(self._on_cycle_done)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._set_running(True)
        total_str = "∞" if n_cycles == 0 else str(n_cycles)
        self._log_msg(
            f"Loop started  ·  {total_str} cycle(s)  ·  "
            f"{len(motions)} motion(s) per cycle"
        )
        self._worker.start()

    def _on_stop(self):
        if self._worker:
            self._worker.stop()
            self._worker.wait(5000)
        self._set_running(False)
        self._log_msg("Loop stopped by user.")

    def _on_cycle_started(self, cycle: int, total: int):
        total_str = "∞" if total == 0 else str(total)
        self._log_msg(f"Cycle {cycle}/{total_str}  starting …")

    def _on_progress(self, cycle: int, total: int,
                      m_idx: int, step: int, total_steps: int):
        total_str = "∞" if total == 0 else str(total)
        self._log_msg(
            f"Cycle {cycle}/{total_str}  ·  "
            f"Motion {m_idx}  ·  step {step}/{total_steps}  running …"
        )

    def _on_step_done(self, cycle: int, total: int,
                       m_idx: int, step: int, total_steps: int):
        total_str = "∞" if total == 0 else str(total)
        self._log_msg(
            f"Cycle {cycle}/{total_str}  ·  "
            f"Motion {m_idx}  ·  step {step}/{total_steps}  done"
        )

    def _on_measurement_done(self, cycle: int, m_idx: int,
                              step: int, label: str):
        self._log_msg(
            f"Cycle {cycle}  ·  Motion {m_idx}  ·  step {step}  →  saved {label}"
        )

    def _on_cycle_done(self, cycle: int, total: int):
        total_str = "∞" if total == 0 else str(total)
        self._log_msg(f"Cycle {cycle}/{total_str}  complete ✓")

    def _on_finished(self):
        self._set_running(False)
        self._log_msg("Loop complete ✓")

    def _on_error(self, message: str):
        self._set_running(False)
        self._log_msg(f"ERROR: {message}")