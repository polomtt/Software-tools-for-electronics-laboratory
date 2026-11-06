# gui/main_window.py
"""
Main application window.
Hosts the three instrument tabs and a status bar with connection indicators.
"""

from PyQt6.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar,
    QLabel, QWidget, QHBoxLayout, QPushButton,
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal
from PyQt6.QtGui  import QFont

import gui.style as S
from gui.widgets     import StatusLED
from gui.motor_panel        import MotorPanel
from gui.scope_panel        import ScopePanel
from gui.power_panel        import PowerPanel
from gui.scan_panel         import ScanPanel
from gui.loop_scan_panel    import LoopScanPanel
from gui.photo_current_panel import PhotoCurrentPanel
from gui.help_panel         import HelpPanel


#  Reconnect worker

class ReconnectWorker(QThread):
    """Disconnects and reconnects all instruments off the UI thread."""
    finished = pyqtSignal(dict)   # {name: True/False}
    progress = pyqtSignal(str)

    def __init__(self, motors: dict, scope, pm):
        super().__init__()
        self._motors = motors
        self._scope  = scope
        self._pm     = pm

    def run(self):
        results = {}

        # Motors
        for axis, motor in self._motors.items():
            self.progress.emit(f"Reconnecting motor {axis.upper()} …")
            try:
                if motor.is_connected:
                    motor.disconnect()
                motor.connect()
                results[f"Motor {axis.upper()}"] = True
            except Exception as exc:
                results[f"Motor {axis.upper()}"] = False
                self.progress.emit(f"Motor {axis.upper()} failed: {exc}")

        # Oscilloscope
        self.progress.emit("Reconnecting oscilloscope …")
        try:
            if self._scope.is_connected:
                self._scope.disconnect()
            self._scope.connect()
            results["Oscilloscope"] = True
        except Exception as exc:
            results["Oscilloscope"] = False
            self.progress.emit(f"Oscilloscope failed: {exc}")

        # Power meter
        self.progress.emit("Reconnecting power meter …")
        try:
            if self._pm.is_connected:
                self._pm.disconnect()
            self._pm.connect()
            results["Power Meter"] = True
        except Exception as exc:
            results["Power Meter"] = False
            self.progress.emit(f"Power Meter failed: {exc}")

        self.finished.emit(results)


class MainWindow(QMainWindow):
    """
    Top-level window for the Lab Control GUI.

    Parameters
    ----------
    motors : dict[str, Motor]
        Axis-label → Motor instance mapping.
    scope : Oscilloscope
        Connected (or not-yet-connected) oscilloscope instance.
    pm : PowerMeter
        Connected (or not-yet-connected) power meter instance.
    """

    def __init__(self, motors: dict, scope, pm, parent=None):
        super().__init__(parent)
        self._motors  = motors
        self._scope   = scope
        self._pm      = pm
        self._rw      = None   # ReconnectWorker kept alive

        self.setWindowTitle("Lab Control System")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)

        self._build_ui()

    # UI Construction

    def _build_ui(self):
        #  Central tab widget 
        tabs = QTabWidget()
        tabs.setDocumentMode(True)

        motor_panel = MotorPanel(self._motors)
        motor_panel.status_message.connect(self._set_status)
        tabs.addTab(motor_panel, "  Motors  ")

        scope_panel = ScopePanel(self._scope)
        scope_panel.status_message.connect(self._set_status)
        tabs.addTab(scope_panel, "  Oscilloscope  ")

        power_panel = PowerPanel(self._pm)
        power_panel.status_message.connect(self._set_status)
        tabs.addTab(power_panel, "  Power Meter  ")

        scan_panel = ScanPanel(self._motors, self._scope, self._pm)
        scan_panel.status_message.connect(self._set_status)
        tabs.addTab(scan_panel, "  Scan  ")

        loop_scan_panel = LoopScanPanel(self._motors, self._scope, self._pm)
        loop_scan_panel.status_message.connect(self._set_status)
        tabs.addTab(loop_scan_panel, "  Loop Scan  ")

        photo_panel = PhotoCurrentPanel(self._motors, self._scope)
        photo_panel.status_message.connect(self._set_status)
        tabs.addTab(photo_panel, "  Photo Current  ")

        help_panel = HelpPanel()
        tabs.addTab(help_panel, "  Help  ")

        help_panel.calibration_updated.connect(scan_panel.update_calibration)
        help_panel.calibration_updated.connect(loop_scan_panel.update_calibration)
        help_panel.calibration_updated.connect(photo_panel.update_calibration)

        self.setCentralWidget(tabs)

        #  Status bar
        status_bar = QStatusBar()
        self.setStatusBar(status_bar)

        # Message label (left)
        self._status_msg = QLabel("Ready")
        self._status_msg.setStyleSheet(
            f"color:{S.TEXT_SUB}; background:transparent; padding:0 4px;"
        )
        status_bar.addWidget(self._status_msg, stretch=1)

        # Right side: indicators + Reconnect All button
        right_widget = QWidget()
        right_widget.setStyleSheet("background:transparent;")
        right_layout = QHBoxLayout(right_widget)
        right_layout.setContentsMargins(0, 0, 8, 0)
        right_layout.setSpacing(14)

        # Instrument LEDs
        self._leds = {}

        def _indicator(key: str, label: str, connected: bool):
            row = QHBoxLayout()
            row.setSpacing(5)
            led = StatusLED("connected" if connected else "disconnected")
            lbl = QLabel(label)
            lbl.setStyleSheet(
                f"color:{S.TEXT_DIM}; font-size:11px; background:transparent;"
            )
            row.addWidget(led)
            row.addWidget(lbl)
            w = QWidget()
            w.setStyleSheet("background:transparent;")
            w.setLayout(row)
            self._leds[key] = led
            return w

        n_motors = len(self._motors)
        right_layout.addWidget(_indicator(
            "motors", f"Motors ({n_motors})", n_motors > 0
        ))
        right_layout.addWidget(_indicator(
            "scope", "Oscilloscope", self._scope.is_connected
        ))
        right_layout.addWidget(_indicator(
            "pm", "Power Meter", self._pm.is_connected
        ))

        # Reconnect All button
        self._btn_reconnect = QPushButton("⟳  Reconnect All")
        self._btn_reconnect.setFixedHeight(24)
        self._btn_reconnect.setStyleSheet(f"""
            QPushButton {{
                background:{S.BG_WIDGET}; color:{S.CYAN};
                border:1px solid {S.CYAN}; border-radius:4px;
                font-size:11px; font-weight:600;
                padding:2px 12px;
            }}
            QPushButton:hover  {{ background:#0A1A2A; }}
            QPushButton:pressed {{ background:{S.BG_DEEP}; }}
            QPushButton:disabled {{
                color:{S.TEXT_DIM}; border-color:{S.BORDER};
            }}
        """)
        self._btn_reconnect.clicked.connect(self._on_reconnect_all)
        right_layout.addWidget(self._btn_reconnect)

        status_bar.addPermanentWidget(right_widget)

    #  Slots 

    def _set_status(self, message: str):
        self._status_msg.setText(message)

    def _on_reconnect_all(self):
        self._btn_reconnect.setEnabled(False)
        self._btn_reconnect.setText("Reconnecting …")
        self._set_status("Reconnecting all instruments …")

        # Set all LEDs to busy
        for led in self._leds.values():
            led.set_state("busy")

        self._rw = ReconnectWorker(self._motors, self._scope, self._pm)
        self._rw.progress.connect(self._set_status)
        self._rw.finished.connect(self._on_reconnect_done)
        self._rw.start()

    def _on_reconnect_done(self, results: dict):
        # Update LEDs
        for axis in self._motors:
            led = self._leds.get("motors")
            if led:
                all_ok = all(
                    self._motors[a].is_connected for a in self._motors
                )
                led.set_state("connected" if all_ok else "disconnected")

        scope_ok = self._scope.is_connected
        self._leds["scope"].set_state(
            "connected" if scope_ok else "disconnected"
        )
        pm_ok = self._pm.is_connected
        self._leds["pm"].set_state(
            "connected" if pm_ok else "disconnected"
        )

        # Summary message
        ok  = [k for k, v in results.items() if v]
        err = [k for k, v in results.items() if not v]
        if err:
            self._set_status(
                f"Reconnect done — OK: {', '.join(ok)}  "
                f"FAILED: {', '.join(err)}"
            )
        else:
            self._set_status(
                f"Reconnect done — all {len(ok)} instrument(s) connected ✓"
            )

        self._btn_reconnect.setText("⟳  Reconnect All")
        self._btn_reconnect.setEnabled(True)
