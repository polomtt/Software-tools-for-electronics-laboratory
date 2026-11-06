# Lab Control System — GUI Technical Reference

This document describes every file in the `gui/` package: its purpose, public
interface, internal structure, and how it connects to the rest of the application.

! Ctrl+Shift+V to compile and reading !

---

## Table of Contents

1. [gui/style.py — Theme and Color Palette](#1-guistylepy--theme-and-color-palette)
2. [gui/widgets.py — Reusable Custom Widgets](#2-guiwidgetspy--reusable-custom-widgets)
3. [gui/main_window.py — Main Application Window](#3-guimain_windowpy--main-application-window)
4. [gui/motor_panel.py — Motor Control Tab](#4-guimotor_panelpy--motor-control-tab)
5. [gui/scope_panel.py — Oscilloscope Tab](#5-guiscope_panelpy--oscilloscope-tab)
6. [gui/power_panel.py — Power Meter Tab](#6-guipower_panelpy--power-meter-tab)
7. [gui/scan_panel.py — Scan Tab (shared base)](#7-guiscan_panelpy--scan-tab-shared-base)
8. [gui/loop_scan_panel.py — Loop Scan Tab](#8-guiloop_scan_panelpy--loop-scan-tab)
9. [gui/photo_current_panel.py — Photo Current Tab](#9-guiphoto_current_panelpy--photo-current-tab)
10. [gui/help_panel.py — Help Tab](#10-guihelp_panelpy--help-tab)
11. [Threading Model](#11-threading-model)
12. [Signal and Slot Map](#12-signal-and-slot-map)

---

## 1. gui/style.py — Theme and Color Palette

### Purpose

Centralizes all visual design decisions. Every panel imports from here instead of
hardcoding colors. This means the entire look of the application can be changed by
editing a single file.

### Color Constants

All colors are hex strings. Import them as `S.COLOR_NAME`.

| Constant | Value | Used for |
|----------|-------|---------|
| `BG_DEEP` | `#07090E` | Window background, deepest layer |
| `BG_MAIN` | `#0D1118` | Main widget background |
| `BG_PANEL` | `#131925` | Cards and panels |
| `BG_WIDGET` | `#1B2133` | Inputs, buttons, inner widgets |
| `BG_HOVER` | `#232C42` | Hover state |
| `ACCENT` | `#FF6B35` | Primary accent — orange (oscilloscope trace, primary buttons) |
| `CYAN` | `#00D2FF` | Data readings, secondary accent |
| `GREEN` | `#39FF14` | Connected status, power meter display |
| `AMBER` | `#FFB800` | Motor axis labels, motor-related highlights |
| `RED` | `#FF4560` | Error state, disconnected, danger buttons |
| `BORDER` | `#232B40` | Standard border |
| `BORDER_LT` | `#38435E` | Lighter border, hover borders |
| `TEXT` | `#E8ECF5` | Primary text |
| `TEXT_SUB` | `#7A86A2` | Secondary/muted text, labels |
| `TEXT_DIM` | `#404D66` | Disabled or very muted text |
| `FONT_UI` | `'Segoe UI', ...` | UI font stack |
| `FONT_MONO` | `'Consolas', ...` | Monospace font for numeric displays |

### Button Roles

Buttons are styled via the `btnRole` Qt property. Available roles:

| Role | Appearance | Used for |
|------|-----------|---------|
| `primary` | Orange fill, dark text | Main action buttons |
| `success` | Green outline | RECORD, Save, connect actions |
| `danger` | Red outline | STOP, delete actions |
| `amber` | Amber fill, dark text | Motor MOVE button |
| *(default)* | Dark fill, light border | Secondary/neutral actions |

### `apply(app)` Function

Call once at startup to apply the stylesheet to the entire `QApplication`:

```python
import gui.style as style
style.apply(app)
```

### How to Change the Theme

To change the primary accent color from orange to blue throughout the entire app:

```python
# In style.py:
ACCENT = "#3A7BFF"   # was "#FF6B35"
```

To change a specific button style, edit the corresponding `QPushButton[btnRole="..."]`
block in the `QSS` string.

---

## 2. gui/widgets.py — Reusable Custom Widgets

### Purpose

Provides small, styled widgets used across multiple panels. Importing from here
keeps code DRY and ensures visual consistency.

---

### `StatusLED(QLabel)`

A small colored circle that indicates connection or activity state.

**States and colors:**

| State | Color | Meaning |
|-------|-------|---------|
| `"connected"` | Electric green | Instrument connected and ready |
| `"disconnected"` | Red | Not connected |
| `"busy"` | Amber | Operation in progress |
| `"idle"` | Dim gray | No activity |

**Usage:**
```python
led = StatusLED("disconnected")
led.set_state("connected")     # updates color and tooltip
```

**Implementation note:** Draws itself via `paintEvent` using `QPainter`. The outer
circle is a translucent version of the state color (glow effect), the inner circle
is the solid color.

---

### `DigitalDisplay(QLabel)`

A large monospace readout styled like an instrument LCD display.

**Constructor parameters:**
- `initial_text` — text shown before any measurement (default: `"---"`)
- `color` — CSS hex string (default: cyan `S.CYAN`)
- `font_size` — font size in pixels (default: 32)

**Methods:**
- `set_value(value, unit="", decimals=4)` — formats and displays a float
- `set_text(text)` — displays an arbitrary string

**Usage:**
```python
display = DigitalDisplay("---", color=S.GREEN, font_size=52)
display.set_value(1.2345, unit="mW", decimals=4)  # shows "1.2345  mW"
display.set_text("ERR")
```

---

### `SectionTitle(QLabel)`

A small all-caps section header label with letter spacing.

```python
root.addWidget(SectionTitle("Measurement Settings"))
```

---

### `HLine(QFrame)`

A horizontal divider line, 1px tall, colored `S.BORDER`.

```python
root.addWidget(HLine())
```

---

### `make_button(text, role="default", tooltip="")` → `QPushButton`

Factory function for styled buttons. Applies the `btnRole` property so the
stylesheet picks up the correct colors.

```python
btn = make_button("ACQUIRE", role="primary")
btn = make_button("SAVE", role="success", tooltip="Save to CSV")
btn = make_button("STOP", role="danger")
```

**Note:** After calling `make_button`, you can still override the stylesheet on
specific buttons with `btn.setStyleSheet(...)` for one-off customizations.

---

## 3. gui/main_window.py — Main Application Window

### Purpose

Top-level `QMainWindow`. Creates all tabs, assembles the status bar, manages
instrument connection LEDs, and provides the **Reconnect All** button.

### Class: `ReconnectWorker(QThread)`

Runs instrument reconnection off the UI thread to prevent freezing.

**Signals:**
- `finished(dict)` — emits `{instrument_name: bool}` with success/failure per instrument
- `progress(str)` — emits status messages during reconnection

**Algorithm:**
1. For each motor: close only `motor._inst` (not the ResourceManager), then call `connect()`
2. For oscilloscope: close `scope._dev`, then call `connect()`
3. For power meter: close `pm._dev`, then call `connect()`

**Why not call `disconnect()`?** `motor.disconnect()` also closes the
`ResourceManager`, which cannot be reopened. This worker bypasses that by
closing only the VISA handle directly.

---

### Class: `MainWindow(QMainWindow)`

**Constructor:**
```python
MainWindow(motors: dict, scope: Oscilloscope, pm: PowerMeter)
```

**Key responsibilities:**
- Creates `QTabWidget` with all seven panels
- Connects `help_panel.calibration_updated` to `scan_panel`, `loop_scan_panel`,
  and `photo_current_panel` — all three receive calibration data automatically
- Builds status bar with `StatusLED` per instrument and `Reconnect All` button
- `_set_status(message)` slot — updates the left-side status label

**Status bar layout:**
```
[last action message ............] [• Motors (3)] [• Oscilloscope] [• Power Meter] [⟳ Reconnect All]
```

**LED keys in `self._leds`:**
- `"motors"` — single LED representing all three axes collectively
- `"scope"` — oscilloscope
- `"pm"` — power meter

After reconnection, `_on_reconnect_done()` updates all LEDs based on
`is_connected` from each instrument object.

---

## 4. gui/motor_panel.py — Motor Control Tab

### Purpose

Provides three `AxisCard` widgets (one per motor axis) laid out horizontally.
Each card has full independent control.

### Class: `MoveWorker(QThread)`

Executes a motor move sequence off the UI thread.

**Constructor:**
```python
MoveWorker(motor, pulses: int, speed: int, steps: int = 1, delay_s: float = 0.0)
```

**Algorithm:**
```
for i in range(steps):
    motor.move(pulses, speed, wait=True)
    emit step_done(i+1, steps)
    if delay_s > 0 and i < steps-1:
        sleep(delay_s)

emit finished(str(position))   # safe: wraps get_position() in try/except
```

**Signals:**
- `finished(str)` — final position as string
- `step_done(int, int)` — (current_step, total_steps) after each step
- `error(str)` — error message if anything fails

**Why `str` for position?** The SRC-101 may return position strings in various
formats. Using `str` avoids `ValueError` from `int()` conversion failures.

---

### Class: `HomeWorker(QThread)`

Sends the home command off the UI thread.

**Algorithm:**
```
motor.home()    # sends H:1 + G: + wait_ready()
emit finished()
```

**Note:** Does NOT call `get_position()` after homing. The position display is
reset to `"0"` directly by the panel when `finished` fires.

---

### Class: `AxisCard(QFrame)`

Self-contained card for one motor axis. All state is local to the card.

**Key state:**
- `self._direction` — `+1` or `-1` (set by Forward/Backward buttons)
- `self._position` — int, tracked locally (never queried from motor after startup)
- `self._worker` — current worker, kept as instance var to prevent GC

**Position tracking:** After each step, `_on_step_done()` updates:
```python
self._position += self._direction * self._pulses_spin.value()
```
This is purely local arithmetic — no serial query involved. HOME resets it to 0.

**`_set_busy(busy)`:** Disables MOVE and HOME buttons, sets LED to "busy".

**`_refresh_connection_state()`:** Called once at construction. Enables/disables
all controls based on `motor.is_connected`. Attempts `get_position()` to initialize
the display (failure is silent).

---

### Class: `MotorPanel(QWidget)`

Container that creates one `AxisCard` per connected motor and lays them out
horizontally. Exposes `status_message` signal forwarding messages from each card.

---

## 5. gui/scope_panel.py — Oscilloscope Tab

### Purpose

Continuous waveform acquisition loop with live pyqtgraph display, waveform
statistics table, and CSV recording.

### Class: `ContinuousAcquireWorker(QThread)`

Runs an acquisition loop off the UI thread.

**Constructor:**
```python
ContinuousAcquireWorker(scope, channel, interval_s: float)
```

**Algorithm:**
```
connect if not connected
while running:
    for ch in channels:
        t, v = scope.read_waveform(ch)
    emit data_ready({'CH1': (t,v), 'CH2': (t,v)})
    interruptible_sleep(interval_s)   # checks stop flag every 100ms
```

**Signals:**
- `data_ready(dict)` — `{'CH1': (t_array, v_array), ...}`
- `error(str)`

**`stop()`:** Sets `self._running = False`. The interruptible sleep checks this
flag every 100 ms, so the worker exits within 100 ms of `stop()` being called.

---

### `_save_waveform_csv(ch_key, t, v, output_dir, prefix)` → `Path`

Module-level helper that saves one waveform to a timestamped CSV. Filename format:

```
prefix_CH1_20260520_103045_123.csv
```

The milliseconds (`123`) prevent collisions between rapid saves.

---

### `_make_plot()` → `(PlotWidget, curve_ch1, curve_ch2)`

Creates and configures a `pyqtgraph.PlotWidget` with:
- Black background matching `S.BG_DEEP`
- Orange pen (`S.ACCENT`) for CH1
- Cyan pen (`S.CYAN`) for CH2
- Subtle grid (alpha 0.15)
- Legend

Falls back to a `QLabel` with install instructions if pyqtgraph is not installed.

---

### Class: `ScopePanel(QWidget)`

**Key methods:**

`_update_curves(data)`: Updates plot curve data AND enforces per-channel visibility.
This is the core logic for the channel switcher:
```python
show_ch1 = (ch == 1 or ch == "both")
show_ch2 = (ch == 2 or ch == "both")
curve_ch1.setVisible(show_ch1)
curve_ch2.setVisible(show_ch2)
```
This is called both when new data arrives AND when the user changes the channel
selector mid-acquisition.

`_update_stats(data)`: Computes Vmin, Vmax, Vpp, Vmean, Vrms from the voltage
array and fills the QTableWidget. Columns not in the current acquisition are
cleared to "---".

`_stop_worker()`: Calls `worker.stop()` then `worker.wait(5000)` — waits up to
5 seconds for the thread to exit cleanly before proceeding.

---

## 6. gui/power_panel.py — Power Meter Tab

### Purpose

Continuous power reading loop with a large digital display, statistics cards,
and per-reading CSV recording.

### Class: `ContinuousReadWorker(QThread)`

**Constructor:**
```python
ContinuousReadWorker(pm, wavelength, n_samples, averaging, interval_ms)
```

**Algorithm:**
```
connect if not connected
pm.set_wavelength(wavelength)
pm.set_auto_range(True)

while running:
    stats = pm.read_average(n_samples, averaging)
    emit reading_ready(stats)
    interruptible_sleep(interval_ms)   # 50ms steps
```

**`stats` dict keys:**
`mean_w`, `std_w`, `min_w`, `max_w`, `mean_mw`, `n_samples`, `averaging`

---

### `_save_single_reading(stats, wavelength, output_dir, prefix)` → `Path`

Module-level helper. Saves one reading to a CSV. Millisecond precision in the
filename prevents overwrites from rapid consecutive saves.

---

### Class: `PowerPanel(QWidget)`

**Unit selector:** The `QComboBox` with "mW" / "µW" connects to `_on_unit_changed`.
When changed, `_update_display` is called with the last stored stats (`self._last_stats`),
re-rendering the display and stat cards in the new unit without waiting for the
next reading. Saved CSV files always use Watts regardless of the display unit.

**RECORD mode:** `_on_record_toggle(checked)` sets `self._recording = True/False`.
Inside `_on_reading`, if recording is active, calls `_save_single_reading` for
each new reading. The record counter increments and updates the label.

**`_on_start_stop(checked)`:** Creates a new `ContinuousReadWorker` on START,
calls `_stop_worker()` on STOP. The worker is stored in `self._worker` (instance
variable) to prevent Python garbage collection.

---

## 7. gui/scan_panel.py — Scan Tab (shared base)

The largest panel. Also acts as a **shared module** — `loop_scan_panel.py` and
`photo_current_panel.py` import classes and functions directly from here to avoid
duplication.

**Exported symbols used by other panels:**
```python
from gui.scan_panel import (
    MotionEntry, TriggerRule,          # data classes
    _load_calibration, _um_to_pulses,  # calibration helpers
    MotionRow, TriggerRow,             # UI row widgets
    MeasurementBlock, PathLog,         # composite UI widgets
)
```

### Data Classes

#### `MotionEntry`

Plain data object representing one motion command:

```python
@dataclass
class MotionEntry:
    axis:    str    # 'x', 'y', or 'z'
    pulses:  int    # pulses per step
    speed:   int    # speed in pulse/s (absolute)
    steps:   int    # number of steps
    delay_s: float  # inter-step delay
    forward: bool   # True = forward, False = backward
```

#### `TriggerRule`

Represents one measurement trigger condition:

```python
@dataclass
class TriggerRule:
    kind:         str   # "every_step_any" | "every_step_of" | "last_step_of"
    motion_index: int   # 1-based (used for "every_step_of" and "last_step_of")
    output_dir:   str   # None = use global folder; set = custom folder for this rule
```

**`matches(motion_idx, step, total_steps)`:** Returns True if this rule fires for
the given motion index and step number.

---

### Calibration Functions

#### `_load_calibration()` → `dict`

Returns `{}` — calibration is now provided entirely by `HelpPanel` via signal.
This function exists as a stub so `ScanPanel.__init__` can initialize
`self._calibration` before the signal arrives.

#### `_um_to_pulses(speed, um_target, cal)` → `int | None`

Converts a µm displacement to pulses using `numpy.interp` on the calibration
table for the given speed. Returns `None` if the speed is not calibrated.

```python
# Example: speed=600, um=2.5 → interpolate on the MEAN column → 3500 pulses
pulses = _um_to_pulses(600, 2.5, calibration)
```

---

### Class: `ScanWorker(QThread)`

Executes the full scan sequence off the UI thread.

**Constructor:**
```python
ScanWorker(motors, motions, scope, scope_enabled, scope_cfg,
           pm, pm_enabled, pm_cfg)
```

**`scope_cfg` / `pm_cfg` dict keys:**
- `channel` — 1, 2, or "both"
- `output_dir` — global output folder
- `prefix` — filename prefix
- `triggers` — list of `TriggerRule` objects

**`_matching_rules(cfg, motion_idx, step, total)`:**
Returns the list of `TriggerRule` objects from `cfg["triggers"]` that match
the current position. There may be zero, one, or multiple matching rules.

**Measurement dispatch in `run()`:**
```python
for rule in self._matching_rules(scope_cfg, m_idx, step, motion.steps):
    self._save_scope(m_idx, step, output_dir_override=rule.output_dir)
```

If two rules match with different `output_dir` values, `_save_scope` is called
twice — one file per rule. If `rule.output_dir` is None, the global folder is used.

**`_save_scope(motion_idx, step, output_dir_override=None)`:**
Calls `scope.read_waveform_meta(ch)` to get `(time, voltage, meta)`. The `meta`
dict is written as `# key, value` comment rows at the top of the CSV, followed
by `time_s, voltage_V` data rows. This makes each CSV fully self-contained for
signal reconstruction.

**`_save_pm(motion_idx, step, output_dir_override=None)`:**
Calls `pm.read_average()`, writes timestamp/wavelength/stats to CSV.

**Interruptible sleep:** All waits use:
```python
elapsed = 0.0
while self._running and elapsed < delay:
    self.msleep(100)
    elapsed += 0.1
```
This allows `stop()` to interrupt any delay within 100 ms.

---

### Class: `ReturnHomeWorker(QThread)`

Executes the reverse of a snapshotted motion list.

**Constructor:**
```python
ReturnHomeWorker(motors: dict, snapshot: list[MotionEntry])
```

**Algorithm:**
```python
return_motions = []
for motion in reversed(snapshot):
    return_motions.append(MotionEntry(
        axis    = motion.axis,
        pulses  = motion.pulses,
        speed   = motion.speed,
        steps   = max(1, motion.steps // 2),   # half steps
        delay_s = motion.delay_s,
        forward = not motion.forward,            # reversed direction
    ))

# Execute return_motions sequentially
```

**Backlash compensation:** Using `steps // 2` means the return covers less total
distance per motion than the forward scan. This is intentional — the undershoot
compensates for mechanical backlash in the motor/stage system.

---

### Class: `MotionRow(QFrame)`

Two-line widget representing one scan motion entry.

**Signals:**
- `remove_requested(self)` — user clicked DEL
- `move_up_requested(self)` — user clicked UP
- `move_dn_requested(self)` — user clicked DN

**`_on_speed_changed(speed)`:**
Checks `speed in self._calibration`. If True, shows the µm target spinbox and
calls `_on_um_changed` to pre-compute pulses. If False, hides it.

**`_on_um_changed(um)`:**
Calls `_um_to_pulses(speed, um, self._calibration)`. If a result is found,
updates `self._pulses` spinbox with `blockSignals(True)` to avoid a feedback loop.

**`update_calibration(cal)`:**
Called by `PathLog.update_calibration()` when `HelpPanel` loads new data.
Updates `self._calibration` and re-triggers `_on_speed_changed` to refresh
the µm field visibility for the current speed value.

**`to_motion_entry()`:**
Converts the current widget state to a `MotionEntry` data object.

---

### Class: `TriggerRow(QFrame)`

Two-row widget for one trigger rule.

**Row 1:** Kind dropdown + motion number spinbox (shown/hidden by kind) + Custom
folder checkbox + remove button.

**Row 2:** Folder path input + Browse button (shown/hidden by checkbox).

**`to_trigger_rule()`:**
Returns a `TriggerRule` with `output_dir=None` if the custom checkbox is not
checked, or `output_dir=<path>` if it is.

---

### Class: `MeasurementBlock(QGroupBox)`

Reusable measurement configuration widget. Used once for Oscilloscope and once
for Power Meter.

**Structure:**
```
[✓] Enable
  └── (visible only when enabled)
      Output folder + Browse
      Filename prefix
      [extra_widgets]      ← instrument-specific controls passed in constructor
      ─────────────────
      TRIGGER RULES
      [TriggerRow]
      [TriggerRow]
      [+ Add Trigger]
```

**`extra_widgets`:** A list of QWidgets injected into the settings area. Used to
add channel selector (scope) or wavelength/samples/averaging inputs (PM) without
subclassing.

**Properties:**
- `enabled` → bool (checkbox state)
- `output_dir` → str (folder path)
- `prefix` → str (filename prefix)
- `triggers` → list[TriggerRule] (from all TriggerRows)

---

### Class: `PathLog(QWidget)`

Scrollable list of `MotionRow` widgets.

**`_add_motion()`:** Creates a new `MotionRow`, appends it to `self._motion_rows`,
inserts it before the trailing `addStretch()` in the layout.

**`_swap(i, j)`:** Removes all rows from the layout, swaps them in the list,
re-inserts in new order, then calls `_renumber()`. This is the only reliable way
to reorder widgets in a `QVBoxLayout`.

**`update_calibration(cal)`:** Propagates the new calibration dict to every
existing `MotionRow`, and stores it so future rows get it at creation.

---

### Class: `ScanPanel(QWidget)`

**`_on_set_home()`:**
1. Gets current motions from `self._pathlog.get_motions()`
2. Stores them in `self._home_snapshot`
3. Enables the **Return Home** button
4. Updates the home info label

**`_on_return_home()`:**
1. Creates `ReturnHomeWorker` with `self._home_snapshot`
2. Disables Set Home during return (prevents conflicting snapshots)
3. On completion, re-enables Set Home

**`update_calibration(cal)`:**
Connected to `HelpPanel.calibration_updated`. Updates `self._calibration` and
calls `self._pathlog.update_calibration(cal)`.

**`_set_running(running)`:**
Enables/disables RUN, STOP, and Return Home buttons atomically. Return Home is
only enabled when not running AND a home has been set.

---

## 8. gui/loop_scan_panel.py — Loop Scan Tab

### Purpose

Repeats a PathLog motion sequence N times. Adds two layers on top of `ScanPanel`:
a loop counter with optional pause between cycles, and a **cycle filter** that
controls in which cycles measurements are saved.

All UI building blocks (`PathLog`, `MeasurementBlock`, `MotionRow`, etc.) are
imported from `scan_panel.py` — no duplication.

### `_cycle_matches(cycle, total, mode, every_n, specific)` → `bool`

Module-level function. Returns True if measurements should fire on this cycle.

| `mode` | Logic |
|--------|-------|
| `"every"` | Always True |
| `"every_n"` | `(cycle % every_n) == 1` → cycles 1, 1+N, 1+2N, … |
| `"specific"` | `cycle in specific` (parsed set of integers) |
| `"first_last"` | `cycle == 1 or cycle == total` (or only 1 if infinite) |

### `_parse_specific_cycles(text)` → `Set[int]`

Parses comma-separated values and dash-ranges from user input:
```
"1, 3, 5-8, 10"  →  {1, 3, 5, 6, 7, 8, 10}
```

### Class: `LoopScanWorker(QThread)`

**Constructor:**
```python
LoopScanWorker(motors, motions, n_cycles, pause_s,
               scope, scope_enabled, scope_cfg,
               pm, pm_enabled, pm_cfg,
               cycle_mode, cycle_every_n, cycle_specific)
```

**Signals:**
- `cycle_started(cycle, total)`
- `progress(cycle, total, motion_idx, step, total_steps)`
- `step_done(cycle, total, motion_idx, step, total_steps)`
- `measurement_done(cycle, motion_idx, step, label)`
- `cycle_done(cycle, total)`
- `finished()`
- `error(str)`

**Algorithm:**
```
cycle = 0
while running:
    cycle += 1
    if n_cycles > 0 and cycle > n_cycles: break

    measure_this_cycle = _cycle_matches(cycle, ...)

    for each motion in motions:
        for each step:
            motor.move(...)
            if measure_this_cycle:
                for each matching trigger rule:
                    _save_scope / _save_pm (with per-rule output_dir)
            interruptible_sleep(delay_s)

    interruptible_sleep(pause_s)  ← between cycles
```

**Key detail:** `measure_this_cycle` is evaluated once per cycle at the top of
the cycle loop, not per step. The trigger rules still control per-step/per-motion
granularity within qualifying cycles.

### Class: `CycleFilterWidget(QGroupBox)`

Four radio buttons (mutually exclusive) with dependent widgets:
- **Every cycle** — no extra widget
- **Every N cycles** — `QSpinBox` for N (enabled only when this radio is selected)
- **Specific cycles** — `QLineEdit` for the comma/range list
- **First and last only** — no extra widget

**Properties:**
- `mode` → `str` ("every" | "every_n" | "specific" | "first_last")
- `every_n` → `int`
- `specific_cycles` → `Set[int]` (parsed on read)

### Class: `LoopScanPanel(QWidget)`

**Layout:** Same split as ScanPanel — `PathLog` on left, scrollable settings +
fixed bottom (log + RUN/STOP) on right.

**`update_calibration(cal)`:** Propagates to `PathLog` — connected to
`HelpPanel.calibration_updated` in `main_window.py`.

---

## 9. gui/photo_current_panel.py — Photo Current Tab

### Purpose

Performs a motor scan where at each step the oscilloscope waveform is integrated
over a user-defined time window, producing a **Charge (V·s) vs Position** data
point. Results are plotted live in a floating `QDialog` window.

### `_pulses_to_um(speed, pulses, cal)` → `Optional[float]`

Inverse of `_um_to_pulses`. Given a number of pulses and a speed, returns the
corresponding µm displacement by interpolating the calibration table:
```python
np.interp(pulses, cal[speed]['pulses'], cal[speed]['means'])
```
Returns `None` if the speed is not calibrated.

### `_cycle_color(cycle)` → `str`

Returns a hex color string cycling through 8 predefined colors. Used to give
each cycle a distinct color on the live plot.

### Class: `LivePlotWindow(QDialog)`

Floating `QDialog` (not modal — does not block the main window) showing the
live Charge vs Position plot.

**`add_point(cycle, x, charge)`:** Appends a point to the curve for `cycle`.
If this is the first point for that cycle, creates a new `pyqtgraph` scatter
plot with the cycle's color and adds it to the legend.

**`clear()`:** Removes all curves and resets internal data.

**`update_x_label(label)`:** Updates the horizontal axis label. Called before
each RUN to reflect whether the axis is in µm or step #.

**Window flags:** `Qt.WindowType.Window` — independent window that can be
minimized/maximized separately from the main window.

### Class: `PhotoCurrentWorker(QThread)`

**Constructor:**
```python
PhotoCurrentWorker(motors, motions, n_cycles, pause_s,
                   scope, channel, t_start_s, t_end_s,
                   calibration, scope_enabled, scope_cfg)
```

**Signals:**
- `point_ready(cycle, position, charge)` — one per motor step
- `cycle_started(cycle, total)`
- `cycle_done(cycle, total)`
- `step_info(str)` — log message per step
- `measurement_done(cycle, motion_idx, step, label)` — when waveform CSV is saved
- `finished()` / `error(str)`

**Position tracking logic:**
```python
um_step = _pulses_to_um(motion.speed, motion.pulses, calibration)
is_um   = um_step is not None

if is_um:
    sign      = +1 if motion.forward else -1
    position += sign * um_step
else:
    position += 1   # monotonic step counter
```

The first motion that determines `is_um` sets the axis label for the whole cycle.
If no motion is calibrated, the axis shows step numbers.

**Integration:**
```python
i0 = np.searchsorted(time_arr, t_start_s)
i1 = np.searchsorted(time_arr, t_end_s)
charge = np.trapz(volt_arr[i0:i1], time_arr[i0:i1])   # V·s
```

`numpy.trapz` implements the trapezoidal rule: `∑ (t[i+1]-t[i]) × (v[i]+v[i+1])/2`.

**CSV save:** Same format as `ScanPanel._save_scope` — full metadata header +
`time_s, voltage_V` columns. Filename includes cycle number:
```
photo_c001_m02_s003_CH1_20260522_103045_123.csv
```

### Class: `IntegrationWidget(QGroupBox)`

Compact widget with `t_start`, `t_end` spinboxes and a unit selector (ns/µs/ms/s).
Properties `t_start_s` and `t_end_s` always return values in seconds regardless
of the selected unit.

### Class: `PhotoCurrentPanel(QWidget)`

**`_x_label()`:** Scans the current PathLog motions. Returns `"Position (µm)"`
if any motion speed is in the calibration dict, otherwise `"Step #"`.

**`_ensure_plot_window()`:** Creates or raises `LivePlotWindow`. If the window
was closed, a fresh one is created. Called both by RUN and by the
**Show Plot** button.

**`update_calibration(cal)`:** Connected to `HelpPanel.calibration_updated` —
propagates to `PathLog` so µm target fields appear/disappear correctly.

---

## 10. gui/help_panel.py — Help Tab

### Purpose

Displays the motor speed calibration Excel file as a read-only table. Supports
multiple sheets (one per speed). Emits the calibration data as a signal so other
panels (Scan) can use it.

### Class: `PlotDialog(QDialog)`

Modal popup showing a pyqtgraph plot of Pulses vs MEAN for the selected speed.

**Constructor:**
```python
PlotDialog(speed_title: str, pulses: list, means: list, parent=None)
```

Falls back to a `QLabel` message if pyqtgraph is not installed.

---

### Class: `HelpPanel(QWidget)`

**Signal:**
- `calibration_updated(dict)` — emits `{speed_int: {'pulses': [...], 'means': [...]}}` whenever an Excel file is successfully loaded

This signal is connected in `main_window.py`:
```python
help_panel.calibration_updated.connect(scan_panel.update_calibration)
```

**`_try_autoload()`:**
Called at construction. Reads `CALIBRATION_FILE` from `utils/config.py` and calls
`_load_excel()` if the file exists. This is why the Scan tab has calibration data
available immediately at startup (assuming the file is in the project folder).

**`_load_excel(path)`:**
1. Opens all sheets with `openpyxl`
2. For each sheet: extracts title from row 0, finds header row, extracts data rows
3. Stores everything in `self._sheet_data = {sheet_name: {title, headers, rows}}`
4. Populates the speed dropdown
5. Calls `_build_calibration_dict()` and emits `calibration_updated`

**`_build_calibration_dict()`:**
Converts `self._sheet_data` to the format expected by `ScanPanel`:
- Extracts speed number from title string using regex `r'\d+'`
- Finds the MEAN column by header name
- Returns `{speed_num: {'pulses': [...], 'means': [...]}}`

**`_show_sheet(sheet_name)`:**
Populates the `QTableWidget` from the stored `_sheet_data`. Applies color
highlights: first column (Pulses) in cyan, MEAN column in amber bold.

---

## 11. Threading Model

All long-running operations use `QThread` workers. This keeps the UI responsive
at all times.

### Worker pattern (every worker follows this)

```python
class MyWorker(QThread):
    finished = pyqtSignal(...)
    error    = pyqtSignal(str)

    def __init__(self, ...):
        super().__init__()
        self._running = False

    def stop(self):
        self._running = False   # signals the loop to exit

    def run(self):
        self._running = True
        try:
            # ... work ...
            self.finished.emit(result)
        except Exception as exc:
            self.error.emit(str(exc))
```

### Rule: always store workers as instance variables

```python
# CORRECT — worker kept alive by self._worker
self._worker = MyWorker(...)
self._worker.finished.connect(self._on_done)
self._worker.start()

# WRONG — Python may garbage-collect 'worker' before it finishes
worker = MyWorker(...)
worker.start()
# → "QThread: Destroyed while thread '' is still running"
```

### Interruptible sleep

For loops that need to wait but also respond to `stop()`:

```python
elapsed = 0.0
while self._running and elapsed < target_seconds:
    self.msleep(100)
    elapsed += 0.1
```

This guarantees exit within 100 ms of `stop()` being called, regardless of
how long the target sleep is.

### Stopping a worker safely

```python
def _stop_worker(self):
    if self._worker is not None:
        self._worker.stop()
        self._worker.wait(5000)   # wait up to 5 seconds
```

Never call `self._worker.terminate()` — it kills the thread without cleanup
and can leave instruments in undefined states.

---

## 12. Signal and Slot Map

Key connections between objects at application level (set up in `main_window.py`):

```
HelpPanel.calibration_updated  →  ScanPanel.update_calibration
                               →  LoopScanPanel.update_calibration
                               →  PhotoCurrentPanel.update_calibration
                                     └→ PathLog.update_calibration (each)
                                            └→ MotionRow.update_calibration (×N)

ReconnectWorker.progress       →  MainWindow._set_status
ReconnectWorker.finished       →  MainWindow._on_reconnect_done
                                     └→ updates StatusLEDs

MotorPanel.status_message      →  MainWindow._set_status
ScopePanel.status_message      →  MainWindow._set_status
PowerPanel.status_message      →  MainWindow._set_status
ScanPanel.status_message       →  MainWindow._set_status
LoopScanPanel.status_message   →  MainWindow._set_status
PhotoCurrentPanel.status_message → MainWindow._set_status
```

Within each panel:

```
# Motor panel
MoveWorker.step_done     →  AxisCard._on_step_done    (updates position display)
MoveWorker.finished      →  AxisCard._on_move_done    (re-enables buttons)
MoveWorker.error         →  AxisCard._on_error        (shows error, re-enables)
HomeWorker.finished      →  AxisCard._on_home_done    (resets position to 0)

# Scope panel
ContinuousAcquireWorker.data_ready  →  ScopePanel._on_data_ready
                                           ├→ _update_curves (plot)
                                           └→ _update_stats  (table)

# Power meter panel
ContinuousReadWorker.reading_ready  →  PowerPanel._on_reading
                                           ├→ _update_display
                                           └→ _save_single_reading (if recording)

# Scan panel
ScanWorker.progress          →  ScanPanel._on_progress
ScanWorker.step_done         →  ScanPanel._on_step_done
ScanWorker.measurement_done  →  ScanPanel._on_measurement_done
ScanWorker.finished          →  ScanPanel._on_finished
ScanWorker.error             →  ScanPanel._on_error

ReturnHomeWorker.progress    →  ScanPanel (lambda → _log_msg)
ReturnHomeWorker.finished    →  ScanPanel._on_return_home_done
ReturnHomeWorker.error       →  ScanPanel._on_error

# Loop Scan panel
LoopScanWorker.cycle_started    →  LoopScanPanel._on_cycle_started
LoopScanWorker.progress         →  LoopScanPanel._on_progress
LoopScanWorker.step_done        →  LoopScanPanel._on_step_done
LoopScanWorker.measurement_done →  LoopScanPanel._on_measurement_done
LoopScanWorker.cycle_done       →  LoopScanPanel._on_cycle_done
LoopScanWorker.finished         →  LoopScanPanel._on_finished
LoopScanWorker.error            →  LoopScanPanel._on_error

# Photo Current panel
PhotoCurrentWorker.point_ready      →  PhotoCurrentPanel._on_point_ready
                                           └→ LivePlotWindow.add_point
PhotoCurrentWorker.cycle_started    →  PhotoCurrentPanel._on_cycle_started
PhotoCurrentWorker.cycle_done       →  PhotoCurrentPanel._on_cycle_done
PhotoCurrentWorker.step_info        →  PhotoCurrentPanel._log_msg
PhotoCurrentWorker.measurement_done →  PhotoCurrentPanel (lambda → _log_msg)
PhotoCurrentWorker.finished         →  PhotoCurrentPanel._on_finished
PhotoCurrentWorker.error            →  PhotoCurrentPanel._on_error
```
