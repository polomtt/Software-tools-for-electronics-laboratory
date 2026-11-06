# Lab Control System — Instrument Communication Reference

**Instruments covered:**
- Opto Sigma SRC-101 (motor controller) × 3
- Tektronix MDO3102 (oscilloscope)
- Thorlabs PM100D (power meter)

---

## Table of Contents

1. [Communication Stack Overview](#1-communication-stack-overview)
2. [PyVISA — The Common Layer](#2-pyvisa--the-common-layer)
3. [Opto Sigma SRC-101 — Motor Controller](#3-opto-sigma-src-101--motor-controller)
4. [Tektronix MDO3102 — Oscilloscope](#4-tektronix-mdo3102--oscilloscope)
5. [Thorlabs PM100D — Power Meter](#5-thorlabs-pm100d--power-meter)
6. [Timing and Synchronization](#6-timing-and-synchronization)
7. [Error Handling Strategy](#7-error-handling-strategy)
8. [VISA Address Reference](#8-visa-address-reference)

---

## 1. Communication Stack Overview

The application communicates with all three instruments through **PyVISA**, a
Python library that provides a uniform API regardless of the underlying physical
connection. The physical connections differ per instrument:

```
┌─────────────────────────────────────────────────────────────┐
│                        app.py / GUI                         │
├─────────────────────────────────────────────────────────────┤
│              core/motor.py  |  core/oscilloscope.py         │
│                             |  core/power_meter.py          │
├─────────────────────────────────────────────────────────────┤
│                    PyVISA (pyvisa)                          │
│              ResourceManager + Resource objects             │
├───────────────────┬─────────────────────────────────────────┤
│    NI-VISA DLL    │         pyvisa-py (pure Python)         │
│  (ni-visa.dll)    │    (used as fallback, not recommended)  │
├────────┬──────────┴─────────────────────────────────────────┤
│ Serial │              USB-TMC                               │
│ RS-232 │   (USB Test & Measurement Class — standard USB)    │
├────────┴────────────────────────────────────────────────────┤
│  SRC-101 (×3)  │  MDO3102 oscilloscope  │ PM100D power meter│
└────────────────┴────────────────────────┴───────────────────┘
```

**Key point:** All three instruments speak **SCPI** (Standard Commands for
Programmable Instruments) — a standardized command language defined by IEEE 488.2.
The SRC-101 uses a proprietary command dialect instead of full SCPI, but the
transport layer (PyVISA) is the same.

---

## 2. PyVISA — The Common Layer

### What PyVISA does

PyVISA is an abstraction layer that wraps the National Instruments VISA library
(NI-VISA). It provides a single Python API (`open_resource`, `write`, `query`,
`read`) that works identically whether the instrument is connected via:
- USB (USB-TMC class)
- Serial port (RS-232/RS-485)
- GPIB (IEEE-488)
- Ethernet (LXI/VXI-11)

### ResourceManager

The `ResourceManager` is the entry point. It holds the VISA session and manages
all open resources:

```python
import pyvisa
rm = pyvisa.ResourceManager()   # loads NI-VISA DLL
```

In the application, each instrument class creates its own `ResourceManager` in
`__init__`. For the motors, one ResourceManager is created per axis (because each
axis is a separate serial port with its own connection lifecycle).

### Opening a resource

```python
dev = rm.open_resource("USB0::0x0699::0x0408::C019950::INSTR")
```

This returns a `Resource` object with methods:
- `write(cmd)` — sends a command string, no response expected
- `query(cmd)` — sends a command and reads the response (write + read in one call)
- `read()` — reads a pending response
- `query_binary_values(cmd, ...)` — reads binary data (used for oscilloscope waveforms)
- `close()` — releases the VISA session

### Termination characters

Every instrument needs to know where a command ends. This is configured via:

```python
dev.read_termination  = '\r\n'   # what to append when reading
dev.write_termination = '\r\n'   # what to append when writing
```

The SRC-101 uses `\r\n` (carriage return + newline).
The MDO3102 and PM100D use `\n` by default (VISA handles it automatically for USB-TMC).

### Timeout

```python
dev.timeout = 10_000   # milliseconds
```

If a `query()` does not receive a response within this time, PyVISA raises
`pyvisa.errors.VisaIOError`. All instruments in this application use 10 seconds,
which is conservative but safe for slow operations like waveform transfer.

---

## 3. Opto Sigma SRC-101 — Motor Controller

### Physical Connection

The SRC-101 connects via **RS-232 serial**, typically through a USB-to-serial
adapter. Windows assigns it a COM port (e.g. COM3, COM4, COM5), which VISA
addresses as `ASRL3::INSTR`, `ASRL4::INSTR`, `ASRL5::INSTR` respectively.

```
PC (USB port)
    │
    └── USB-to-serial adapter (FTDI or similar)
            │
            └── RS-232 cable (DB9)
                    │
                    └── SRC-101 RS-232 port
```

### Serial Port Parameters

These must match exactly what the SRC-101 expects:

| Parameter | Value |
|-----------|-------|
| Baud rate | 38400 |
| Data bits | 8 |
| Stop bits | 1 |
| Parity | None |
| Flow control | None |

Configured in `motor.py`:
```python
self._inst = self._rm.open_resource(
    self.address,
    baud_rate    = 38400,
    data_bits    = 8,
    stop_bits    = pyvisa.constants.StopBits.one,
    parity       = pyvisa.constants.Parity.none,
    flow_control = pyvisa.constants.ControlFlow.none,
)
self._inst.read_termination  = '\r\n'
self._inst.write_termination = '\r\n'
self._inst.timeout           = 2000   # 2 seconds
```

### Buffer Flushing at Connection

After opening the serial port, stale bytes may remain in the input buffer from a
previous session. The application attempts to flush them:

```python
try:
    self._inst.flush(pyvisa.constants.VI_IO_IN_BUF_DISCARD)
except Exception:
    pass   # not all backends support flush — safe to ignore
```

A `time.sleep(0.1)` follows to let the port stabilize.

### Command Language

The SRC-101 uses a proprietary ASCII command language. Commands are sent as
strings; the controller responds with acknowledgements or data.

#### Speed Setting — `D:` command

```
D:1S0F{speed}R0
```

| Token | Meaning |
|-------|---------|
| `D:` | Set drive parameters |
| `1` | Axis 1 (the SRC-101 is single-axis; always 1) |
| `S0` | Start speed = 0 pulse/s (ramp from zero) |
| `F{speed}` | Final (maximum) speed in pulse/s |
| `R0` | Ramp rate = 0 (no ramping; immediate full speed) |

Example — set speed to 5000 pulse/s:
```
D:1S0F5000R0
```

#### Relative Move — `M:` command

```
M:1{direction}P{pulses}
```

| Token | Meaning |
|-------|---------|
| `M:` | Set motion parameters |
| `1` | Axis 1 |
| `{direction}` | `+` for forward, `-` for backward |
| `P{pulses}` | Number of pulses (integer) |

Example — move 1000 pulses forward:
```
M:1+P1000
```

Example — move 500 pulses backward:
```
M:1-P500
```

#### Execute — `G:` command

```
G:
```

Sends the previously loaded motion command. The `M:` command only loads parameters;
`G:` triggers actual movement. This two-step approach allows setting up a motion
before committing to it.

#### Complete move sequence

```python
self._write(f"D:1S0F{abs_speed}")   # 1. Set speed
self._write(f"M:1{direction}P{pulses}")  # 2. Load motion
self._write("G:")                    # 3. Execute
```

#### Status Query — `Q:` command

```
Q:
```

Response format:
```
{position},{unknown},{unknown},{status}
```

Example response:
```
1000,0,0,R
```

| Field | Meaning |
|-------|---------|
| Field 0 | Current position in pulses (signed integer) |
| Field 1 | Reserved |
| Field 2 | Reserved |
| Field 3 | `R` = Ready (motor stopped), `B` = Busy (motor moving) |

The application polls this response to implement `wait_ready()`:

```python
def wait_ready(self, poll_interval=0.1):
    while True:
        status = self.get_status()
        if status['ready']:
            break
        time.sleep(poll_interval)
```

**Robust parsing** — the application strips non-numeric characters before
converting position to integer, to handle any unexpected formatting:

```python
try:
    clean    = ''.join(c for c in parts[0] if c.isdigit() or c in '+-')
    position = int(clean) if clean else 0
except (ValueError, IndexError):
    position = 0
```

#### Home — `H:` command

```
H:1
G:
```

Sends the axis to its mechanical origin (limit switch). The application then calls
`wait_ready()` to block until homing is complete.

#### Stop — `L:` command

```
L:1
```

Decelerates and stops the motor immediately.

### Full Move Sequence (with timing)

```
PC                              SRC-101
 │                                 │
 │── D:1S0F5000\r\n ──────────────▶│  set speed
 │                                 │  (processes, ~50ms)
 │── M:1+P1000\r\n ───────────────▶│  load motion
 │                                 │  (processes, ~50ms)
 │── G:\r\n ──────────────────────▶│  execute
 │                                 │  (motor starts moving)
 │                                 │
 │── Q:\r\n ──────────────────────▶│  poll status
 │◀── 500,0,0,B\r\n ───────────────│  still busy
 │                                 │  (wait 100ms)
 │── Q:\r\n ──────────────────────▶│  poll status
 │◀── 1000,0,0,R\r\n ──────────────│  ready — motion complete
 │                                 │
```

### Inter-command Delay

A `time.sleep(0.05)` is inserted after every `_write()` call. This is required
because the SRC-101 cannot process commands faster than its internal processing
cycle. Without this delay, commands can be lost or misinterpreted.

```python
def _write(self, cmd: str):
    self._inst.write(cmd)
    time.sleep(0.05)   # 50ms — mandatory for SRC-101
```

---

## 4. Tektronix MDO3102 — Oscilloscope

### Physical Connection

The MDO3102 connects via **USB-TMC** (USB Test and Measurement Class). This is a
standardized USB device class — the PC communicates with it like a VISA instrument
without needing a custom driver. Windows identifies it using the Tektronix vendor ID.

```
PC (USB port)
    │
    └── USB-A to USB-B cable
            │
            └── MDO3102 rear USB Device port
```

### VISA Address Format

```
USB0::0x0699::0x0408::C019950::INSTR
         │        │        │
         │        │        └── Serial number (unique per unit)
         │        └── Product ID (0x0408 = MDO3000 series)
         └── Vendor ID (0x0699 = Tektronix)
```

### Protocol: SCPI over USB-TMC

SCPI (Standard Commands for Programmable Instruments) is a text-based command
language. Commands follow the colon-separated hierarchy convention:

```
INSTRUMENT:SUBSYSTEM:COMMAND? [parameter]
```

The `?` suffix makes a command a query (expects a response).

### Connection and Initial Setup

```python
dev = rm.open_resource(address)
dev.timeout = 10_000   # 10 seconds — needed for long waveform transfers

# Set binary encoding ONCE at connection time
dev.write("DATA:ENCdg RIBinary")   # raw binary, signed integers
dev.write("DATA:WIDTH 2")          # 2 bytes per sample = int16
```

Setting encoding once at connection (rather than before each acquisition) reduces
overhead during continuous acquisition.

### Identification — `*IDN?`

```python
idn = dev.query("*IDN?")
# Returns: "TEKTRONIX,MDO3102,C019950,CF:91.1CT FV:v1.14"
```

Format: `MANUFACTURER,MODEL,SERIAL,FIRMWARE`

### Waveform Acquisition — Full Sequence

#### Step 1: Select source channel

```python
dev.write(f"DATA:SOURCE CH{channel}")   # CH1 or CH2
```

#### Step 2: Read the waveform preamble

The preamble contains the scaling parameters needed to convert raw integer samples
to real physical units (seconds and volts).

```python
x_incr = float(dev.query("WFMOUTPRE:XINCR?"))   # time between samples (seconds)
x_zero = float(dev.query("WFMOUTPRE:XZERO?"))   # time of first sample (seconds)
y_mult = float(dev.query("WFMOUTPRE:YMULT?"))   # voltage per raw unit (V/count)
y_off  = float(dev.query("WFMOUTPRE:YOFF?"))    # offset in raw counts
y_zero = float(dev.query("WFMOUTPRE:YZERO?"))   # voltage offset (volts)
```

| Parameter | Typical value | Meaning |
|-----------|--------------|---------|
| `XINCR` | `1e-9` | 1 ns between samples → 1 GSa/s |
| `XZERO` | `-5e-6` | waveform starts at -5 µs |
| `YMULT` | `1e-4` | 0.1 mV per raw count |
| `YOFF` | `0.0` | no raw offset |
| `YZERO` | `0.0` | no voltage offset |

Additional metadata queries for the CSV header:

```python
x_unit  = dev.query("WFMOUTPRE:XUNIT?")   # typically "s"
y_unit  = dev.query("WFMOUTPRE:YUNIT?")   # typically "V"
ch_scale = dev.query(f"CH{ch}:SCALE?")    # V/div on screen
h_scale  = dev.query("HORIZONTAL:SCALE?") # s/div on screen
```

#### Step 3: Read raw sample data

```python
raw = dev.query_binary_values(
    "CURVE?",
    datatype     = 'h',    # 'h' = signed 16-bit integer (int16)
    is_big_endian = True,  # Tektronix sends big-endian by default
)
raw = np.array(raw, dtype=np.int16)
```

`CURVE?` triggers the actual data transfer. The oscilloscope sends a binary block:
```
#<N><NNNN><raw bytes>
│    │      └── actual int16 sample data
│    └── N digits specifying byte count
└── '#' marks the start of a binary block
```

PyVISA's `query_binary_values` handles the binary block header automatically.

#### Step 4: Convert to physical units

```python
voltage_v = (raw - y_off) * y_mult + y_zero
time_s    = np.arange(len(raw)) * x_incr + x_zero
```

**Voltage conversion formula:**
```
V[i] = (raw[i] - YOFF) × YMULT + YZERO
```

This is the standard Tektronix conversion formula. `YOFF` removes the digital
offset, `YMULT` scales to volts, `YZERO` adds the analog zero reference.

**Time array:**
```
t[i] = i × XINCR + XZERO
```

A simple linear ramp starting at `XZERO` with spacing `XINCR`.

#### Complete timing diagram

```
PC                                  MDO3102
 │                                     │
 │── DATA:SOURCE CH1\n ───────────────▶│
 │── WFMOUTPRE:XINCR?\n ──────────────▶│
 │◀── 1.000000e-09\n ──────────────────│
 │── WFMOUTPRE:XZERO?\n ──────────────▶│
 │◀── -5.000000e-06\n ─────────────────│
 │   [... 3 more preamble queries ...]  │
 │                                     │
 │── CURVE?\n ────────────────────────▶│  (triggers transfer)
 │                                     │  (oscilloscope prepares binary block)
 │◀── #520000<20000 bytes of int16> ───│  (10000 samples × 2 bytes each)
 │                                     │
```

Typical transfer time for 10,000 samples: **50–200 ms** depending on USB speed.

### Acquisition Control Commands

| Command | Effect |
|---------|--------|
| `ACQuire:STATE RUN` | Start continuous acquisition |
| `ACQuire:STATE STOP` | Freeze the display |
| `ACQuire:STATE SEQuence` | Single acquisition (wait for one trigger) |

These are not used during normal waveform reading (the application reads whatever
is currently on screen), but are available in `oscilloscope.py` for future use.

### Why Binary Instead of ASCII?

The MDO3102 can also return waveform data as ASCII numbers
(`DATA:ENCdg ASCIi`). ASCII is human-readable but much slower:
- **ASCII:** `"0.001234, 0.001235, ..."` — ~11 bytes per sample
- **Binary int16:** 2 bytes per sample → **5.5× smaller, proportionally faster**

For a 10,000-sample waveform at 1 GSa/s:
- ASCII: ~110 KB transfer
- Binary: ~20 KB transfer

The application always uses binary (`RIBinary` = Raw Integer Binary, signed).

---

## 5. Thorlabs PM100D — Power Meter

### Physical Connection

The PM100D connects via **USB-TMC**, identical to the oscilloscope.

```
PC (USB port)
    │
    └── USB cable (type A to type B mini)
            │
            └── PM100D USB port
```

### VISA Address Format

```
USB0::0x1313::0x8078::P0040580::INSTR
         │        │        │
         │        │        └── Serial number
         │        └── Product ID (0x8078 = PM100D)
         └── Vendor ID (0x1313 = Thorlabs)
```

### Auto-Detection

The PM100D can be found automatically by scanning all VISA resources for the
Thorlabs vendor ID `0x1313`:

```python
for addr in rm.list_resources():
    if "1313" in addr:
        return addr   # found by vendor ID
```

If the vendor ID check fails (rare), a fallback scans all USB resources and
queries `*IDN?` looking for "THORLABS" or "PM100" in the response.

### Protocol: SCPI over USB-TMC

Like the oscilloscope, the PM100D uses SCPI. The command set follows the
IVI-COM Power Meter standard.

### Identification — `*IDN?`

```python
idn = dev.query("*IDN?")
# Returns: "Thorlabs,PM100D,P0040580,2.8.1"
```

Format: `MANUFACTURER,MODEL,SERIAL,FIRMWARE`

### Sensor Information

```python
sensor_info = dev.query("SYST:SENS:IDN?")
# Returns: "S130C,00123456,20220101,0.1 to 10 mW, Si, Photodiode"
```

This identifies the head attached to the PM100D (sensor model, serial, date,
power range, detector type).

### Wavelength Calibration

The PM100D applies a wavelength-dependent responsivity correction. Before
measuring, set the wavelength to match the light source:

```python
dev.write(f"SENS:CORR:WAV {wavelength_nm}")   # set calibration wavelength
wl = dev.query("SENS:CORR:WAV?")              # read back current wavelength
```

Range: typically 200–1800 nm (depends on sensor head). At incorrect wavelengths,
readings will be systematically off by the responsivity error.

### Range Setting

```python
# Auto-range (recommended for most use cases)
dev.write("SENS:POW:RANG:AUTO ON")

# Manual range (for faster readings when signal level is stable)
dev.write("SENS:POW:RANG:AUTO OFF")
dev.write(f"SENS:POW:RANG {range_watts}")   # e.g. "SENS:POW:RANG 0.001" for 1 mW range
```

Auto-range is always used in this application to handle signal variations.

### Hardware Averaging

The PM100D can average multiple internal measurements before returning a result:

```python
dev.write(f"SENS:AVER:COUNT {count}")   # 1–300 internal averages
```

Higher count = slower but less noisy readings. At count=1, the PM100D returns
individual photodiode samples. At count=100, it returns the average of 100 samples.

**Typical response times:**
- `count=1`: ~5 ms per reading
- `count=10`: ~50 ms per reading
- `count=100`: ~500 ms per reading

### Single Power Measurement

```python
power_w = float(dev.query("MEAS:POW?"))
```

Returns power in Watts. The `MEAS:` prefix means "measure immediately" — it
triggers a fresh acquisition and waits for the result.

**Full measurement sequence:**
```
PC                              PM100D
 │                                 │
 │── SENS:CORR:WAV 1550\n ────────▶│  set wavelength to 1550 nm
 │── SENS:POW:RANG:AUTO ON\n ─────▶│  enable auto-range
 │── SENS:AVER:COUNT 10\n ────────▶│  set 10 internal averages
 │                                 │
 │── MEAS:POW?\n ─────────────────▶│  trigger measurement
 │                                 │  (waits ~50ms for 10 averages)
 │◀── 1.23456789E-03\n ────────────│  returns 1.23 mW in Watts
```

### Software Averaging (`read_average`)

Beyond hardware averaging, the application takes multiple consecutive readings
and computes statistics:

```python
def read_average(self, n_samples=10, averaging=1):
    self.set_averaging(averaging)   # set hardware averaging
    samples = np.array([
        float(self._dev.query("MEAS:POW?"))
        for _ in range(n_samples)
    ])
    return {
        "mean_w"   : float(samples.mean()),
        "std_w"    : float(samples.std()),
        "min_w"    : float(samples.min()),
        "max_w"    : float(samples.max()),
        "mean_mw"  : float(samples.mean() * 1000),
        "n_samples": n_samples,
        "averaging": averaging,
    }
```

**Two levels of averaging:**
1. **Hardware** (`averaging` parameter): PM100D internal signal processing
2. **Software** (`n_samples` parameter): Python-level statistics over multiple queries

Example: `n_samples=10, averaging=5` → 10 queries × 5 internal averages = 50 total
photodiode samples, returning mean, std, min, max.

---

## 6. Timing and Synchronization

### Motor: Blocking vs Non-blocking

The SRC-101 `G:` command is **fire-and-forget** — the controller starts moving
immediately and does not hold the serial port. The application must poll `Q:` to
detect completion.

`move(wait=True)` (default) polls until `R` (Ready) is returned:
```python
while True:
    if self.get_status()['ready']:
        break
    time.sleep(0.1)   # 100ms polling interval
```

`move(wait=False)` returns immediately after `G:` — useful for non-blocking
use cases (not currently used in the GUI, but available).

### Oscilloscope: Synchronous Transfer

`query_binary_values("CURVE?")` is fully synchronous — it blocks until the entire
waveform binary block is received. Transfer time varies with record length and USB
speed, typically 50–500 ms. This is why waveform acquisition runs in a `QThread`
worker — blocking the UI thread for 500 ms would make the interface unresponsive.

### Power Meter: Query Latency

Each `MEAS:POW?` query takes approximately `averaging × 5 ms`. For the default
`averaging=5`, each query takes ~25 ms. For `n_samples=10`, a full `read_average`
call takes ~250 ms.

### Scan Panel: Sequential Execution

In the Scan and Loop Scan panels, the `ScanWorker` / `LoopScanWorker` executes
motions strictly sequentially:

```
Motion 1, Step 1:
    motor.move(wait=True)       ← blocks until motor stops
    [trigger check]
    scope.read_waveform_meta()  ← blocks until transfer complete
    pm.read_average()           ← blocks until all samples done
    time.sleep(delay_s)         ← optional inter-step delay
Motion 1, Step 2:
    ...
```

### Photo Current Panel: Waveform Integration

The `PhotoCurrentWorker` reads the oscilloscope at every motor step and immediately
integrates the waveform before moving to the next step:

```
for each step:
    motor.move(wait=True)
    t, v, meta = scope.read_waveform_meta(channel)   ← full USB transfer
    charge = np.trapz(v[i0:i1], t[i0:i1])            ← integration in Python
    emit point_ready(cycle, position, charge)          ← updates live plot
    [optional: save waveform CSV]
```

The integration itself (`numpy.trapz`) takes microseconds. The bottleneck is
always the oscilloscope USB transfer (~50–500 ms per waveform).

---

## 7. Error Handling Strategy

### Motor errors

Serial communication errors manifest as:
- `pyvisa.errors.VisaIOError` — timeout (motor not responding)
- `ValueError` in `get_status()` — unexpected response format

The application wraps `get_position()` in a try/except:
```python
try:
    pos = self._motor.get_position()
    self.finished.emit(str(pos))
except Exception:
    self.finished.emit("?")   # show "?" instead of crashing
```

The `get_status()` parser is also defensive:
```python
try:
    clean    = ''.join(c for c in parts[0] if c.isdigit() or c in '+-')
    position = int(clean) if clean else 0
except (ValueError, IndexError):
    position = 0   # default to 0 on parse failure
```

### Oscilloscope errors

USB-TMC errors manifest as:
- `pyvisa.errors.VisaIOError` — timeout (instrument busy or disconnected)
- `ValueError` — malformed binary block header

All acquisition workers catch any exception and emit `error(str)`:
```python
except Exception as exc:
    self.error.emit(str(exc))
```

The GUI then displays the error message and stops the acquisition loop.

### Power meter errors

Same pattern as oscilloscope. `MEAS:POW?` can fail if:
- The instrument is in a fault state (overload)
- The USB connection was interrupted
- The wavelength is outside the sensor's range

### Reconnection

If an instrument disconnects mid-session, the **Reconnect All** button in the
status bar attempts to reopen the VISA connection without restarting the app:

```python
# Close only the VISA handle (not the ResourceManager)
if motor.is_connected:
    motor._inst.close()
    motor._inst = None

# Reopen the connection
motor.connect()
```

This approach preserves the `ResourceManager` instance (which holds the NI-VISA
DLL session) and only reopens the instrument handle. Calling `motor.disconnect()`
would also close the ResourceManager, making `connect()` fail.

---

## 8. VISA Address Reference

### Address formats

| Connection type | Format | Example |
|----------------|--------|---------|
| Serial (RS-232) | `ASRL{N}::INSTR` | `ASRL3::INSTR` |
| USB-TMC | `USB{bus}::0x{VID}::0x{PID}::{serial}::INSTR` | `USB0::0x0699::0x0408::C019950::INSTR` |
| GPIB | `GPIB{bus}::{address}::INSTR` | `GPIB0::24::INSTR` |
| Ethernet | `TCPIP::{ip}::INSTR` | `TCPIP::192.168.1.10::INSTR` |

### Vendor IDs

| Manufacturer | Vendor ID | Notes |
|-------------|-----------|-------|
| Tektronix | `0x0699` | All Tektronix instruments |
| Thorlabs | `0x1313` | All Thorlabs USB instruments |
| Opto Sigma / SRC-101 | N/A | Serial only — no vendor ID |

### Product IDs (known)

| Instrument | Product ID |
|-----------|-----------|
| MDO3102 (and MDO3000 series) | `0x0408` |
| PM100D | `0x8078` |
| PM100USB | `0x8072` |

### How to find addresses on your system

With all instruments connected and powered on:

```python
import pyvisa
rm = pyvisa.ResourceManager()
resources = rm.list_resources()
print(resources)
# ('ASRL3::INSTR', 'ASRL4::INSTR', 'ASRL5::INSTR',
#  'USB0::0x0699::0x0408::C019950::INSTR',
#  'USB0::0x1313::0x8078::P0040580::INSTR')
```

To identify which serial port is which motor axis, temporarily disconnect one
axis and run `list_resources()` again — the missing address is that axis.

The USB addresses include the serial number, so they remain stable across reboots
(unlike serial ports, which can change COM number if plugged into different USB
ports).

### config.py mapping

```python
# utils/config.py

# Serial ports — COM3/4/5 map to ASRL3/4/5
MOTOR_1_ADDRESS = "ASRL3::INSTR"   # Z axis (COM3)
MOTOR_2_ADDRESS = "ASRL4::INSTR"   # X axis (COM4)
MOTOR_3_ADDRESS = "ASRL5::INSTR"   # Y axis (COM5)

# USB-TMC — identified by serial number
OSCILLOSCOPE_ADDRESS = "USB0::0x0699::0x0408::C019950::INSTR"
# PM100D is auto-detected by vendor ID 0x1313 — no address needed in config
```

The PM100D does not need an entry in `config.py` because `power_meter.py` scans
`list_resources()` automatically and identifies it by vendor ID.
