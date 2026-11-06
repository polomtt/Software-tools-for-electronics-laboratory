# core/power_meter.py
"""
Thorlabs PM100D - Power measurement via SCPI/USB-TMC.

Features:
  - Connect / disconnect  (auto-detects the device by vendor ID)
  - Wavelength calibration
  - Single reading and averaged reading
  - Save measurements to CSV
"""

import pyvisa
import numpy as np
import csv
from pathlib import Path
from datetime import datetime


class PowerMeter:
    """
    Driver for the Thorlabs PM100D power meter.

    The device is identified automatically by its vendor ID (0x1313).
    If auto-detection fails, the VISA address can be passed explicitly.

    Typical usage
    -------------
        pm = PowerMeter()          # auto-detect
        pm.connect()

        pm.set_wavelength(1550)    # nm
        power_w = pm.read_power()  # single reading in Watts

        # Average over 10 samples and save to CSV
        pm.save_power(
            n_samples   = 10,
            averaging   = 5,
            output_dir  = "data/",
            wavelength_nm = 1550,
        )

        pm.disconnect()
    """

    THORLABS_VENDOR_ID = "1313"     # used for auto-detection

    def __init__(self, address: str = None):
        """
        Parameters
        ----------
        address : str, optional
            VISA address (e.g. 'USB0::0x1313::0x8078::P0012345::INSTR').
            If None, the device is located automatically via list_resources().
        """
        self.address = address
        self._rm  = pyvisa.ResourceManager()
        self._dev = None             # VISA handle, valid after connect()

    # Connection
  

    def _find_address(self) -> str:
        """
        Scan all VISA resources and return the first one that matches
        the Thorlabs vendor ID or responds to *IDN? with 'THORLABS'.
        Raises RuntimeError if nothing is found.
        """
        for addr in self._rm.list_resources():
            # Fast path: vendor ID in address string
            if self.THORLABS_VENDOR_ID in addr:
                print(f"[PowerMeter] Found by vendor ID: {addr}")
                return addr

        # Slow path: open each USB resource and query IDN
        for addr in self._rm.list_resources():
            if "USB" not in addr:
                continue
            try:
                inst = self._rm.open_resource(addr)
                inst.timeout = 3000
                idn = inst.query("*IDN?").strip()
                inst.close()
                if "THORLABS" in idn.upper() or "PM100" in idn.upper():
                    print(f"[PowerMeter] Found by IDN: {addr}  ({idn})")
                    return addr
            except Exception:
                pass

        raise RuntimeError(
            "PM100D not found on any USB resource. "
            "Check the USB cable and try again, or pass the address explicitly."
        )

    def connect(self):
        """Open the USB-TMC connection to the power meter."""
        if self.address is None:
            self.address = self._find_address()

        self._dev = self._rm.open_resource(self.address)
        self._dev.timeout = 10_000      # ms

        idn = self._dev.query("*IDN?").strip()
        print(f"[PowerMeter] Connected: {idn}")

    def disconnect(self):
        """Close the VISA connection."""
        if self._dev is not None:
            self._dev.close()
            self._dev = None
            print("[PowerMeter] Disconnected.")

    @property
    def is_connected(self) -> bool:
        return self._dev is not None

    def _check_connected(self):
        if not self.is_connected:
            raise RuntimeError("PowerMeter not connected. Call connect() first.")

    
    # Configuration

    def set_wavelength(self, wavelength_nm: float):
        """Set the calibration wavelength in nm."""
        self._check_connected()
        self._dev.write(f"SENS:CORR:WAV {wavelength_nm}")

    def get_wavelength(self) -> float:
        """Return the current calibration wavelength in nm."""
        self._check_connected()
        return float(self._dev.query("SENS:CORR:WAV?"))

    def set_auto_range(self, enabled: bool = True):
        """Enable or disable auto-range."""
        self._check_connected()
        self._dev.write(f"SENS:POW:RANG:AUTO {'ON' if enabled else 'OFF'}")

    def set_range(self, power_range_w: float):
        """Set manual range in Watts."""
        self._check_connected()
        self._dev.write(f"SENS:POW:RANG {power_range_w}")

    def set_averaging(self, count: int):
        """Set the number of internal hardware averages (1–300)."""
        self._check_connected()
        self._dev.write(f"SENS:AVER:COUNT {count}")

    def get_sensor_info(self) -> str:
        """Return sensor identification string."""
        self._check_connected()
        return self._dev.query("SYST:SENS:IDN?").strip()

    # Measurement

    def read_power(self) -> float:
        """
        Return a single instantaneous power reading in Watts.
        """
        self._check_connected()
        return float(self._dev.query("MEAS:POW?"))

    def read_average(
        self,
        n_samples: int = 10,
        averaging: int = 1,
    ) -> dict:
        """
        Acquire n_samples readings and return basic statistics.

        Parameters
        ----------
        n_samples : int
            Number of software samples to collect.
        averaging : int
            Hardware averaging count set on the device before sampling.

        Returns
        -------
        dict with keys: mean_w, std_w, min_w, max_w, mean_mw, n_samples, averaging
        """
        self._check_connected()
        self.set_averaging(averaging)

        samples = np.array([float(self._dev.query("MEAS:POW?"))
                            for _ in range(n_samples)])
        return {
            "mean_w"   : float(samples.mean()),
            "std_w"    : float(samples.std()),
            "min_w"    : float(samples.min()),
            "max_w"    : float(samples.max()),
            "mean_mw"  : float(samples.mean() * 1000),
            "n_samples": n_samples,
            "averaging": averaging,
        }

    # Save to CSV

    def save_power(
        self,
        n_samples     : int   = 10,
        averaging     : int   = 1,
        wavelength_nm : float = None,
        output_dir    : str   = ".",
        filename      : str   = None,
    ) -> Path:
        """
        Measure power (averaged) and save the result to a CSV file.

        Parameters
        ----------
        n_samples : int
            Number of software samples.
        averaging : int
            Hardware averaging count.
        wavelength_nm : float, optional
            If provided, sets the calibration wavelength before measuring.
        output_dir : str
            Destination folder (created if it does not exist).
        filename : str, optional
            Base filename without extension.
            If omitted, a timestamp-based name is generated automatically.

        Returns
        -------
        Path
            Path of the CSV file created.
        """
        self._check_connected()

        if wavelength_nm is not None:
            self.set_wavelength(wavelength_nm)

        print(f"[PowerMeter] Acquiring {n_samples} samples "
              f"(hw averaging={averaging})...")
        stats = self.read_average(n_samples=n_samples, averaging=averaging)

        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base      = filename if filename else f"power_{timestamp}"
        filepath  = out_dir / f"{base}.csv"

        wl = wavelength_nm if wavelength_nm is not None else self.get_wavelength()

        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)
            # Header block
            writer.writerow(["timestamp",    datetime.now().strftime("%Y-%m-%d %H:%M:%S")])
            writer.writerow(["wavelength_nm", f"{wl:.1f}"])
            writer.writerow(["n_samples",    stats["n_samples"]])
            writer.writerow(["averaging",    stats["averaging"]])
            writer.writerow([])
            # Data
            writer.writerow(["mean_W", "std_W", "min_W", "max_W", "mean_mW"])
            writer.writerow([
                f"{stats['mean_w']:.6E}",
                f"{stats['std_w']:.6E}",
                f"{stats['min_w']:.6E}",
                f"{stats['max_w']:.6E}",
                f"{stats['mean_mw']:.6f}",
            ])

        print(f"[PowerMeter] Saved: {filepath}")
        print(f"             Mean = {stats['mean_mw']:.4f} mW  "
              f"(+/- {stats['std_w']*1000:.4f} mW)")

        return filepath
