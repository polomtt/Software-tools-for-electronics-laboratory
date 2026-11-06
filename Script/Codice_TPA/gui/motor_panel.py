# gui/motor_panel.py
"""
Motor Control Panel — Opto Sigma SRC-101
Three axis cards (X, Y, Z) with position display, steps, move controls, and homing.
"""

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QSpinBox, QDoubleSpinBox, QGroupBox, QFrame,
)
from PyQt6.QtCore    import Qt, QThread, pyqtSignal

import gui.style  as S
from   gui.widgets import StatusLED, SectionTitle, HLine, DigitalDisplay, make_button


#  Workers 

class MoveWorker(QThread):
    """Executes N steps off the UI thread."""
    finished  = pyqtSignal(str)        # final position as string
    step_done = pyqtSignal(int, int)   # (current_step, total_steps)
    error     = pyqtSignal(str)

    def __init__(self, motor, pulses: int, speed: int, steps: int = 1, delay_s: float = 0.0):
        super().__init__()
        self._motor   = motor
        self._pulses  = pulses
        self._speed   = speed
        self._steps   = max(1, steps)
        self._delay_s = delay_s

    def run(self):
        try:
            for i in range(self._steps):
                self._motor.move(pulses=self._pulses, speed=self._speed, wait=True)
                self.step_done.emit(i + 1, self._steps)
                if self._delay_s > 0 and i < self._steps - 1:
                    self.msleep(int(self._delay_s * 1000))

            try:
                pos = self._motor.get_position()
                self.finished.emit(str(pos))
            except Exception:
                self.finished.emit("?")

        except Exception as exc:
            self.error.emit(str(exc))


class HomeWorker(QThread):
    """Sends the home command off the UI thread."""
    finished = pyqtSignal()    # no position # just signals completion
    error    = pyqtSignal(str)

    def __init__(self, motor):
        super().__init__()
        self._motor = motor

    def run(self):
        try:
            self._motor.home()
            self.finished.emit()
        except Exception as exc:
            self.error.emit(str(exc))


# Single axis card 

class AxisCard(QFrame):
    """A self-contained card for one motor axis."""

    status_changed = pyqtSignal(str, str)   # (axis_label, message)

    def __init__(self, axis: str, motor, parent=None):
        super().__init__(parent)
        self._axis      = axis.upper()
        self._motor     = motor
        self._worker    = None
        self._direction = +1
        self._position  = 0

        self._build_ui()
        self._refresh_connection_state()

    #  UI 

    def _build_ui(self):
        self.setObjectName("axisCard")
        self.setStyleSheet(f"""
            #axisCard {{
                background-color: {S.BG_PANEL};
                border: 1px solid {S.BORDER};
                border-radius: 8px;
            }}
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(10)

        #  Header 
        header = QHBoxLayout()
        self._led = StatusLED("connected" if self._motor.is_connected
                              else "disconnected")
        axis_label = QLabel(f"AXIS  {self._axis}")
        axis_label.setStyleSheet(f"""
            color: {S.AMBER}; font-size: 16px; font-weight: 800;
            letter-spacing: 2px; background: transparent;
        """)
        header.addWidget(self._led, alignment=Qt.AlignmentFlag.AlignVCenter)
        header.addSpacing(8)
        header.addWidget(axis_label)
        header.addStretch()
        root.addLayout(header)
        root.addWidget(HLine())

        #  Position display 
        root.addWidget(SectionTitle("Position"))
        self._pos_display = DigitalDisplay("0", color=S.AMBER, font_size=24)
        self._pos_display.setToolTip("Current position in pulses")
        root.addWidget(self._pos_display)
        root.addWidget(HLine())

        #  Move parameters 
        root.addWidget(SectionTitle("Move"))

        grid = QGridLayout()
        grid.setSpacing(8)

        grid.addWidget(QLabel("Pulses"), 0, 0)
        self._pulses_spin = QSpinBox()
        self._pulses_spin.setRange(1, 999_999)
        self._pulses_spin.setValue(1000)
        self._pulses_spin.setSingleStep(100)
        self._pulses_spin.setToolTip("Pulses per single step")
        grid.addWidget(self._pulses_spin, 0, 1)

        grid.addWidget(QLabel("Speed"), 1, 0)
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(1, 500_000)
        self._speed_spin.setValue(5000)
        self._speed_spin.setSingleStep(500)
        self._speed_spin.setToolTip("Speed in pulse/s (direction set by Forward/Backward)")
        grid.addWidget(self._speed_spin, 1, 1)

        grid.addWidget(QLabel("Steps"), 2, 0)
        self._steps_spin = QSpinBox()
        self._steps_spin.setRange(1, 10_000)
        self._steps_spin.setValue(1)
        self._steps_spin.setToolTip("How many times to repeat the move")
        grid.addWidget(self._steps_spin, 2, 1)

        grid.addWidget(QLabel("Delay (s)"), 3, 0)
        self._delay_spin = QDoubleSpinBox()
        self._delay_spin.setRange(0.0, 3600.0)
        self._delay_spin.setValue(0.0)
        self._delay_spin.setSingleStep(0.5)
        self._delay_spin.setDecimals(1)
        self._delay_spin.setToolTip("Pause between steps in seconds (0 = no pause)")
        grid.addWidget(self._delay_spin, 3, 1)

        root.addLayout(grid)

        #  Direction toggle 
        dir_row = QHBoxLayout()
        dir_row.setSpacing(6)
        self._btn_fwd = QPushButton("▶  Forward")
        self._btn_fwd.setCheckable(True)
        self._btn_fwd.setChecked(True)
        self._btn_fwd.clicked.connect(lambda: self._set_direction(+1))

        self._btn_bwd = QPushButton("◀  Backward")
        self._btn_bwd.setCheckable(True)
        self._btn_bwd.clicked.connect(lambda: self._set_direction(-1))

        _dir_style = f"""
            QPushButton {{
                background-color: {S.BG_WIDGET};
                color: {S.TEXT_SUB};
                border: 1px solid {S.BORDER};
                border-radius: 4px;
                padding: 6px 10px;
                font-size: 12px;
            }}
            QPushButton:checked {{
                background-color: #2A1A08;
                color: {S.AMBER};
                border-color: {S.AMBER};
                font-weight: 700;
            }}
            QPushButton:hover {{ background-color: {S.BG_HOVER}; }}
        """
        self._btn_fwd.setStyleSheet(_dir_style)
        self._btn_bwd.setStyleSheet(_dir_style)
        dir_row.addWidget(self._btn_fwd)
        dir_row.addWidget(self._btn_bwd)
        root.addLayout(dir_row)

        root.addWidget(HLine())

        #  Action buttons 
        self._btn_move = make_button("MOVE", role="amber")
        self._btn_move.setStyleSheet(f"""
            QPushButton {{
                background-color: {S.AMBER};
                color: #07090E;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: 700;
                padding: 8px 22px;
            }}
            QPushButton:hover   {{ background-color: #FFC830; }}
            QPushButton:pressed {{ background-color: #CC8800; }}
            QPushButton:disabled {{
                background-color: #2A2000;
                color: #5A4800;
            }}
        """)
        self._btn_move.clicked.connect(self._on_move)

        self._btn_home = make_button("HOME", role="default")
        self._btn_home.setToolTip("Send motor to origin (H:1 command)")
        self._btn_home.clicked.connect(self._on_home)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self._btn_move)
        btn_row.addWidget(self._btn_home)
        root.addLayout(btn_row)

        #  Status label 
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet(
            f"color: {S.TEXT_DIM}; font-size: 11px; background: transparent;"
        )
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        root.addWidget(self._status_label)
        root.addStretch()

    # Slots 

    def _set_direction(self, d: int):
        self._direction = d
        self._btn_fwd.setChecked(d == +1)
        self._btn_bwd.setChecked(d == -1)

    def _on_move(self):
        if not self._motor.is_connected:
            self._set_status("Not connected", error=True)
            return
        
        if self._worker is not None:
          self._worker.quit()
          self._worker.wait(2000)
          self._worker = None

        pulses = self._pulses_spin.value()
        speed  = self._direction * abs(self._speed_spin.value())
        steps  = self._steps_spin.value()

        self._set_busy(True)
        self._set_status(
            f"Step 0/{steps}  ·  {'+' if speed > 0 else ''}{speed} p/s …"
        )

        self._worker = MoveWorker(self._motor, pulses, speed, steps,
                                   delay_s=self._delay_spin.value())
        self._worker.step_done.connect(self._on_step_done)
        self._worker.finished.connect(self._on_move_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_home(self):
        if not self._motor.is_connected:
            self._set_status("Not connected", error=True)
            return
        self._set_busy(True)
        self._set_status("Homing …")
        self._worker = HomeWorker(self._motor)
        self._worker.finished.connect(self._on_home_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_step_done(self, current: int, total: int):
        self._position += self._direction * self._pulses_spin.value()
        self._pos_display.set_text(str(self._position))
        delay = self._delay_spin.value()
        if delay > 0 and current < total:
            self._set_status(f"Step {current}/{total} done  ·  waiting {delay:.1f}s …")
        else:
            self._set_status(f"Step {current}/{total} …")

    def _on_move_done(self, position: str):
        self._pos_display.set_text(str(self._position))
        self._set_busy(False)
        self._set_status(f"Done  ·  pos = {self._position} pulses")
        self.status_changed.emit(self._axis, f"Move complete — position: {self._position}")

    def _on_home_done(self):
        self._position = 0
        self._pos_display.set_text("0")
        self._set_busy(False)
        self._set_status("Homing complete  ·  pos = 0")
        self.status_changed.emit(self._axis, "Homing complete")

    def _on_error(self, message: str):
        self._set_busy(False)
        self._set_status(message, error=True)
        self.status_changed.emit(self._axis, f"Error: {message}")

    #  Helpers 

    def _set_busy(self, busy: bool):
        self._btn_move.setEnabled(not busy)
        self._btn_home.setEnabled(not busy)
        self._led.set_state("busy" if busy else
                            ("connected" if self._motor.is_connected
                             else "disconnected"))

    def _set_status(self, text: str, error: bool = False):
        color = S.RED if error else S.TEXT_DIM
        self._status_label.setStyleSheet(
            f"color: {color}; font-size: 11px; background: transparent;"
        )
        self._status_label.setText(text)

    def _refresh_connection_state(self):
        connected = self._motor.is_connected
        self._led.set_state("connected" if connected else "disconnected")
        for w in (self._btn_move, self._btn_home,
                  self._pulses_spin, self._speed_spin,
                  self._steps_spin, self._delay_spin):
            w.setEnabled(connected)
        if connected:
            try:
                pos = self._motor.get_position()
                self._pos_display.set_text(str(pos))
            except Exception:
                pass


#  Main panel 

class MotorPanel(QWidget):
    status_message = pyqtSignal(str)

    def __init__(self, motors: dict, parent=None):
        super().__init__(parent)
        self._motors = motors
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)
        root.setSpacing(16)

        title = QLabel("Motion Control")
        title.setStyleSheet(
            f"color: {S.TEXT}; font-size: 20px; font-weight: 700; background: transparent;"
        )
        subtitle = QLabel(
            f"{len(self._motors)} axis connected  ·  Opto Sigma SRC-101"
        )
        subtitle.setStyleSheet(
            f"color: {S.TEXT_SUB}; font-size: 12px; background: transparent;"
        )
        root.addWidget(title)
        root.addWidget(subtitle)
        root.addWidget(HLine())

        cards_row = QHBoxLayout()
        cards_row.setSpacing(14)

        for axis in sorted(self._motors.keys()):
            card = AxisCard(axis, self._motors[axis])
            card.status_changed.connect(
                lambda ax, msg: self.status_message.emit(f"[Motor {ax}]  {msg}")
            )
            cards_row.addWidget(card)

        if not self._motors:
            no_motor = QLabel(
                "No motors connected.\nCheck cables and VISA addresses in config.py."
            )
            no_motor.setAlignment(Qt.AlignmentFlag.AlignCenter)
            no_motor.setStyleSheet(
                f"color: {S.TEXT_DIM}; font-size: 14px; background: transparent;"
            )
            cards_row.addWidget(no_motor)

        root.addLayout(cards_row)
        root.addStretch()
