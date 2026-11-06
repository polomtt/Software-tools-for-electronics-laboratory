# gui/help_panel.py
"""
Help Panel — Motor Speed Calibration Reference

Features:
  - Auto-loads calibration file from project folder
  - Sheet selector dropdown (one sheet = one speed calibration)
  - Read-only table view with Pulses / measurements / MEAN
  - Open in Excel button
  - Reload after editing
  - Show Plot button - Pulses vs MEAN chart for the selected speed
"""

import os
import re
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QLineEdit, QFileDialog,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui  import QColor, QFont
from PyQt6.QtCore import Qt, pyqtSignal

import gui.style as S
from gui.widgets import SectionTitle, HLine, make_button

try:
    import pyqtgraph as pg
    PYQTGRAPH_OK = True
except ImportError:
    PYQTGRAPH_OK = False


#  Plot dialog 

class PlotDialog(QDialog):
    """Popup window showing Pulses vs MEAN for a given speed."""

    def __init__(self, speed_title: str, pulses: list, means: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Calibration Plot — {speed_title}")
        self.setMinimumSize(700, 450)
        self.setStyleSheet(f"background:{S.BG_MAIN}; color:{S.TEXT};")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        title = QLabel(f"Pulses  vs  µm/step  ·  {speed_title}")
        title.setStyleSheet(
            f"color:{S.AMBER}; font-size:15px; font-weight:700; background:transparent;"
        )
        layout.addWidget(title)

        if not PYQTGRAPH_OK:
            lbl = QLabel("pyqtgraph not available.\npip install pyqtgraph")
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setStyleSheet(f"color:{S.TEXT_DIM}; font-size:13px;")
            layout.addWidget(lbl)
            return

        pg.setConfigOptions(antialias=True,
                            background=S.BG_DEEP,
                            foreground=S.TEXT_SUB)
        plot = pg.PlotWidget()
        plot.setLabel("bottom", "Pulses",
                      **{"color": S.TEXT_SUB, "font-size": "12px"})
        plot.setLabel("left", "µm / step",
                      **{"color": S.TEXT_SUB, "font-size": "12px"})
        plot.showGrid(x=True, y=True, alpha=0.15)
        plot.getPlotItem().getAxis("bottom").setPen(
            pg.mkPen(color=S.BORDER_LT))
        plot.getPlotItem().getAxis("left").setPen(
            pg.mkPen(color=S.BORDER_LT))

        # Line + dots
        plot.plot(pulses, means,
                  pen=pg.mkPen(color=S.ACCENT, width=2),
                  symbol='o',
                  symbolSize=7,
                  symbolBrush=pg.mkBrush(S.ACCENT),
                  symbolPen=pg.mkPen(None),
                  name="MEAN")

        layout.addWidget(plot, stretch=1)

        btn_close = make_button("Close")
        btn_close.setFixedHeight(34)
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, alignment=Qt.AlignmentFlag.AlignRight)


#  Main panel 

class HelpPanel(QWidget):
    """
    Displays a calibration Excel file as a read-only table.
    Supports multiple sheets (one per speed calibration).
    Emits calibration_updated with parsed data whenever a file is loaded.
    """
    calibration_updated = pyqtSignal(dict)   # {speed_int: {'pulses': [], 'means': []}}

    def __init__(self, parent=None):
        super().__init__(parent)
        self._file_path  = ""
        self._sheet_data = {}   # {sheet_name: {'title': str, 'headers': [], 'rows': []}}
        self._build_ui()
        self._try_autoload()

    #  UI 

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 24, 24, 24)
        root.setSpacing(14)

        # Title
        title = QLabel("Help  —  Motor Speed Calibration")
        title.setStyleSheet(
            f"color:{S.TEXT}; font-size:20px; font-weight:700; background:transparent;"
        )
        subtitle = QLabel(
            "Load the calibration Excel file. Each sheet corresponds to one speed. "
            "Use 'Open in Excel' to edit, then 'Reload' to refresh."
        )
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet(
            f"color:{S.TEXT_SUB}; font-size:12px; background:transparent;"
        )
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(HLine())

        #  File selector 
        file_row = QHBoxLayout()
        file_row.setSpacing(8)

        lbl = QLabel("Calibration file:")
        lbl.setStyleSheet(f"color:{S.TEXT_SUB}; background:transparent;")
        lbl.setFixedWidth(120)

        self._path_edit = QLineEdit()
        self._path_edit.setPlaceholderText("Select the .xlsx calibration file ...")
        self._path_edit.setReadOnly(True)

        btn_browse = make_button("Browse ...")
        btn_browse.setFixedHeight(34)
        btn_browse.clicked.connect(self._on_browse)

        file_row.addWidget(lbl)
        file_row.addWidget(self._path_edit, stretch=1)
        file_row.addWidget(btn_browse)
        root.addLayout(file_row)

        #  Speed selector + action buttons 
        ctrl_row = QHBoxLayout()
        ctrl_row.setSpacing(10)

        speed_lbl = QLabel("Speed:")
        speed_lbl.setStyleSheet(f"color:{S.TEXT_SUB}; background:transparent;")
        self._speed_combo = QComboBox()
        self._speed_combo.setFixedWidth(180)
        self._speed_combo.setStyleSheet(f"""
            QComboBox {{
                background:{S.BG_WIDGET}; color:{S.AMBER};
                border:1px solid {S.BORDER}; border-radius:4px;
                padding:6px 10px; font-size:13px; font-weight:700;
            }}
            QComboBox:focus {{ border-color:{S.ACCENT}; }}
            QComboBox::drop-down {{
                border:none; background:{S.BG_HOVER};
                width:24px; border-radius:0 4px 4px 0;
            }}
            QComboBox QAbstractItemView {{
                background:{S.BG_PANEL}; color:{S.TEXT};
                border:1px solid {S.BORDER_LT};
                selection-background-color:{S.BG_HOVER};
                padding:4px;
            }}
        """)
        self._speed_combo.currentIndexChanged.connect(self._on_speed_changed)

        self._btn_open = make_button("Open in Excel")
        self._btn_open.setFixedHeight(34)
        self._btn_open.setEnabled(False)
        self._btn_open.clicked.connect(self._on_open_excel)

        self._btn_reload = make_button("↻  Reload", role="success")
        self._btn_reload.setFixedHeight(34)
        self._btn_reload.setEnabled(False)
        self._btn_reload.clicked.connect(self._on_reload)

        self._btn_plot = make_button("📈  Show Plot", role="default")
        self._btn_plot.setFixedHeight(34)
        self._btn_plot.setEnabled(False)
        self._btn_plot.setToolTip("Plot Pulses vs MEAN for this speed")
        self._btn_plot.clicked.connect(self._on_show_plot)

        ctrl_row.addWidget(speed_lbl)
        ctrl_row.addWidget(self._speed_combo)
        ctrl_row.addSpacing(8)
        ctrl_row.addWidget(self._btn_open)
        ctrl_row.addWidget(self._btn_reload)
        ctrl_row.addWidget(self._btn_plot)
        ctrl_row.addStretch()
        root.addLayout(ctrl_row)

        root.addWidget(HLine())

        #  Table 
        self._table = QTableWidget()
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        self._table.setStyleSheet(f"""
            QTableWidget {{
                background-color: {S.BG_PANEL};
                color: {S.TEXT};
                border: 1px solid {S.BORDER};
                gridline-color: {S.BORDER};
                alternate-background-color: {S.BG_WIDGET};
                font-size: 13px;
            }}
            QTableWidget QHeaderView::section {{
                background-color: {S.BG_WIDGET};
                color: {S.CYAN};
                border: none;
                border-bottom: 2px solid {S.ACCENT};
                border-right: 1px solid {S.BORDER};
                padding: 8px 12px;
                font-size: 12px;
                font-weight: 700;
                letter-spacing: 0.8px;
            }}
            QTableWidget::item {{ padding: 6px 12px; }}
            QTableWidget::item:selected {{
                background-color: {S.BG_HOVER}; color: {S.TEXT};
            }}
        """)
        self._table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._table.verticalHeader().setVisible(False)
        root.addWidget(self._table, stretch=1)

        # Status
        self._status_lbl = QLabel("No file loaded.")
        self._status_lbl.setStyleSheet(
            f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        root.addWidget(self._status_lbl)

    #  Auto-load 

    def _try_autoload(self):
        """Load calibration file automatically if found in the project folder."""
        try:
            from utils.config import CALIBRATION_FILE
            path = Path(CALIBRATION_FILE)
            if path.exists():
                self._file_path = str(path.resolve())
                self._path_edit.setText(self._file_path)
                self._load_excel(self._file_path)
        except (ImportError, AttributeError):
            pass

    #  Excel loading 

    def _load_excel(self, path: str):
        """Read all sheets from the xlsx and populate the speed combo."""
        try:
            from openpyxl import load_workbook
        except ImportError:
            self._set_status("openpyxl not installed — run: pip install openpyxl", S.RED)
            return

        try:
            wb = load_workbook(path, read_only=True, data_only=True)
            self._sheet_data.clear()

            for sheet_name in wb.sheetnames:
                ws = wb[sheet_name]
                rows = [r for r in ws.iter_rows(values_only=True)
                        if any(c is not None for c in r)]

                # Extract speed title from first row
                speed_title = sheet_name
                for cell in rows[0] if rows else []:
                    if isinstance(cell, str) and cell.strip():
                        speed_title = cell.strip()
                        break

                # Find header row
                header_idx = 0
                for i, row in enumerate(rows):
                    non_none = sum(1 for c in row if c is not None)
                    if non_none >= 3 and isinstance(row[0], str):
                        header_idx = i
                        break

                headers   = [str(c) if c is not None else ""
                             for c in rows[header_idx]]
                data_rows = rows[header_idx + 1:]

                # Trim trailing empty columns
                max_col = max(
                    (i for i, h in enumerate(headers) if h.strip()),
                    default=len(headers) - 1
                ) + 1
                headers   = headers[:max_col]
                data_rows = [r[:max_col] for r in data_rows]

                self._sheet_data[sheet_name] = {
                    "title"  : speed_title,
                    "headers": headers,
                    "rows"   : data_rows,
                }

            wb.close()

            # Populate speed combo
            self._speed_combo.blockSignals(True)
            self._speed_combo.clear()
            for sheet_name, data in self._sheet_data.items():
                self._speed_combo.addItem(data["title"], userData=sheet_name)
            self._speed_combo.blockSignals(False)

            self._btn_open.setEnabled(True)
            self._btn_reload.setEnabled(True)
            self._btn_plot.setEnabled(True)

            # Show first sheet
            self._speed_combo.setCurrentIndex(0)
            self._show_sheet(list(self._sheet_data.keys())[0])

            n_sheets = len(self._sheet_data)
            self._set_status(
                f"Loaded  {n_sheets} calibration(s)  ·  {Path(path).name}", S.GREEN
            )

            # Emit calibration data for other panels (e.g. ScanPanel)
            self.calibration_updated.emit(self._build_calibration_dict())

        except Exception as exc:
            self._set_status(f"Error loading file: {exc}", S.RED)

    def _build_calibration_dict(self) -> dict:
        """
        Convert _sheet_data into the format used by ScanPanel:
        {speed_int: {'pulses': [...], 'means': [...]}}
        Speed number is extracted from the title string (e.g. 'Speed 600' → 600).
        """
        cal = {}
        for sheet_name, data in self._sheet_data.items():
            # Extract speed number from title
            m = re.search(r'\d+', data["title"])
            if not m:
                continue
            speed_num = int(m.group())

            headers   = [h.strip().upper() for h in data["headers"]]
            mean_col  = next((i for i, h in enumerate(headers)
                              if h == "MEAN"), None)
            if mean_col is None:
                continue

            pulses, means = [], []
            for row in data["rows"]:
                try:
                    pulses.append(float(row[0]))
                    means.append(float(row[mean_col]))
                except (TypeError, ValueError):
                    continue

            if pulses:
                cal[speed_num] = {"pulses": pulses, "means": means}
        return cal

    def _show_sheet(self, sheet_name: str):
        """Populate the table with data from the selected sheet."""
        data = self._sheet_data.get(sheet_name)
        if not data:
            return

        headers   = data["headers"]
        data_rows = data["rows"]

        self._table.clear()
        self._table.setColumnCount(len(headers))
        self._table.setRowCount(len(data_rows))
        self._table.setHorizontalHeaderLabels(headers)

        for r, row in enumerate(data_rows):
            for c, val in enumerate(row):
                text = "" if val is None else str(val)
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)

                if headers[c].strip().upper() == "MEAN" and text:
                    item.setForeground(QColor(S.AMBER))
                    f = QFont(); f.setBold(True)
                    item.setFont(f)
                elif c == 0 and text:
                    item.setForeground(QColor(S.CYAN))

                self._table.setItem(r, c, item)

    #  Helpers 

    def _set_status(self, text: str, color: str = None):
        self._status_lbl.setStyleSheet(
            f"color:{color or S.TEXT_DIM}; font-size:11px; background:transparent;"
        )
        self._status_lbl.setText(text)

    def _current_sheet_name(self) -> str:
        return self._speed_combo.currentData() or ""

    #  Slots 

    def _on_browse(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select calibration file", str(Path.home()),
            "Excel files (*.xlsx *.xlsm *.xls);;All files (*.*)",
        )
        if path:
            self._file_path = path
            self._path_edit.setText(path)
            self._load_excel(path)

    def _on_speed_changed(self, _idx: int):
        self._show_sheet(self._current_sheet_name())

    def _on_open_excel(self):
        if self._file_path and Path(self._file_path).exists():
            os.startfile(self._file_path)
        else:
            self._set_status("File not found.", S.RED)

    def _on_reload(self):
        if self._file_path:
            self._load_excel(self._file_path)
        else:
            self._set_status("No file selected.", S.RED)

    def _on_show_plot(self):
        sheet_name = self._current_sheet_name()
        data = self._sheet_data.get(sheet_name)
        if not data:
            return

        headers   = data["headers"]
        data_rows = data["rows"]

        # Find Pulses column (index 0) and MEAN column
        mean_col = next(
            (i for i, h in enumerate(headers)
             if h.strip().upper() == "MEAN"),
            None
        )
        if mean_col is None:
            self._set_status("MEAN column not found in this sheet.", S.RED)
            return

        pulses, means = [], []
        for row in data_rows:
            try:
                p = float(row[0])
                m = float(row[mean_col])
                pulses.append(p)
                means.append(m)
            except (TypeError, ValueError):
                continue

        if not pulses:
            self._set_status("No numeric data to plot.", S.RED)
            return

        dlg = PlotDialog(data["title"], pulses, means, parent=self)
        dlg.exec()
