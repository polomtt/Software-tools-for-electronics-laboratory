# I-V Characterization Script Guide (SMU via PyVISA)

The script applies a voltage ramp to a sample through a Source-Measure Unit (SMU) connected over the network, measures the current at each step, saves the data to a text file and produces the I-V plot.

---

# PART 1 – BASIC GUIDE

## 1. Getting started

- Open a terminal and type:
  ` conda activate `

## 2. What the script does, in brief

1. Connects to the instrument and prints its name (`*IDN?`).
2. Sets the source to voltage mode and sets the current limit.
3. Turns the output on.
4. Runs the voltage ramp in small steps, measuring the current at each step.
5. Turns the output off, resets the instrument and disconnects.
6. Saves the data (`.txt`) and the plot (`.png`) in the `Data/` folder.

## 3. Parameters to edit

They are located in the block between the `Parameters` and `STOP` comments. **Do not modify anything below the `STOP` line.**

| Parameter | Unit | What it does | Example |
|---|---|---|---|
| `step_voltage` | V | Size of each voltage step. Smaller = denser curve but longer measurement. | `0.05` |
| `V_set` | V | Maximum voltage (in absolute value) reached by the ramp. | `0.5` |
| `double_polarity` | `True` / `False` | `False`: positive polarity only. `True`: positive first, then negative. | `True` |
| `current_compliance` | A | Safety current limit: the instrument will not deliver more than this value. | `1e-3` (1 mA) |
| `delay_new_step` | s | Wait time after each step, before the next one. Allows the sample to stabilize. | `0.5` |
| `sample_name` | text | Sample name: it becomes part of the output file names. | `"GelMA-2PEDOT_2"` |

### What `double_polarity` does

- `False`: `0 → +V_set → 0`
- `True`: `0 → +V_set → 0 → −V_set → 0`

## 4. Step-by-step procedure

1. **Connect the sample** to the instrument and check the contacts.
2. **Set `current_compliance`** to a value suitable for the sample (see tips below).
3. **Set a different `sample_name`** for each sample/measurement, so you can recognize the files.
4. Set `V_set`, `step_voltage`, `delay_new_step`, `double_polarity`.
5. Check that the `Data/` folder exists next to the script.
6. Run the script:
   ```bash
   python set_voltage.py
   ```
7. During the measurement the terminal prints one line per point: `time[s], voltage[V], current[A]`.
8. At the end `done :)` appears and the plot opens. **Close the plot window** to terminate the program.

## 5. Common problems

| Symptom | Likely cause | What to do |
|---|---|---|
| `VisaIOError` / timeout when connecting | Wrong IP, instrument off or not on the network, another program connected to the instrument | Check the network and the IP (see advanced part, section A.1), close other control software |
| `FileNotFoundError: Data/...` | The `Data` folder does not exist | Create it next to the script |
| `ModuleNotFoundError` | Missing package | `pip install pyvisa matplotlib numpy` |
| Current flat at a fixed value | Compliance reached | Increase `current_compliance` (with caution) or reduce `V_set` |
| Very noisy / quantized current | Measuring very small currents with a fixed range that is too large | See advanced part, section B.1 |
| The program seems "stuck" at the end of the measurement | The plot window is open | Close the plot window |

## 6. Output files

In the `Data/` folder you will find two files with the same base name:

- `<sample_name>_<YYYYMMDD_HHMMSS>.txt` – raw data (CSV).
- `<sample_name>_<YYYYMMDD_HHMMSS>.png` – current vs voltage plot.

The `.txt` file has the header `#time[s],voltage[V],current[A]` and opens easily in Excel, Origin, Python (`np.loadtxt(..., delimiter=",")`), etc.

---

# PART 2 – ADVANCED GUIDE

## A. Code structure

### A.1 Instrument settings (below `STOP`)

```python
instrument_resource_string = "TCPIP::10.196.31.73::inst0::INSTR"
```

This is the VISA address of the instrument (TCPIP protocol, IP address, `inst0`). Change it **only** if the instrument or its IP changes. The code contains a commented-out line with an alternative IP: useful if you work with two instruments.

To discover the visible instruments:

```python
import pyvisa
print(pyvisa.ResourceManager().list_resources())
```

### A.2 Service functions

| Function | Role |
|---|---|
| `instrument_connect(...)` | Opens the VISA resource, sets the `timeout` and the `\n` terminators, and optionally runs `*IDN?`, `*RST`, `clear()`. In the current call: timeout 10000 ms, ID query enabled, reset and clear disabled. |
| `instrument_write / read / query` | Wrappers around `write`, `read`, `query`. With `echo_commands = 1` they print every SCPI command sent: useful for debugging. |
| `instrument_disconnect` | Closes the resource. |
| `acquisition(...)` | Measures the current (`:MEAS:CURR?`), computes the time since start, writes a line to the file and to the screen (with immediate `flush()`) and appends the values to the lists used for the plot. |
| `ramp(...)` | Moves the voltage from `v_start` to `v_end` in steps of `step`, waiting `delay` after each point. |

### A.3 SCPI initialization sequence

```text
:OUTP:STAT OFF              output off
:ABOR                       stops any running trigger model
:SOUR:FUNC VOLT             voltage source
:SOUR:VOLT 0                initial voltage 0 V
:SOURce:VOLT:ILIM <I>       current limit (compliance)
:SENS:CURR:RANG 10e-3       current measurement range fixed at 10 mA
:TRIG:BLOC:BUFF:CLE 1       trigger model: "buffer clear" block
:TRIG:BLOC:MEAS 1           trigger model: "measure" block
:INIT                       starts the trigger model
:OUTP:STAT ON               output on
```

The commands are those typical of the Keithley 2450 / 2460 / 2470 SMU family. If you use a different instrument, check the syntax in its SCPI manual.

> The `:TRIG:BLOC:...` and `:INIT` commands configure a trigger model that is, in practice, not used for the readings: the data are obtained with direct `:MEAS:CURR?` queries. They are probably leftovers from a previous version; it is worth testing whether they can be removed.

### A.4 Measurement sequence logic

```python
for v_set in v_set_value_vector:
    v_start = float(instrument_query(my_instr, ":SOUR:VOLT?"))
    ramp(my_instr, v_start, v_set, ...)   # ramp up towards v_set
    ramp(my_instr, v_set, 0.0, ...)       # return to zero
```

With `double_polarity = True` the vector is `[+V_set, -V_set]`, so the actual sequence is:

```text
0 → +V_set → 0 → −V_set → 0
```

Note: the comment in the code describes `0 → +Vset → −Vset → 0` (without passing through 0 between the two polarities), but the code **does pass through 0**. If you need a continuous `+V → −V` cycle, the sequence must be modified.

### A.5 Shutdown

```python
instrument_write(my_instr, ":OUTP:STAT OFF")
instrument_write(my_instr, '*RST')
instrument_disconnect(my_instr)
resource_manager.close
```

## B. Measurement notes

### B.1 Current range and resolution

The range is fixed at **10 mA** (`:SENS:CURR:RANG 10e-3`). For very small currents (µA, nA) the resolution with this range may be insufficient and the curve may appear noisy or "stepped".

Options:

- Set a smaller range (e.g. `1e-6`), as long as the expected current does not exceed it.
- Enable autorange: `:SENS:CURR:RANG:AUTO ON` (it may introduce small discontinuities when the range changes and longer times).

Also, the compliance value (default 1 mA) is lower than the range: this is consistent, but keep in mind that the two parameters are independent.

## C. Quick checklist before each measurement

- [ ] Instrument on, on the network, correct IP
- [ ] Sample connected correctly
- [ ] `current_compliance` suitable for the sample
- [ ] `V_set` and `step_voltage` sensible (estimated duration acceptable)
- [ ] `sample_name` new and clear
- [ ] `Data/` folder present
- [ ] No other program connected to the instrument
