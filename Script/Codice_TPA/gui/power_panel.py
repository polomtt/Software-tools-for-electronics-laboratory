# gui/power_panel.py
"""
Power Meter Panel - Thorlabs PM100D

Features:
  - Continuous live reading (START / STOP)
  - RECORD toggle: while active, saves one CSV file per reading
  - Display: current value + std, min, max
  - Configurable wavelength, samples, averaging, read interval
"""

import csv
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QDoubleSpinBox, QSpinBox, QGroupBox,
    QLineEdit, QFileDialog, QComboBox,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal

import gui.style as S
from gui.widgets import StatusLED, SectionTitle, HLine, DigitalDisplay, make_button


# Continuous worker 

class ContinuousReadWorker(QThread):
    """
    Reads power in a loop until stop() is called.
    Emits one signal per reading.
    """
    reading_ready = pyqtSignal(dict)   # stats dict from read_average()
    error         = pyqtSignal(str)

    def __init__(self, pm, wavelength: float, n_samples: int,
                 averaging: int, interval_ms: int):
        super().__init__()
        self._pm          = pm
        self._wavelength  = wavelength
        self._n_samples   = n_samples
        self._averaging   = averaging
        self._interval_ms = max(interval_ms, 100)
        self._running     = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        try:
            if not self._pm.is_connected:
                self._pm.connect()
            self._pm.set_wavelength(self._wavelength)
            self._pm.set_auto_range(True)
        except Exception as exc:
            self.error.emit(str(exc))
            return

        while self._running:
            try:
                stats = self._pm.read_average(
                    n_samples = self._n_samples,
                    averaging = self._averaging,
                )
                self.reading_ready.emit(stats)
            except Exception as exc:
                self.error.emit(str(exc))
                break

            # Interruptible sleep: check stop flag every 50 ms
            elapsed = 0
            while self._running and elapsed < self._interval_ms:
                self.msleep(50)
                elapsed += 50


#  CSV helper 

def _save_single_reading(stats: dict, wavelength: float,
                          output_dir: str, prefix: str) -> Path:
    """
    Save one reading to a uniquely named CSV file.
    Filename: <prefix>_<YYYYMMDD_HHMMSS_mmm>.csv
    """
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts       = datetime.now()
    ts_str   = ts.strftime("%Y%m%d_%H%M%S_") + f"{ts.microsecond // 1000:03d}"
    base     = f"{prefix}_{ts_str}" if prefix else f"power_{ts_str}"
    filepath = out_dir / f"{base}.csv"

    with open(filepath, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp",    ts.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]])
        writer.writerow(["wavelength_nm", f"{wavelength:.1f}"])
        writer.writerow(["n_samples",    stats["n_samples"]])
        writer.writerow(["averaging",    stats["averaging"]])
        writer.writerow([])
        writer.writerow(["mean_W", "std_W", "min_W", "max_W", "mean_mW"])
        writer.writerow([
            f"{stats['mean_w']:.6E}",
            f"{stats['std_w']:.6E}",
            f"{stats['min_w']:.6E}",
            f"{stats['max_w']:.6E}",
            f"{stats['mean_mw']:.6f}",
        ])

    return filepath


# Panel 

class PowerPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, pm, parent=None):
        super().__init__(parent)
        self._pm             = pm
        self._worker         = None   # always kept as instance var - no GC crash
        self._recording      = False
        self._reading_count  = 0
        self._last_stats     = None   # used to re-render when unit changes
        self._build_ui()
        self._refresh_led()

    #  UI 

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(20)

        #  Left sidebar 
        sidebar = QVBoxLayout()
        sidebar.setSpacing(10)

        # Title
        title = QLabel("Power Meter")
        title.setStyleSheet(
            f"color:{S.TEXT}; font-size:20px; font-weight:700; background:transparent;"
        )
        subtitle = QLabel("Thorlabs PM100D  ·  SCPI/USB-TMC")
        subtitle.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:12px; background:transparent;"
        )
        con_row = QHBoxLayout()
        self._led = StatusLED("disconnected")
        self._conn_label = QLabel("Disconnected")
        self._conn_label.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:12px; background:transparent;"
        )
        con_row.addWidget(self._led, alignment=Qt.AlignmentFlag.AlignVCenter)
        con_row.addSpacing(6)
        con_row.addWidget(self._conn_label)
        con_row.addStretch()

        sidebar.addWidget(title)
        sidebar.addWidget(subtitle)
        sidebar.addLayout(con_row)
        sidebar.addWidget(HLine())

        # Measurement settings
        meas_box = QGroupBox("Measurement Settings")
        mg = QGridLayout(meas_box)
        mg.setSpacing(8)

        mg.addWidget(QLabel("Wavelength (nm)"), 0, 0)
        self._wl_spin = QDoubleSpinBox()
        self._wl_spin.setRange(200, 3500)
        self._wl_spin.setValue(1550)
        self._wl_spin.setSingleStep(10)
        self._wl_spin.setDecimals(1)
        mg.addWidget(self._wl_spin, 0, 1)

        mg.addWidget(QLabel("Samples"), 1, 0)
        self._samples_spin = QSpinBox()
        self._samples_spin.setRange(1, 1000)
        self._samples_spin.setValue(10)
        mg.addWidget(self._samples_spin, 1, 1)

        mg.addWidget(QLabel("Averaging"), 2, 0)
        self._avg_spin = QSpinBox()
        self._avg_spin.setRange(1, 300)
        self._avg_spin.setValue(5)
        self._avg_spin.setToolTip("Hardware averaging count on the PM100D")
        mg.addWidget(self._avg_spin, 2, 1)

        mg.addWidget(QLabel("Interval (ms)"), 3, 0)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(100, 60000)
        self._interval_spin.setValue(500)
        self._interval_spin.setSingleStep(100)
        self._interval_spin.setToolTip("Wait between readings in milliseconds")
        mg.addWidget(self._interval_spin, 3, 1)

        sidebar.addWidget(meas_box)

        # Save settings
        save_box = QGroupBox("Save Location  (for RECORD)")
        sv = QVBoxLayout(save_box)
        sv.setSpacing(8)

        self._dir_edit = QLineEdit("data/power")
        self._dir_edit.setPlaceholderText("Output folder")
        btn_browse = make_button("Browse …")
        btn_browse.setFixedHeight(32)
        btn_browse.clicked.connect(self._on_browse)
        sv.addWidget(self._dir_edit)
        sv.addWidget(btn_browse)

        sv.addWidget(QLabel("Filename prefix (optional):"))
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText("e.g.  run_001  →  run_001_<timestamp>.csv")
        sv.addWidget(self._prefix_edit)

        sidebar.addWidget(save_box)
        sidebar.addStretch()

        # Action buttons
        self._btn_start = make_button("▶  START", role="primary")
        self._btn_start.setMinimumHeight(42)
        self._btn_start.setCheckable(True)
        self._btn_start.setToolTip("Start / stop continuous reading")
        self._btn_start.clicked.connect(self._on_start_stop)

        self._btn_record = make_button("⏺  RECORD", role="success")
        self._btn_record.setMinimumHeight(38)
        self._btn_record.setCheckable(True)
        self._btn_record.setEnabled(False)
        self._btn_record.setToolTip(
            "While active: saves one CSV file per reading to the selected folder"
        )
        self._btn_record.clicked.connect(self._on_record_toggle)

        sidebar.addWidget(self._btn_start)
        sidebar.addWidget(self._btn_record)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sidebar.addWidget(self._status_lbl)

        sidebar_widget = QWidget()
        sidebar_widget.setLayout(sidebar)
        sidebar_widget.setFixedWidth(280)

        #  Right side - live display 
        right = QVBoxLayout()
        right.setSpacing(14)
        right.setAlignment(Qt.AlignmentFlag.AlignTop)

        right.addWidget(SectionTitle("Live Reading"))

        # Main digital display
        self._display_mw = DigitalDisplay("---", color=S.GREEN, font_size=52)

        self._unit_combo = QComboBox()
        self._unit_combo.addItems(["mW", "µW"])
        self._unit_combo.setFixedWidth(72)
        self._unit_combo.setFixedHeight(40)
        self._unit_combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {S.BG_WIDGET};
                color: {S.TEXT_SUB};
                border: 1px solid {S.BORDER};
                border-radius: 4px;
                padding: 4px 8px;
                font-size: 16px;
                font-weight: 700;
            }}
            QComboBox:focus {{ border-color: {S.ACCENT}; }}
            QComboBox::drop-down {{
                border: none;
                background: {S.BG_HOVER};
                width: 20px;
                border-radius: 0 4px 4px 0;
            }}
            QComboBox QAbstractItemView {{
                background: {S.BG_PANEL};
                color: {S.TEXT};
                border: 1px solid {S.BORDER_LT};
                selection-background-color: {S.BG_HOVER};
                font-size: 14px;
                padding: 4px;
            }}
        """)
        self._unit_combo.currentTextChanged.connect(self._on_unit_changed)

        disp_row = QHBoxLayout()
        disp_row.addWidget(self._display_mw, stretch=1)
        disp_row.addWidget(
            self._unit_combo, alignment=Qt.AlignmentFlag.AlignBottom
        )
        right.addLayout(disp_row)

        right.addWidget(HLine())

        # Stat cards
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self._stat_labels = {}

        for key, label in [("std", "± Std Dev"), ("min", "Min"), ("max", "Max")]:
            card = QWidget()
            card.setStyleSheet(
                f"background:{S.BG_PANEL}; border:1px solid {S.BORDER};"
                f"border-radius:6px;"
            )
            cl = QVBoxLayout(card)
            cl.setContentsMargins(10, 8, 10, 8)
            cl.setSpacing(4)
            name_lbl = QLabel(label)
            name_lbl.setStyleSheet(
                f"color:{S.TEXT_SUB}; font-size:10px; font-weight:700;"
                f"letter-spacing:1px; background:transparent; border:none;"
            )
            name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            val_lbl = QLabel("---")
            val_lbl.setStyleSheet(
                f"color:{S.CYAN}; font-family:{S.FONT_MONO}; font-size:15px;"
                f"font-weight:600; background:transparent; border:none;"
            )
            val_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(name_lbl)
            cl.addWidget(val_lbl)
            self._stat_labels[key] = val_lbl
            stats_row.addWidget(card)

        right.addLayout(stats_row)

        # Recording info
        self._rec_lbl = QLabel("")
        self._rec_lbl.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        self._rec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self._rec_lbl)

        right.addStretch()

        right_widget = QWidget()
        right_widget.setLayout(right)

        root.addWidget(sidebar_widget)
        root.addWidget(right_widget, stretch=1)

    #  Helpers 

    def _refresh_led(self):
        connected = self._pm.is_connected
        self._led.set_state("connected" if connected else "disconnected")
        text  = "Connected"    if connected else "Disconnected"
        color = S.GREEN        if connected else S.TEXT_DIM
        self._conn_label.setText(text)
        self._conn_label.setStyleSheet(
            f"color:{color}; font-size:12px; background:transparent;"
        )

    def _set_status(self, text: str, color: str = None):
        color = color or S.TEXT_DIM
        self._status_lbl.setStyleSheet(
            f"color:{color}; font-size:11px; background:transparent;"
        )
        self._status_lbl.setText(text)

    def _update_display(self, stats: dict):
        self._last_stats = stats
        unit = self._unit_combo.currentText()

        if unit == "mW":
            factor, decimals = 1_000, 5
        else:                          # µW
            factor, decimals = 1_000_000, 3

        self._display_mw.set_value(stats["mean_w"] * factor, unit="", decimals=decimals)
        self._stat_labels["std"].setText(f"{stats['std_w'] * factor:.{decimals}f} {unit}")
        self._stat_labels["min"].setText(f"{stats['min_w'] * factor:.{decimals}f} {unit}")
        self._stat_labels["max"].setText(f"{stats['max_w'] * factor:.{decimals}f} {unit}")

    def _on_unit_changed(self, _unit: str):
        """Re-render the last reading in the newly selected unit."""
        if self._last_stats is not None:
            self._update_display(self._last_stats)

    #  Slots 

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select output folder", self._dir_edit.text()
        )
        if folder:
            self._dir_edit.setText(folder)

    def _on_start_stop(self, checked: bool):
        if checked:
            #  START 
            self._reading_count = 0
            self._btn_start.setText("■  STOP")
            self._btn_record.setEnabled(True)
            self._led.set_state("busy")
            self._set_status("Reading …", S.TEXT_SUB)

            self._worker = ContinuousReadWorker(
                pm          = self._pm,
                wavelength  = self._wl_spin.value(),
                n_samples   = self._samples_spin.value(),
                averaging   = self._avg_spin.value(),
                interval_ms = self._interval_spin.value(),
            )
            self._worker.reading_ready.connect(self._on_reading)
            self._worker.error.connect(self._on_error)
            self._worker.start()

        else:
            # STOP 
            self._stop_worker()

    def _stop_worker(self):
        """Gracefully stop the reading loop."""
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(3000)   # wait up to 3 s for thread to finish

        self._btn_start.setText("▶  START")
        self._btn_start.setChecked(False)
        self._btn_record.setChecked(False)
        self._btn_record.setEnabled(False)
        self._recording = False
        self._refresh_led()
        self._rec_lbl.setText("")
        self._set_status(
            f"Stopped  ·  {self._reading_count} readings", S.TEXT_SUB
        )
        self.status_message.emit(
            f"[Power Meter]  Stopped after {self._reading_count} readings"
        )

    def _on_record_toggle(self, checked: bool):
        self._recording = checked
        if checked:
            self._reading_count = 0   # reset counter for this recording session
            self._rec_lbl.setStyleSheet(
                f"color:{S.RED}; font-size:11px; font-weight:700; background:transparent;"
            )
            self._rec_lbl.setText("⏺  RECORDING")
        else:
            self._rec_lbl.setStyleSheet(
                f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
            )
            self._rec_lbl.setText(
                f"Recording stopped  ·  {self._reading_count} files saved"
            )

    def _on_reading(self, stats: dict):
        self._reading_count += 1
        self._update_display(stats)
        self.status_message.emit(
            f"[Power Meter]  {stats['mean_mw']:.4f} mW  "
            f"(reading #{self._reading_count})"
        )

        if self._recording:
            try:
                path = _save_single_reading(
                    stats      = stats,
                    wavelength = self._wl_spin.value(),
                    output_dir = self._dir_edit.text().strip() or "data/power",
                    prefix     = self._prefix_edit.text().strip(),
                )
                self._rec_lbl.setText(
                    f"⏺ RECORDING  ·  {self._reading_count} files saved"
                )
                self._set_status(f"Saved -> {path.name}", S.GREEN)
            except Exception as exc:
                self._set_status(f"Save error: {exc}", S.RED)

    def _on_error(self, message: str):
        self._stop_worker()
        self._set_status(f"Error: {message}", S.RED)
        self.status_message.emit(f"[Power Meter]  ERROR: {message}")
