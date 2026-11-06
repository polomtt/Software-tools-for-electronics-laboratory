# Lab Control System — General Guide

**Version:** 1.1
**Stack:** Python 3.11+, PyQt6, pyqtgraph, pyvisa, openpyxl
**Entry point:** `app.py`

---

## Table of Contents

1. [Project Structure](#1-project-structure)
2. [Getting Started](#2-getting-started)
3. [Running the Application](#3-running-the-application)
4. [Application Overview](#4-application-overview)
5. [Tab by Tab — User Guide](#5-tab-by-tab--user-guide)
   - [5.1 Motors](#51-motors)
   - [5.2 Oscilloscope](#52-oscilloscope)
   - [5.3 Power Meter](#53-power-meter)
   - [5.4 Scan](#54-scan)
   - [5.5 Loop Scan](#55-loop-scan)
   - [5.6 Photo Current](#56-photo-current)
   - [5.7 Help](#57-help)
6. [Configuration — config.py](#6-configuration--configpy)
7. [Developer Guide: Adding a New Tab](#7-developer-guide-adding-a-new-tab)
8. [Developer Guide: Adjusting Window and Panel Sizes](#8-developer-guide-adjusting-window-and-panel-sizes)
9. [Developer Guide: Adding a New Instrument](#9-developer-guide-adding-a-new-instrument)
10. [Building the Executable](#10-building-the-executable)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Project Structure

```
LabApplication/
├── app.py                  # Entry point — connects instruments, launches GUI
├── main.py                 # Legacy terminal interface (still functional)
├── build.bat               # One-click rebuild of the .exe
├── icona.ico               # Application icon
├── TestSpeed.xlsx          # Motor calibration file (loaded by Help tab)
├── requirements.txt        # Python dependencies
│
├── core/                   # Instrument drivers (no GUI dependency)
│   ├── motor.py            # Opto Sigma SRC-101 serial driver
│   ├── oscilloscope.py     # Tektronix MDO3102 SCPI/USB-TMC driver
│   └── power_meter.py      # Thorlabs PM100D SCPI/USB-TMC driver
│
├── gui/                    # All GUI components
│   ├── __init__.py
│   ├── style.py            # Dark theme: color palette + QSS stylesheet
│   ├── widgets.py          # Reusable widgets: StatusLED, DigitalDisplay, etc.
│   ├── main_window.py      # Main window: tabs + status bar + Reconnect All
│   ├── motor_panel.py      # Tab: Motors
│   ├── scope_panel.py      # Tab: Oscilloscope
│   ├── power_panel.py      # Tab: Power Meter
│   ├── scan_panel.py       # Tab: Scan (also exports shared classes)
│   ├── loop_scan_panel.py  # Tab: Loop Scan
│   ├── photo_current_panel.py  # Tab: Photo Current
│   └── help_panel.py       # Tab: Help (calibration table + plot)
│
├── utils/
│   └── config.py           # VISA addresses, constants, calibration file path
│
├── build/                  # PyInstaller build cache (auto-generated)
└── dist/                   # Final .exe output (auto-generated)
```

**Key design principle:** `core/` knows nothing about `gui/`. The instrument drivers
work identically whether called from `app.py`, `main.py`, or any GUI panel. This
separation makes the code easy to test and extend.

---

## 2. Getting Started

### Prerequisites

- Python 3.11 or later
- NI-VISA installed on the machine (required for instrument communication)
- USB cables for all instruments

### Install dependencies

```bash
# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install all packages
pip install -r requirements.txt
```

If `requirements.txt` is missing or outdated, install manually:

```bash
pip install PyQt6 pyqtgraph pyvisa pyvisa-py pyusb pyserial openpyxl numpy
```

### Find VISA addresses

With instruments connected and powered on, run:

```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
```

Note each address and enter it in `utils/config.py`.

---

## 3. Running the Application

### GUI mode (normal use)

```bash
python app.py
```

### Terminal mode (legacy, no GUI)

```bash
python main.py
```

### As executable (after building)

Double-click `dist/app.exe`. No Python installation required on the target machine,
but NI-VISA (or equivalent USB driver) must be installed.

---

## 4. Application Overview

The application window has seven tabs:

| Tab | Purpose |
|-----|---------|
| Motors | Manual motor control — move, home, set steps/speed/delay |
| Oscilloscope | Continuous waveform acquisition, live plot, CSV save |
| Power Meter | Continuous power reading, live display, CSV save |
| Scan | Automated scan sequences with triggered measurements |
| Loop Scan | Repeat a motion sequence N times with cycle-filtered measurements |
| Photo Current | Integrate oscilloscope signal at each step, plot Charge vs Position live |
| Help | Motor speed calibration table from Excel, with plot |

A **status bar** runs across the bottom of the window, showing:
- The last action message (left)
- Connection LEDs for each instrument (right)
- A **Reconnect All** button to reconnect instruments without restarting the app

---

## 5. Tab by Tab — User Guide

### 5.1 Motors

Each motor axis (X, Y, Z) has its own card. Controls per card:

| Field | Description |
|-------|-------------|
| Position display | Current position in pulses (tracked locally, resets to 0 on start or HOME) |
| Pulses | Number of pulses per single step |
| Speed | Digital speed (absolute value; direction set by Forward/Backward) |
| Steps | How many times to repeat the move |
| Delay (s) | Pause between steps in seconds (0 = no pause) |
| Forward / Backward | Direction toggle |
| MOVE | Execute the configured motion |
| HOME | Send the axis to its mechanical origin (H:1 command) |

**Note on position tracking:** The position counter is software-side only. It starts
at 0 when the app opens. Forward moves add pulses, backward moves subtract. HOME
resets to 0. This is intentional to avoid serial communication issues.

---

### 5.2 Oscilloscope

**Controls:**
- Channel selector: CH1 only / CH2 only / Both
- Interval (s): time between automatic acquisitions
- Save Location: output folder and optional filename prefix

**Workflow:**
1. Press **START** — waveform updates every N seconds
2. Press **RECORD** — every acquisition is saved as a CSV file
3. Press **STOP** — stops both acquisition and recording

**CSV format:** Each file has a metadata header followed by two columns:
```
# timestamp,        2026-05-20 10:30:45.123
# channel,          CH1
# n_points,         10000
# sample_rate_Hz,   1.000000e+09
# ch_scale_V_div,   2.000000e-03
# h_scale_s_div,    1.000000e-08
...

time_s,voltage_V
-5.000000e-06,1.234567e-03
...
```
All parameters needed to reconstruct the signal as displayed on the oscilloscope
are included in the header.

**Filename format:** `prefix_CH1_20260520_103045_123.csv`

---

### 5.3 Power Meter

**Controls:**
- Wavelength (nm): calibration wavelength
- Samples: number of software readings averaged
- Averaging: hardware averaging count on the PM100D
- Interval (ms): time between readings
- Unit selector: switch display between mW and µW (does not affect saved data)

**Workflow:**
1. Press **START** — display updates continuously
2. Press **RECORD** — every reading is saved as a separate CSV file
3. Press **STOP** — stops both

**CSV format:**
```
timestamp,    2026-05-20 10:30:45
wavelength_nm, 1550.0
n_samples,    10
averaging,    5

mean_W,       std_W,        min_W,        max_W,        mean_mW
1.234567E-03, 2.345678E-05, ...
```

**Filename format:** `prefix_20260520_103045_123.csv`

---

### 5.4 Scan

The Scan tab automates a sequence of motor movements with triggered measurements.

#### Path Log (left panel)

Each motion row has two lines:

```
[N] [Axis▾] [Dir▾]  Pulses [____]  Speed [____]      [UP][DN][DEL]
              Steps [____]  Delay(s) [____]  µm target [____]
```

The **µm target** field appears automatically when the entered speed matches a
calibration in `TestSpeed.xlsx`. Changing the µm value automatically recalculates
the pulses using interpolation on the calibration table.

**UP / DN** buttons reorder motions before the scan starts.

#### Measurements (right panel)

Select Oscilloscope or Power Meter from the dropdown. Each has:
- Enable checkbox
- Output folder + prefix
- Trigger rules list (add as many as needed)

**Trigger rule types:**
- After every step (any motion)
- After every step of motion #N
- After last step of motion #N

Each rule can optionally have a **Custom folder** (checkbox). If not set, uses the
global folder for that instrument.

If two rules match the same step with different folders, two files are saved —
one in each folder.

#### Relative Homing

1. Configure the Path Log
2. Press **Set Home** — snapshots the current motions as the home reference
3. Run the scan
4. Press **Return Home** — executes the reverse:
   - Motions in reverse order
   - Each direction flipped
   - Each step count halved (backlash compensation)
   - Minimum 1 step per motion

**Note:** Set Home snapshots the Path Log at that moment. Changing the Path Log
after setting home does not affect the return path.

---

### 5.5 Loop Scan

The Loop Scan tab repeats a motion sequence N times, with full control over which
cycles trigger measurements.

#### Loop Settings

| Field | Description |
|-------|-------------|
| Cycles | Number of repetitions (or tick ∞ for infinite loop) |
| Pause between cycles | Wait time in seconds between each full cycle (can be 0) |

#### Cycle Filter

Determines in which cycles measurements are saved. Four modes (mutually exclusive):

| Mode | Behaviour |
|------|-----------|
| Every cycle | Save on every cycle |
| Every N cycles | Save on cycles 1, 1+N, 1+2N, … |
| Specific cycles | Enter a list/range: `1, 3, 5-8, 10` |
| First and last only | Saves only on cycle 1 and on the final cycle |

The cycle filter applies equally to both Oscilloscope and Power Meter.

#### Measurement Policy

Identical to the Scan tab — Oscilloscope and Power Meter each have trigger rules,
output folders, and optional custom folder per rule.

#### CSV filename format

Includes the cycle number for easy sorting:
```
prefix_c001_m02_s003_CH1_20260522_103045.csv
         │    │    │
         │    │    └── step 3
         │    └──────── motion 2
         └───────────── cycle 001
```

---

### 5.6 Photo Current

Integrates the oscilloscope signal at each motor step and plots the result as a
**Charge vs Position** curve in a floating live-updating window.

#### Acquisition Settings

| Field | Description |
|-------|-------------|
| Channel | CH1 or CH2 (single channel only) |
| Cycles | Number of loop repetitions (or ∞) |
| Pause between cycles | Wait between cycles in seconds |

#### Integration Window

Sets the time interval `[t_start, t_end]` over which `V(t)` is integrated using
the trapezoidal rule (`numpy.trapz`). The unit selector (ns / µs / ms / s) scales
both fields.

```
Charge (V·s) = ∫[t_start → t_end] V(t) dt
```

#### Position axis

- **µm** — if the motion speed is calibrated in `TestSpeed.xlsx`. Position accumulates
  as `± µm_per_step` for each motor step (sign depends on direction).
- **Step #** — if the speed is not calibrated. A monotonically increasing counter.

When there are multiple motions with different speeds (some calibrated, some not),
the first calibrated motion determines whether µm or step # is used for the whole scan.

#### Live Plot Window

Opens automatically when RUN is pressed. Stays open even if you switch tab.
Each cycle is plotted as a separate colored curve (orange, cyan, green, amber…).
The **Clear Plot** button wipes all curves. The **Show Plot** button re-opens the
window if it was closed.

#### Save Waveforms (optional)

If enabled, saves the raw oscilloscope CSV at triggered steps — same format as
the Scan tab, including the full metadata header.

---

### 5.7 Help

1. Browse to `TestSpeed.xlsx` (or it loads automatically from the project folder)
2. Use the **Speed** dropdown to switch between calibration sheets
3. Press **Open in Excel** to edit the file
4. Press **Reload** after saving to refresh the table
5. Press **Show Plot** to see a Pulses vs µm/step chart for the selected speed

**Adding a new speed calibration:**
1. Open `TestSpeed.xlsx` in Excel
2. Create a new sheet
3. In cell C1 (or any cell in row 1), write the speed title, e.g. `Speed 1200`
4. In row 3, write the column headers: `Pulses`, `um/step_1`, ..., `MEAN`
5. Fill in the data rows
6. Save and press **Reload** in the Help tab
7. The new speed will appear in the dropdown and become available in the Scan tab

---

## 6. Configuration — config.py

Located at `utils/config.py`. Edit this file to match your hardware setup.

```python
# VISA addresses for the three motor axes
MOTOR_1_ADDRESS = "ASRL3::INSTR"   # Z axis
MOTOR_2_ADDRESS = "ASRL4::INSTR"   # X axis
MOTOR_3_ADDRESS = "ASRL5::INSTR"   # Y axis

# VISA address for the oscilloscope
# Format: "USB0::0x<VendorID>::0x<ProductID>::<Serial>::INSTR"
OSCILLOSCOPE_ADDRESS = "USB0::0x0699::0x0408::C019950::INSTR"

# Delay between motor steps in the terminal interface (seconds)
STEP_DELAY = 0.1

# Path to the Excel calibration file (relative to project root)
CALIBRATION_FILE = "TestSpeed.xlsx"
```

**Finding VISA addresses:**
```python
import pyvisa
rm = pyvisa.ResourceManager()
print(rm.list_resources())
# Output: ('ASRL3::INSTR', 'ASRL4::INSTR', 'USB0::0x0699::...')
```

---

## 7. Developer Guide: Adding a New Tab

Adding a new tab requires three steps:

### Step 1 — Create the panel file

Create `gui/my_panel.py` with this minimal structure:

```python
# gui/my_panel.py
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PyQt6.QtCore    import pyqtSignal
import gui.style as S
from gui.widgets import HLine

class MyPanel(QWidget):
    status_message = pyqtSignal(str)   # optional — connects to status bar

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 20)

        title = QLabel("My Panel")
        title.setStyleSheet(
            f"color:{S.TEXT}; font-size:20px; font-weight:700; background:transparent;"
        )
        root.addWidget(title)
        root.addWidget(HLine())
        root.addStretch()
```

### Step 2 — Register it in main_window.py

Open `gui/main_window.py` and add two lines inside `_build_ui()`:

```python
from gui.my_panel import MyPanel

# ...inside _build_ui(), after the other tabs:
my_panel = MyPanel()
my_panel.status_message.connect(self._set_status)   # optional
tabs.addTab(my_panel, "  My Panel  ")
```

### Step 3 — If the panel needs instruments

Pass the relevant objects from `MainWindow.__init__`:

```python
# In main_window.py _build_ui():
my_panel = MyPanel(motors=self._motors, scope=self._scope)
```

```python
# In my_panel.py:
def __init__(self, motors: dict, scope, parent=None):
    super().__init__(parent)
    self._motors = motors
    self._scope  = scope
    self._build_ui()
```

That's all — the tab appears automatically in the tab bar.

---

## 8. Developer Guide: Adjusting Window and Panel Sizes

### Main window size

In `gui/main_window.py`, `__init__`:

```python
self.setMinimumSize(1100, 720)   # minimum size (cannot shrink below this)
self.resize(1280, 800)           # initial size on open
```

To start maximized instead:
```python
self.showMaximized()
```

### Sidebar widths

Each panel has a `sidebar_widget.setFixedWidth(N)` call. Change `N` to widen or
narrow the left controls column. For example in `scope_panel.py`:

```python
sidebar_widget.setFixedWidth(320)   # increase for more room
```

### Making a sidebar scrollable

If a sidebar has too many controls for the window height, wrap it in a
`QScrollArea`. The oscilloscope panel already does this as a reference:

```python
scroll = QScrollArea()
scroll.setWidget(settings_widget)
scroll.setWidgetResizable(True)
scroll.setFrameShape(QFrame.Shape.NoFrame)
scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
```

### Separating settings from action buttons

A good pattern (used in scope_panel.py and power_panel.py) is:

```python
sidebar_outer = QVBoxLayout(sidebar_widget)
sidebar_outer.addWidget(scroll_area, stretch=1)   # settings scroll freely
sidebar_outer.addWidget(btn_area)                  # buttons always visible at bottom
```

### Table heights

In scope_panel.py the statistics table has:
```python
self._stats_table.setFixedHeight(168)
```
Remove `setFixedHeight` or increase the value to show more rows.

---

## 9. Developer Guide: Adding a New Instrument

### Step 1 — Write the driver in core/

Follow the pattern of `oscilloscope.py`:

```python
# core/my_instrument.py
import pyvisa

class MyInstrument:
    def __init__(self, address: str):
        self.address = address
        self._rm  = pyvisa.ResourceManager()
        self._dev = None

    def connect(self):
        self._dev = self._rm.open_resource(self.address)
        self._dev.timeout = 10_000
        idn = self._dev.query("*IDN?").strip()
        print(f"[MyInstrument] Connected: {idn}")

    def disconnect(self):
        if self._dev:
            self._dev.close()
            self._dev = None

    @property # manage as attribute, not method
    def is_connected(self) -> bool:
        return self._dev is not None

    def read(self):
        return float(self._dev.query("MEAS?"))
```

### Step 2 — Add the address to config.py

```python
MY_INSTRUMENT_ADDRESS = "USB0::0x1234::0x5678::SN001::INSTR"
```

### Step 3 — Instantiate it in app.py

```python
from core.my_instrument import MyInstrument
from utils.config import MY_INSTRUMENT_ADDRESS

def build_my_instrument():
    inst = MyInstrument(MY_INSTRUMENT_ADDRESS)
    try:
        inst.connect()
        print("[MyInstrument] Connected")
    except Exception as exc:
        print(f"[MyInstrument] Not connected: {exc}")
    return inst

# In main():
my_inst = build_my_instrument()
window = MainWindow(motors=motors, scope=scope, pm=pm, my_inst=my_inst)
```

### Step 4 — Pass it through MainWindow and add a panel

In `main_window.py`, add it to `__init__` and create a panel for it following the
pattern in Section 7.

### Step 5 — Add to Reconnect All

In `main_window.py`, inside `ReconnectWorker.run()`, add a block:

```python
self.progress.emit("Reconnecting my instrument …")
try:
    if self._my_inst.is_connected:
        self._my_inst._dev.close()
        self._my_inst._dev = None
    self._my_inst.connect()
    results["My Instrument"] = True
except Exception as exc:
    results["My Instrument"] = False
    self.progress.emit(f"My Instrument failed: {exc}")
```

---

## 10. Building the Executable

### Prerequisites

```bash
pip install pyinstaller
```

The `icona.ico` file must be in the project root.

### Build

Double-click `build.bat`, or from PowerShell with the venv active:

```bash
pyinstaller --onefile --windowed --clean \
  --collect-all PyQt6 \
  --collect-all pyqtgraph \
  --collect-all pyvisa \
  --collect-all pyvisa_py \
  --collect-all usb \
  --collect-all serial \
  --collect-all openpyxl \
  --collect-all OpenGL \
  --icon=icona.ico \
  app.py
```

The executable is created at `dist/app.exe`.

### Deploying to another PC

Copy only `dist/app.exe` (and optionally `TestSpeed.xlsx` next to it).
The target PC needs:
- **NI-VISA** (or equivalent USB/serial driver) — not included in the .exe
- No Python installation required

**Important:** VISA addresses are baked into the executable at build time via
`config.py`. If the target PC uses different port numbers (e.g. `ASRL5` instead of
`ASRL3`), update `config.py` before rebuilding.

---

## 11. Troubleshooting

### Instruments not found on startup

1. Check USB/serial cables are connected and powered on
2. Open NI-MAX and verify the instrument appears there
3. Run `pyvisa.ResourceManager().list_resources()` to confirm the address
4. Update `utils/config.py` with the correct address
5. If the address changed between runs, use **Reconnect All** in the status bar

### "No module named 'gui'" error

The `gui/` folder is not in the same directory as `app.py`.
Verify the folder structure matches Section 1.

### Oscilloscope CSV has only two columns

You are using an older version of `core/oscilloscope.py`. The current version
uses `read_waveform_meta()` which writes a full metadata header. Replace the file
with the latest version.

### µm target field does not appear in Scan tab

The calibration file was not loaded. Open the **Help** tab — if the table is empty,
click **Browse** and select `TestSpeed.xlsx`. The Scan tab updates automatically
once the file is loaded.

### Motors move but position display stops updating

This is a known PyQt6 threading issue with stale worker objects. The fix is already
in `motor_panel.py` — the position is tracked locally by the panel (not queried
from the motor). If you still see the issue after updating the file, verify you are
running the latest `motor_panel.py`.

### "QThread: Destroyed while thread is still running"

A worker thread was garbage-collected before finishing. All workers in the
application are stored as instance variables (`self._worker`) to prevent this.
If you see this error in a new panel you are developing, make sure to store
the worker as `self._worker = MyWorker(...)` rather than a local variable.

### PyInstaller build fails with missing module

Add `--collect-all <module_name>` to the build command in `build.bat`.
Common additions: `OpenGL`, `openpyxl`, `pyvisa_py`, `usb`, `serial`.
