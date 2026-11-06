# gui/scope_panel.py
"""
Oscilloscope Panel — Tektronix MDO3102

Features:
  - Continuous acquisition every N seconds (START / STOP)
  - RECORD toggle: saves one CSV file per acquisition
  - Channel selection: CH1 / CH2 shows only that curve; Both shows both
  - Live waveform plot + statistics table
"""

import csv
from pathlib import Path
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QSplitter,
    QLabel, QPushButton, QSpinBox, QGroupBox, QButtonGroup,
    QRadioButton, QFileDialog, QTableWidget, QTableWidgetItem,
    QHeaderView, QLineEdit,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui  import QColor

import numpy as np
import gui.style as S
from gui.widgets import StatusLED, SectionTitle, HLine, make_button

try:
    import pyqtgraph as pg
    PYQTGRAPH_OK = True
except ImportError:
    PYQTGRAPH_OK = False


#  Continuous acquisition worker 

class ContinuousAcquireWorker(QThread):
    """
    Acquires waveform(s) in a loop until stop() is called.
    Emits one signal per acquisition cycle.
    """
    data_ready = pyqtSignal(dict)   # {'CH1': (t, v), 'CH2': (t, v)}
    error      = pyqtSignal(str)

    def __init__(self, scope, channel, interval_s: float):
        super().__init__()
        self._scope      = scope
        self._channel    = channel    # 1 | 2 | "both"
        self._interval_s = max(interval_s, 0.5)
        self._running    = False

    def stop(self):
        self._running = False

    def run(self):
        self._running = True
        try:
            if not self._scope.is_connected:
                self._scope.connect()
        except Exception as exc:
            self.error.emit(str(exc))
            return

        while self._running:
            try:
                channels = [1, 2] if self._channel == "both" else [self._channel]
                result   = {}
                for ch in channels:
                    t, v = self._scope.read_waveform(ch)
                    result[f"CH{ch}"] = (t, v)
                self.data_ready.emit(result)
            except Exception as exc:
                self.error.emit(str(exc))
                break

            # Interruptible sleep - checks stop flag every 100 ms
            elapsed = 0.0
            while self._running and elapsed < self._interval_s:
                self.msleep(100)
                elapsed += 0.1


#  CSV save helper 

def _save_waveform_csv(ch_key: str, t: np.ndarray, v: np.ndarray,
                        output_dir: str, prefix: str) -> Path:
    """Save one waveform to a uniquely named CSV file."""
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ts     = datetime.now()
    ts_str = ts.strftime("%Y%m%d_%H%M%S_") + f"{ts.microsecond // 1000:03d}"
    base   = f"{prefix}_{ch_key}_{ts_str}" if prefix else f"waveform_{ch_key}_{ts_str}"
    path   = out_dir / f"{base}.csv"

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["time_s", "voltage_V"])
        for ti, vi in zip(t, v):
            writer.writerow([f"{ti:.9e}", f"{vi:.6e}"])
    return path


#  Plot setup 

def _make_plot():
    if not PYQTGRAPH_OK:
        lbl = QLabel(
            "pyqtgraph not installed.\n\npip install pyqtgraph\n\n"
            "Acquire / Save still work without the plot."
        )
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:13px; background:{S.BG_DEEP};"
            f"border:1px solid {S.BORDER}; border-radius:4px;"
        )
        return lbl, None, None

    pg.setConfigOptions(antialias=True, background=S.BG_DEEP, foreground=S.TEXT_SUB)
    plot = pg.PlotWidget()
    plot.setLabel("bottom", "Time", units="s",
                  **{"color": S.TEXT_SUB, "font-size": "11px"})
    plot.setLabel("left", "Voltage", units="V",
                  **{"color": S.TEXT_SUB, "font-size": "11px"})
    plot.showGrid(x=True, y=True, alpha=0.15)
    plot.getPlotItem().getAxis("bottom").setPen(pg.mkPen(color=S.BORDER_LT))
    plot.getPlotItem().getAxis("left"  ).setPen(pg.mkPen(color=S.BORDER_LT))
    plot.setMinimumHeight(260)

    curve_ch1 = plot.plot(pen=pg.mkPen(color=S.ACCENT, width=1.5), name="CH1")
    curve_ch2 = plot.plot(pen=pg.mkPen(color=S.CYAN,   width=1.5), name="CH2")

    legend = plot.addLegend(offset=(10, 10))
    legend.setLabelTextColor(S.TEXT_SUB)

    return plot, curve_ch1, curve_ch2


#  Panel 

class ScopePanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, scope, parent=None):
        super().__init__(parent)
        self._scope          = scope
        self._worker         = None
        self._recording      = False
        self._acq_count      = 0
        self._last_data      = {}

        self._build_ui()
        self._refresh_led()

    #  UI 

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        #  Left sidebar 
        # Structure: QWidget (fixed width)
        #   --> scroll area  <- all settings (scrollable)
        #   --> buttons area <- START / RECORD always visible at bottom

        # Scrollable settings content 
        from PyQt6.QtWidgets import QScrollArea

        settings_widget = QWidget()
        settings_widget.setStyleSheet("background: transparent;")
        sidebar = QVBoxLayout(settings_widget)
        sidebar.setSpacing(12)
        sidebar.setContentsMargins(0, 0, 8, 0)

        title = QLabel("Oscilloscope")
        title.setStyleSheet(
            f"color:{S.TEXT}; font-size:20px; font-weight:700; background:transparent;"
        )
        subtitle = QLabel("Tektronix MDO3102  ·  SCPI/USB-TMC")
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

        # Channel selection
        ch_box = QGroupBox("Channel")
        ch_layout = QVBoxLayout(ch_box)
        ch_layout.setSpacing(8)
        ch_layout.setContentsMargins(10, 14, 10, 14)
        self._ch_group = QButtonGroup(self)

        for label, value in [("CH1 only", 1), ("CH2 only", 2), ("Both", "both")]:
            rb = QRadioButton(label)
            rb.setProperty("chValue", value)
            rb.setStyleSheet(f"""
                QRadioButton {{
                    color:{S.TEXT}; font-size:13px;
                    background:transparent; spacing:8px;
                }}
                QRadioButton::indicator {{
                    width:14px; height:14px; border-radius:7px;
                    border:2px solid {S.BORDER_LT};
                    background:{S.BG_WIDGET};
                }}
                QRadioButton::indicator:checked {{
                    background:{S.ACCENT}; border-color:{S.ACCENT};
                }}
            """)
            if value == 1:
                rb.setChecked(True)
            self._ch_group.addButton(rb)
            ch_layout.addWidget(rb)

        self._ch_group.buttonClicked.connect(self._on_channel_changed)
        sidebar.addWidget(ch_box)

        # Acquisition interval
        acq_box = QGroupBox("Acquisition Settings")
        ag = QGridLayout(acq_box)
        ag.setSpacing(10)
        ag.setContentsMargins(10, 14, 10, 14)
        ag.addWidget(QLabel("Interval (s)"), 0, 0)
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(1, 3600)
        self._interval_spin.setValue(2)
        self._interval_spin.setToolTip("Seconds between acquisitions")
        ag.addWidget(self._interval_spin, 0, 1)
        sidebar.addWidget(acq_box)

        # Save location
        save_box = QGroupBox("Save Location  (for RECORD)")
        sv = QVBoxLayout(save_box)
        sv.setSpacing(10)
        sv.setContentsMargins(10, 16, 10, 16)
        self._dir_edit = QLineEdit("data/waveforms")
        self._dir_edit.setPlaceholderText("Output folder")
        btn_browse = make_button("Browse …")
        btn_browse.setMinimumHeight(34)
        btn_browse.clicked.connect(self._on_browse)
        sv.addWidget(self._dir_edit)
        sv.addWidget(btn_browse)
        sv.addSpacing(6)
        lbl_prefix = QLabel("Filename prefix (optional):")
        lbl_prefix.setStyleSheet("background:transparent;")
        sv.addWidget(lbl_prefix)
        self._prefix_edit = QLineEdit()
        self._prefix_edit.setPlaceholderText("e.g.  run_001")
        sv.addWidget(self._prefix_edit)
        sidebar.addWidget(save_box)

        sidebar.addStretch()

        # Wrap settings in a scroll area
        scroll = QScrollArea()
        scroll.setWidget(settings_widget)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(scroll.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setStyleSheet("background: transparent;")

        #  Fixed bottom: buttons 
        self._btn_start = make_button("▶  START", role="primary")
        
        self._btn_start.setStyleSheet(f"""
    QPushButton {{
        background-color: {S.ACCENT};
        color: #07090E;
        border: none;
        border-radius: 4px;
        font-size: 13px;
        font-weight: 700;
        letter-spacing: 0.5px;
        padding: 8px 22px;
    }}
    QPushButton:hover  {{ background-color: #FF855A; }}
    QPushButton:pressed {{ background-color: #D94E18; }}
""")
        
        self._btn_start.setMinimumHeight(44)
        self._btn_start.setCheckable(True)
        self._btn_start.setToolTip("Start / stop continuous acquisition")
        self._btn_start.clicked.connect(self._on_start_stop)

        self._btn_record = make_button("⏺  RECORD", role="success")
        self._btn_record.setMinimumHeight(40)
        self._btn_record.setCheckable(True)
        self._btn_record.setEnabled(False)
        self._btn_record.setToolTip(
            "While active: saves one CSV per acquisition to the selected folder"
        )
        self._btn_record.clicked.connect(self._on_record_toggle)

        self._status_lbl = QLabel("")
        self._status_lbl.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        self._status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        btn_area = QWidget()
        btn_area.setStyleSheet("background: transparent;")
        btn_layout = QVBoxLayout(btn_area)
        btn_layout.setContentsMargins(0, 8, 8, 0)
        btn_layout.setSpacing(8)
        btn_layout.addWidget(HLine())
        btn_layout.addWidget(self._btn_start)
        btn_layout.addWidget(self._btn_record)
        btn_layout.addWidget(self._status_lbl)

        #  Assemble sidebar container 
        sidebar_widget = QWidget()
        sidebar_widget.setFixedWidth(320)
        sidebar_outer = QVBoxLayout(sidebar_widget)
        sidebar_outer.setContentsMargins(0, 0, 0, 0)
        sidebar_outer.setSpacing(0)
        sidebar_outer.addWidget(scroll, stretch=1)
        sidebar_outer.addWidget(btn_area)

        #  Right side  plot + stats 
        right = QVBoxLayout()
        right.setSpacing(10)

        self._plot_widget, self._curve_ch1, self._curve_ch2 = _make_plot()
        right.addWidget(self._plot_widget, stretch=3)

        # Recording info label
        self._rec_lbl = QLabel("")
        self._rec_lbl.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        self._rec_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        right.addWidget(self._rec_lbl)

        # Stats table
        self._stats_table = QTableWidget(5, 3)
        self._stats_table.setHorizontalHeaderLabels(["Stat", "CH1", "CH2"])
        self._stats_table.verticalHeader().setVisible(False)
        self._stats_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._stats_table.setFixedHeight(168)
        for row, stat in enumerate(["Vmin", "Vmax", "Vpp", "Vmean", "Vrms"]):
            self._stats_table.setItem(row, 0, self._cell(stat, S.TEXT_SUB))
            self._stats_table.setItem(row, 1, self._cell("---"))
            self._stats_table.setItem(row, 2, self._cell("---"))

        right.addWidget(SectionTitle("Waveform Statistics"))
        right.addWidget(self._stats_table)

        right_widget = QWidget()
        right_widget.setLayout(right)

        root.addWidget(sidebar_widget)
        root.addWidget(right_widget, stretch=1)

    #  Helpers 

    @staticmethod
    def _cell(text: str, color: str = None) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        if color:
            item.setForeground(QColor(color))
        return item

    def _selected_channel(self):
        for btn in self._ch_group.buttons():
            if btn.isChecked():
                return btn.property("chValue")
        return 1

    def _refresh_led(self):
        connected = self._scope.is_connected
        self._led.set_state("connected" if connected else "disconnected")
        text  = "Connected"  if connected else "Disconnected"
        color = S.GREEN      if connected else S.TEXT_DIM
        self._conn_label.setText(text)
        self._conn_label.setStyleSheet(
            f"color:{color}; font-size:12px; background:transparent;"
        )

    def _set_status(self, text: str, color: str = None):
        self._status_lbl.setStyleSheet(
            f"color:{color or S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        self._status_lbl.setText(text)

    def _update_curves(self, data: dict):
        """
        Update plot curves and enforce per-channel visibility:
        - CH1 only  → CH1 curve visible, CH2 hidden
        - CH2 only  → CH2 visible, CH1 hidden
        - Both      → both visible
        """
        if not PYQTGRAPH_OK:
            return

        ch = self._selected_channel()

        # Update data for received channels
        for ch_key, (t, v) in data.items():
            if ch_key == "CH1" and self._curve_ch1:
                self._curve_ch1.setData(t, v)
            elif ch_key == "CH2" and self._curve_ch2:
                self._curve_ch2.setData(t, v)

        # Enforce visibility
        show_ch1 = (ch == 1 or ch == "both")
        show_ch2 = (ch == 2 or ch == "both")
        if self._curve_ch1:
            self._curve_ch1.setVisible(show_ch1)
        if self._curve_ch2:
            self._curve_ch2.setVisible(show_ch2)

    def _update_stats(self, data: dict):
        """Recompute stats for each channel in data; clear columns not present."""
        for col, ch_key in [(1, "CH1"), (2, "CH2")]:
            if ch_key in data:
                _t, v = data[ch_key]
                vpp  = float(v.max() - v.min())
                vrms = float(np.sqrt(np.mean(v ** 2)))
                vals = [
                    f"{v.min():.4f} V",
                    f"{v.max():.4f} V",
                    f"{vpp:.4f} V",
                    f"{v.mean():.4f} V",
                    f"{vrms:.4f} V",
                ]
                accent = S.ACCENT if ch_key == "CH1" else S.CYAN
                for row, val in enumerate(vals):
                    self._stats_table.setItem(row, col, self._cell(val, accent))
            else:
                for row in range(5):
                    self._stats_table.setItem(row, col, self._cell("---"))

    #  Slots 

    def _on_browse(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select output folder", self._dir_edit.text()
        )
        if folder:
            self._dir_edit.setText(folder)

    def _on_channel_changed(self, _btn):
        """When the user switches channel while running, update curve visibility."""
        self._update_curves(self._last_data)

    def _on_start_stop(self, checked: bool):
        if checked:
            self._acq_count = 0
            self._btn_start.setText("■  STOP")
            self._btn_record.setEnabled(True)
            self._led.set_state("busy")
            self._set_status("Acquiring …", S.TEXT_SUB)

            self._worker = ContinuousAcquireWorker(
                scope      = self._scope,
                channel    = self._selected_channel(),
                interval_s = self._interval_spin.value(),
            )
            self._worker.data_ready.connect(self._on_data_ready)
            self._worker.error.connect(self._on_error)
            self._worker.start()
        else:
            self._stop_worker()

    def _stop_worker(self):
        if self._worker is not None:
            self._worker.stop()
            self._worker.wait(5000)

        self._btn_start.setText("▶  START")
        self._btn_start.setChecked(False)
        self._btn_record.setChecked(False)
        self._btn_record.setEnabled(False)
        self._recording = False
        self._refresh_led()
        self._rec_lbl.setText("")
        self._set_status(
            f"Stopped  ·  {self._acq_count} acquisitions", S.TEXT_SUB
        )
        self.status_message.emit(
            f"[Oscilloscope]  Stopped after {self._acq_count} acquisitions"
        )

    def _on_record_toggle(self, checked: bool):
        self._recording = checked
        if checked:
            self._acq_count = 0
            self._rec_lbl.setStyleSheet(
                f"color:{S.RED}; font-size:11px; font-weight:700; background:transparent;"
            )
            self._rec_lbl.setText("⏺  RECORDING")
        else:
            self._rec_lbl.setStyleSheet(
                f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
            )
            self._rec_lbl.setText(
                f"Recording stopped  ·  {self._acq_count} files saved"
            )

    def _on_data_ready(self, data: dict):
        self._last_data = data
        self._acq_count += 1

        self._update_curves(data)
        self._update_stats(data)
        self._refresh_led()

        chs = ", ".join(data.keys())
        self.status_message.emit(
            f"[Oscilloscope]  Acquired {chs}  (#{self._acq_count})"
        )

        if self._recording:
            out_dir = self._dir_edit.text().strip() or "data/waveforms"
            prefix  = self._prefix_edit.text().strip()
            saved   = []
            try:
                for ch_key, (t, v) in data.items():
                    path = _save_waveform_csv(ch_key, t, v, out_dir, prefix)
                    saved.append(path.name)
                self._rec_lbl.setText(
                    f"⏺  RECORDING  ·  acq #{self._acq_count}  ·  "
                    f"{', '.join(saved)}"
                )
                self._set_status(f"Saved: {', '.join(saved)}", S.GREEN)
            except Exception as exc:
                self._set_status(f"Save error: {exc}", S.RED)
        else:
            self._set_status(f"Acquisition #{self._acq_count}", S.TEXT_SUB)

    def _on_error(self, message: str):
        self._stop_worker()
        self._set_status(f"Error: {message}", S.RED)
        self.status_message.emit(f"[Oscilloscope]  ERROR: {message}")
