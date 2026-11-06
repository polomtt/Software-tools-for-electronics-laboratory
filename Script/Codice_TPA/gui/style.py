# gui/style.py
"""
Dark theme stylesheet and color palette.
Aesthetic: Instrument-Grade Industrial - dark panels, glowing accents.
"""

#  Color Palette 
BG_DEEP    = "#07090E"   # window / deepest background
BG_MAIN    = "#0D1118"   # main widget background
BG_PANEL   = "#131925"   # card / panel background
BG_WIDGET  = "#1B2133"   # input / inner widget background
BG_HOVER   = "#232C42"   # hover state

ACCENT     = "#FF6B35"   # primary accent - orange (oscilloscope trace feel)
CYAN       = "#00D2FF"   # data / readings
GREEN      = "#39FF14"   # connected / OK (electric green)
AMBER      = "#FFB800"   # motor / warning
RED        = "#FF4560"   # error / disconnected

BORDER     = "#232B40"
BORDER_LT  = "#38435E"

TEXT       = "#E8ECF5"
TEXT_SUB   = "#7A86A2"
TEXT_DIM   = "#404D66"

FONT_UI    = "'Segoe UI', 'SF Pro Display', 'Ubuntu', sans-serif"
FONT_MONO  = "'Consolas', 'Courier New', monospace"

#  Main Stylesheet 
QSS = f"""

/*  Base  */
QMainWindow {{
    background-color: {BG_DEEP};
}}
QWidget {{
    background-color: {BG_MAIN};
    color: {TEXT};
    font-family: {FONT_UI};
    font-size: 13px;
}}

/*  Tab Widget  */
QTabWidget::pane {{
    border: 1px solid {BORDER};
    background-color: {BG_PANEL};
    top: -1px;
}}
QTabWidget::tab-bar {{
    alignment: left;
}}
QTabBar {{
    background-color: {BG_DEEP};
}}
QTabBar::tab {{
    background-color: {BG_DEEP};
    color: {TEXT_SUB};
    padding: 11px 30px;
    border: none;
    border-bottom: 2px solid transparent;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 1.2px;
    text-transform: uppercase;
    min-width: 120px;
}}
QTabBar::tab:selected {{
    color: {ACCENT};
    border-bottom: 2px solid {ACCENT};
    background-color: {BG_PANEL};
}}
QTabBar::tab:hover:!selected {{
    color: {TEXT};
    background-color: {BG_WIDGET};
    border-bottom: 2px solid {BORDER_LT};
}}

/*  GroupBox  */
QGroupBox {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 22px;
    padding: 14px 12px 12px 12px;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 14px;
    top: 3px;
    padding: 0 6px;
    color: {TEXT_SUB};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.5px;
    text-transform: uppercase;
}}

/*  Inputs  */
QLineEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {BG_WIDGET};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 7px 10px;
    font-size: 13px;
    selection-background-color: {ACCENT};
    selection-color: #0D1118;
}}
QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus {{
    border-color: {ACCENT};
}}
QLineEdit:disabled, QSpinBox:disabled, QDoubleSpinBox:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background-color: {BG_PANEL};
}}
QSpinBox::up-button, QSpinBox::down-button,
QDoubleSpinBox::up-button, QDoubleSpinBox::down-button {{
    background-color: {BG_HOVER};
    border: none;
    width: 20px;
    border-radius: 2px;
}}
QSpinBox::up-button:hover, QSpinBox::down-button:hover,
QDoubleSpinBox::up-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {BORDER_LT};
}}
QComboBox {{
    background-color: {BG_WIDGET};
    color: {TEXT};
    border: 1px solid {BORDER};
    border-radius: 4px;
    padding: 7px 10px;
    font-size: 13px;
}}
QComboBox:focus {{ border-color: {ACCENT}; }}
QComboBox::drop-down {{
    border: none;
    background-color: {BG_HOVER};
    width: 26px;
    border-radius: 0 4px 4px 0;
}}
QComboBox QAbstractItemView {{
    background-color: {BG_PANEL};
    border: 1px solid {BORDER_LT};
    selection-background-color: {BG_HOVER};
    color: {TEXT};
    outline: none;
    padding: 4px;
}}

/*  Buttons  */
QPushButton {{
    background-color: {BG_WIDGET};
    color: {TEXT};
    border: 1px solid {BORDER_LT};
    border-radius: 4px;
    padding: 8px 22px;
    font-size: 13px;
    font-weight: 500;
}}
QPushButton:hover {{
    background-color: {BG_HOVER};
    border-color: {TEXT_SUB};
}}
QPushButton:pressed {{
    background-color: {BG_DEEP};
    border-color: {ACCENT};
}}
QPushButton:disabled {{
    color: {TEXT_DIM};
    border-color: {BORDER};
    background-color: {BG_PANEL};
}}

/* Primary — orange fill */
QPushButton[btnRole="primary"] {{
    background-color: {ACCENT};
    color: #07090E;
    border: none;
    font-weight: 700;
    letter-spacing: 0.5px;
}}
QPushButton[btnRole="primary"]:hover  {{ background-color: #FF855A; }}
QPushButton[btnRole="primary"]:pressed {{ background-color: #D94E18; }}
QPushButton[btnRole="primary"]:disabled {{
    background-color: #3A2010;
    color: #6A4030;
}}

/* Success — green outline */
QPushButton[btnRole="success"] {{
    background-color: transparent;
    color: {GREEN};
    border: 1px solid {GREEN};
    font-weight: 600;
}}
QPushButton[btnRole="success"]:hover  {{ background-color: #0A2010; }}
QPushButton[btnRole="success"]:pressed {{ background-color: #051008; }}

/* Danger — red outline */
QPushButton[btnRole="danger"] {{
    background-color: transparent;
    color: {RED};
    border: 1px solid {RED};
    font-weight: 600;
}}
QPushButton[btnRole="danger"]:hover  {{ background-color: #2A0510; }}
QPushButton[btnRole="danger"]:pressed {{ background-color: #150208; }}

/* Amber - motor accent */
QPushButton[btnRole="amber"] {{
    background-color: {AMBER};
    color: #07090E;
    border: none;
    font-weight: 700;
}}
QPushButton[btnRole="amber"]:hover  {{ background-color: #FFC830; }}
QPushButton[btnRole="amber"]:pressed {{ background-color: #CC8800; }}
QPushButton[btnRole="amber"]:disabled {{
    background-color: #2A2000;
    color: #5A4800;
}}

/*  Labels  */
QLabel {{ color: {TEXT}; background-color: transparent; }}

/*  Status Bar  */
QStatusBar {{
    background-color: {BG_DEEP};
    color: {TEXT_SUB};
    border-top: 1px solid {BORDER};
    font-size: 12px;
    padding: 2px 8px;
}}
QStatusBar::item {{ border: none; }}

/*  Scroll Bars  */
QScrollBar:vertical {{
    background-color: {BG_PANEL};
    width: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {BORDER_LT};
    border-radius: 4px;
    min-height: 30px;
}}
QScrollBar::handle:vertical:hover {{ background-color: {TEXT_SUB}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}

QScrollBar:horizontal {{
    background-color: {BG_PANEL};
    height: 8px;
    border-radius: 4px;
    margin: 0;
}}
QScrollBar::handle:horizontal {{
    background-color: {BORDER_LT};
    border-radius: 4px;
    min-width: 30px;
}}
QScrollBar::handle:horizontal:hover {{ background-color: {TEXT_SUB}; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/*  Separator  */
QFrame[frameShape="4"], QFrame[frameShape="5"] {{
    color: {BORDER};
    background-color: {BORDER};
}}

/*  Splitter  */
QSplitter::handle {{
    background-color: {BORDER};
}}
QSplitter::handle:horizontal {{ width: 2px; }}
QSplitter::handle:vertical   {{ height: 2px; }}

/*  Table  */
QTableWidget {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER};
    gridline-color: {BORDER};
    selection-background-color: {BG_HOVER};
    selection-color: {TEXT};
    font-size: 12px;
    outline: none;
}}
QTableWidget QHeaderView::section {{
    background-color: {BG_WIDGET};
    color: {TEXT_SUB};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 7px 10px;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1px;
    text-transform: uppercase;
}}
QTableWidget::item {{ padding: 4px 8px; }}
QTableWidget::item:selected {{ background-color: {BG_HOVER}; }}

/*  ToolTip  */
QToolTip {{
    background-color: {BG_PANEL};
    color: {TEXT};
    border: 1px solid {BORDER_LT};
    padding: 5px 8px;
    font-size: 12px;
}}
"""


def apply(app):
    """Apply the dark theme stylesheet to a QApplication instance."""
    app.setStyleSheet(QSS)
