# gui/widgets.py
"""
Reusable custom widgets for the Lab Control GUI.
"""

from PyQt6.QtWidgets import QLabel, QFrame, QSizePolicy
from PyQt6.QtCore    import Qt
from PyQt6.QtGui     import QColor, QPainter, QBrush, QPen

import gui.style as S


class StatusLED(QLabel):
    """
    A small colored circle indicator.

    States
    ------
    "connected"    -> electric green
    "disconnected" -> red
    "busy"         -> amber
    "idle"         -> dim gray
    """

    _COLORS = {
        "connected"    : S.GREEN,
        "disconnected" : S.RED,
        "busy"         : S.AMBER,
        "idle"         : S.TEXT_DIM,
    }

    def __init__(self, state: str = "disconnected", parent=None):
        super().__init__(parent)
        self._state = state
        self.setFixedSize(12, 12)
        self.setToolTip(state.capitalize())

    def set_state(self, state: str):
        """Update the LED state and repaint."""
        self._state = state
        self.setToolTip(state.capitalize())
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        color = QColor(self._COLORS.get(self._state, S.TEXT_DIM))

        # Outer glow (lighter, translucent)
        glow = QColor(color)
        glow.setAlpha(60)
        painter.setBrush(QBrush(glow))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(0, 0, 12, 12)

        # Inner filled circle
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(120), 0.5))
        painter.drawEllipse(2, 2, 8, 8)


class DigitalDisplay(QLabel):
    """
    A large monospace readout styled like an instrument LCD.

    Parameters
    ----------
    initial_text : str
        Text shown before any measurement (e.g. '---').
    color : str
        CSS color for the displayed value. Defaults to cyan.
    font_size : int
        Font size in points.
    """

    def __init__(
        self,
        initial_text: str = "---",
        color: str = None,
        font_size: int = 32,
        parent=None,
    ):
        super().__init__(initial_text, parent)
        color = color or S.CYAN
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                           QSizePolicy.Policy.Preferred)
        self.setStyleSheet(f"""
            QLabel {{
                color: {color};
                background-color: {S.BG_DEEP};
                border: 1px solid {S.BORDER};
                border-radius: 4px;
                font-family: {S.FONT_MONO};
                font-size: {font_size}px;
                font-weight: 700;
                padding: 10px 18px;
                letter-spacing: 2px;
            }}
        """)

    def set_value(self, value: float, unit: str = "", decimals: int = 4):
        """Update the displayed value."""
        self.setText(f"{value:.{decimals}f}  {unit}")

    def set_text(self, text: str):
        self.setText(text)


class SectionTitle(QLabel):
    """A small all-caps section header label."""

    def __init__(self, text: str, parent=None):
        super().__init__(text.upper(), parent)
        self.setStyleSheet(f"""
            QLabel {{
                color: {S.TEXT_SUB};
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.8px;
                background-color: transparent;
                padding-bottom: 4px;
            }}
        """)


class HLine(QFrame):
    """A horizontal divider line."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.HLine)
        self.setFrameShadow(QFrame.Shadow.Plain)
        self.setFixedHeight(1)
        self.setStyleSheet(f"background-color: {S.BORDER}; border: none;")


def make_button(text: str, role: str = "default", tooltip: str = "") -> "QPushButton":
    """
    Factory for styled buttons.

    Parameters
    ----------
    role : str
        "primary" | "success" | "danger" | "amber" | "default"
    """
    from PyQt6.QtWidgets import QPushButton
    btn = QPushButton(text)
    if role != "default":
        btn.setProperty("btnRole", role)
        btn.style().unpolish(btn)
        btn.style().polish(btn)
    if tooltip:
        btn.setToolTip(tooltip)
    return btn
