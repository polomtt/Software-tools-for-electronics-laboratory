# Lab Control System — Installation Guide

**For:** Anyone setting up the application on a new PC.  
**Time required:** ~15 minutes.

---

## What you need before starting

- Windows 10 or 11 (64-bit)
- Internet connection (for downloads)
- The instruments physically connected via USB/serial cables

---

## Step 1 — Install Python

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Download the latest **Python 3.11** or newer (64-bit)
3. Run the installer — **important:** tick the box **"Add Python to PATH"** before clicking Install
4. Verify the installation by opening PowerShell and typing:
   ```
   python --version
   ```
   You should see something like `Python 3.11.x`

---

## Step 2 — Install NI-VISA

NI-VISA is required to communicate with the instruments (oscilloscope, power meter).

1. Go to [ni.com/downloads](https://www.ni.com/en/support/downloads/drivers/download.ni-visa.html)
2. Download and install **NI-VISA** (free, requires a free NI account)
3. Restart the PC after installation

> **Note:** If NI-MAX is already installed on the PC, NI-VISA is already present.
> You can verify by searching "NI-MAX" in the Start menu.

---

## Step 3 — Download the application

### Option A — From GitHub (recommended)

1. Go to the repository page on GitHub
2. Click the green **Code** button → **Download ZIP**
3. Extract the ZIP to a folder of your choice, e.g. `C:\LabApplication\`

### Option B — Copy from a colleague

Copy the entire project folder to your PC. Make sure it contains:
```
app.py
core/
gui/
utils/
requirements.txt
TestSpeed.xlsx
```

---

## Step 4 — Create the virtual environment

Open PowerShell **inside the project folder** (Shift + right-click in the folder → "Open PowerShell here") and run:

```powershell
python -m venv venv
```

Then activate it:

```powershell
venv\Scripts\activate
```

You should see `(venv)` appear at the start of the line.

---

## Step 5 — Install dependencies

With the venv active, run:

```powershell
pip install -r requirements.txt
```

This installs all required packages automatically. It may take a few minutes.

---

## Step 6 — Find the instrument addresses

Connect all instruments via USB/serial and power them on. Then run:

```powershell
python -c "import pyvisa; rm = pyvisa.ResourceManager(); print(rm.list_resources())"
```

You will see something like:
```
('ASRL3::INSTR', 'ASRL4::INSTR', 'ASRL5::INSTR', 'USB0::0x0699::0x0408::C019950::INSTR', 'USB0::0x1313::0x8078::P0040580::INSTR')
```

Note down:
- The three `ASRL` addresses → these are the motor serial ports
- The address containing `0x0699` → oscilloscope (Tektronix)
- The address containing `0x1313` → power meter (Thorlabs) — detected automatically, no config needed

> **Tip:** To find which ASRL address belongs to which motor axis,
> disconnect one cable at a time and re-run the command — the missing
> address is that axis.

---

## Step 7 — Configure the addresses

Open `utils/config.py` with any text editor (Notepad, VS Code, etc.)
and update the addresses to match your system:

```python
MOTOR_1_ADDRESS = "ASRL3::INSTR"   # Z axis — change to your value
MOTOR_2_ADDRESS = "ASRL4::INSTR"   # X axis — change to your value
MOTOR_3_ADDRESS = "ASRL5::INSTR"   # Y axis — change to your value

OSCILLOSCOPE_ADDRESS = "USB0::0x0699::0x0408::C019950::INSTR"  # change serial number

CALIBRATION_FILE = "TestSpeed.xlsx"   # leave as-is if the file is in the project folder
```

Save the file.

---

## Step 8 — Run the application

With the venv active:

```powershell
python app.py
```

The application window will open. The status bar at the bottom shows green LEDs
for each connected instrument.

---

## Step 9 — (Optional) Build the executable

If you want a standalone `.exe` that launches with a double-click (no Python required):

```powershell
pip install pyinstaller
```

Then double-click `build.bat` in the project folder, or run:

```powershell
pyinstaller --onefile --windowed --clean --collect-all PyQt6 --collect-all pyqtgraph --collect-all pyvisa --collect-all pyvisa_py --collect-all usb --collect-all serial --collect-all openpyxl --collect-all OpenGL --icon=icona.ico app.py
```

The executable will be at `dist\app.exe`.
Copy it to any PC that has NI-VISA installed — no Python needed on the target machine.

---

## Troubleshooting

### "python is not recognized"
Python was not added to PATH during installation. Re-run the Python installer,
choose "Modify", and tick "Add Python to PATH".

### "No module named pyvisa" or similar
The venv is not active. Run `venv\Scripts\activate` first.

### list_resources() returns empty ()
NI-VISA is not installed, or the instrument USB driver needs to be set up.
Open NI-MAX — if the instrument does not appear there, the issue is at the
driver level (try reinstalling the USB driver or using Zadig for serial adapters).

### Instrument shows as connected in NI-MAX but not in the app
The address in `config.py` does not match. Re-run the `list_resources()` command
and copy the exact address shown.

### Motors connect but do not move
Check that the serial port parameters match the SRC-101:
baud rate 38400, 8 data bits, no parity, 1 stop bit.
This is already set in `core/motor.py` — if it still fails, the USB-to-serial
adapter may need its driver reinstalled.
