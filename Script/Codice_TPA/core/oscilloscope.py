# core/oscilloscope.py
"""
Tektronix MDO3102 - Waveform acquisition via SCPI/USB-TMC.

Features:
  - Connect / disconnect
  - Read waveform from CH1, CH2, or both
  - read_waveform_meta: returns (time, voltage, meta) with full preamble info
  - Save waveform(s) to CSV
"""

import pyvisa
import numpy as np
import csv
from pathlib import Path
from datetime import datetime


class Oscilloscope:
    """
    Driver for the Tektronix MDO3102 oscilloscope.

    Typical usage
    -------------
        scope = Oscilloscope("USB0::0x0699::0x0408::C012345::INSTR")
        scope.connect()

        # Read CH1 and save
        scope.save_waveform(channel=1, output_dir="data/")

        # Read both channels into a single CSV
        scope.save_waveform(channel="both", output_dir="data/")

        scope.disconnect()
    """

    VALID_CHANNELS = (1, 2)

    def __init__(self, address: str):
        self.address = address
        self._rm     = pyvisa.ResourceManager()
        self._dev    = None          # VISA handle, valid after connect()

# Connection

    def connect(self):
        """Open the USB-TMC connection to the oscilloscope."""
        self._dev = self._rm.open_resource(self.address)
        self._dev.timeout = 10_000          # ms — required for CURVE? transfers

        idn = self._dev.query("*IDN?").strip()
        print(f"[Oscilloscope] Connected: {idn}")

        # Set binary encoding once at connection time
        self._dev.write("DATA:ENCdg RIBinary")
        self._dev.write("DATA:WIDTH 2")     # 2 bytes per sample → int16

    def disconnect(self):
        """Close the VISA connection."""
        if self._dev is not None:
            self._dev.close()
            self._dev = None
            print("[Oscilloscope] Disconnected.")

    @property
    def is_connected(self) -> bool:
        return self._dev is not None

   # Waveform reading

    def _read_channel(self, channel: int) -> tuple[np.ndarray, np.ndarray]:
        """
        Read the raw waveform from a single channel.

        Returns
        -------
        time_s : np.ndarray
        voltage_v : np.ndarray
        """
        if channel not in self.VALID_CHANNELS:
            raise ValueError(f"Invalid channel: {channel}. Choose 1 or 2.")
        if not self.is_connected:
            raise RuntimeError("Oscilloscope not connected. Call connect() first.")

        self._dev.write(f"DATA:SOURCE CH{channel}")

        x_incr = float(self._dev.query("WFMOUTPRE:XINCR?"))
        x_zero = float(self._dev.query("WFMOUTPRE:XZERO?"))
        y_mult = float(self._dev.query("WFMOUTPRE:YMULT?"))
        y_off  = float(self._dev.query("WFMOUTPRE:YOFF?"))
        y_zero = float(self._dev.query("WFMOUTPRE:YZERO?"))

        raw = self._dev.query_binary_values(
            "CURVE?", datatype='h', is_big_endian=True
        )
        raw = np.array(raw, dtype=np.int16)

        voltage_v = (raw - y_off) * y_mult + y_zero
        time_s    = np.arange(len(raw)) * x_incr + x_zero

        return time_s, voltage_v

    def _read_channel_full(self, channel: int) -> tuple:
        """
        Read waveform + full preamble metadata.

        Returns
        -------
        time_s    : np.ndarray
        voltage_v : np.ndarray
        meta      : dict with all preamble parameters and derived values
        """
        if channel not in self.VALID_CHANNELS:
            raise ValueError(f"Invalid channel: {channel}. Choose 1 or 2.")
        if not self.is_connected:
            raise RuntimeError("Oscilloscope not connected. Call connect() first.")

        self._dev.write(f"DATA:SOURCE CH{channel}")

        # Read all preamble parameters
        x_incr = float(self._dev.query("WFMOUTPRE:XINCR?"))
        x_zero = float(self._dev.query("WFMOUTPRE:XZERO?"))
        x_unit = self._dev.query("WFMOUTPRE:XUNIT?").strip().strip('"')
        y_mult = float(self._dev.query("WFMOUTPRE:YMULT?"))
        y_off  = float(self._dev.query("WFMOUTPRE:YOFF?"))
        y_zero = float(self._dev.query("WFMOUTPRE:YZERO?"))
        y_unit = self._dev.query("WFMOUTPRE:YUNIT?").strip().strip('"')

        # Try to read oscilloscope display settings
        try:
            ch_scale    = float(self._dev.query(f"CH{channel}:SCALE?"))
            ch_offset   = float(self._dev.query(f"CH{channel}:POSITION?"))
            h_scale     = float(self._dev.query("HORIZONTAL:SCALE?"))
        except Exception:
            ch_scale  = None
            ch_offset = None
            h_scale   = None

        # Read raw samples
        raw = self._dev.query_binary_values(
            "CURVE?", datatype='h', is_big_endian=True
        )
        raw = np.array(raw, dtype=np.int16)

        voltage_v = (raw - y_off) * y_mult + y_zero
        time_s    = np.arange(len(raw)) * x_incr + x_zero

        n_points    = len(raw)
        sample_rate = 1.0 / x_incr if x_incr != 0 else 0.0
        # timebase: total time window / 10 divisions
        timebase_s_div = (x_incr * n_points) / 10.0

        meta = {
            "timestamp"       : datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "channel"         : f"CH{channel}",
            "n_points"        : n_points,
            "sample_rate_Hz"  : f"{sample_rate:.6e}",
            "x_increment_s"   : f"{x_incr:.9e}",
            "x_zero_s"        : f"{x_zero:.9e}",
            "x_unit"          : x_unit,
            "y_multiplier_V"  : f"{y_mult:.9e}",
            "y_offset_raw"    : f"{y_off:.6f}",
            "y_zero_V"        : f"{y_zero:.9e}",
            "y_unit"          : y_unit,
            "v_min_V"         : f"{voltage_v.min():.6e}",
            "v_max_V"         : f"{voltage_v.max():.6e}",
            "v_pp_V"          : f"{(voltage_v.max() - voltage_v.min()):.6e}",
            "v_mean_V"        : f"{voltage_v.mean():.6e}",
            "timebase_s_div"  : f"{timebase_s_div:.6e}",
        }

        # Add display settings if available
        if ch_scale is not None:
            meta["ch_scale_V_div"]   = f"{ch_scale:.6e}"
            meta["ch_offset_div"]    = f"{ch_offset:.6f}"
            meta["h_scale_s_div"]    = f"{h_scale:.6e}"

        return time_s, voltage_v, meta

    # Public API

    def read_waveform(self, channel: int) -> tuple[np.ndarray, np.ndarray]:
        """Read and return (time_s, voltage_v) for a single channel."""
        return self._read_channel(channel)

    def read_waveform_meta(self, channel: int) -> tuple:
        """
        Read and return (time_s, voltage_v, meta) for a single channel.
        meta contains all preamble parameters and derived values needed
        to fully reconstruct the signal as displayed on the oscilloscope.
        """
        return self._read_channel_full(channel)

    def save_waveform(
        self,
        channel,
        output_dir: str = ".",
        filename: str   = None,
    ) -> list[Path]:
        """
        Read a waveform and save it to one or more CSV files.

        Parameters
        ----------
        channel : 1 | 2 | "both"
        output_dir : destination folder
        filename : base name without extension (auto-timestamp if omitted)

        Returns
        -------
        list[Path] — files created
        """
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base = filename if filename else f"waveform_{timestamp}"

        saved_files = []

        if channel == "both":
            print("[Oscilloscope] Reading CH1...")
            t1, v1, m1 = self._read_channel_full(1)
            print("[Oscilloscope] Reading CH2...")
            t2, v2, m2 = self._read_channel_full(2)

            for ch_key, t, v, meta in [("CH1", t1, v1, m1), ("CH2", t2, v2, m2)]:
                filepath = out_dir / f"{base}_{ch_key}.csv"
                self._write_csv(filepath, t, v, meta)
                saved_files.append(filepath)
                print(f"[Oscilloscope] Saved: {filepath}")

        elif channel in self.VALID_CHANNELS:
            print(f"[Oscilloscope] Reading CH{channel}...")
            t, v, meta = self._read_channel_full(channel)
            filepath = out_dir / f"{base}_CH{channel}.csv"
            self._write_csv(filepath, t, v, meta)
            saved_files.append(filepath)
            print(f"[Oscilloscope] Saved: {filepath}")

        else:
            raise ValueError(
                f"Invalid channel parameter: {channel!r}. Use 1, 2, or 'both'."
            )

        return saved_files

    # CSV writer

    @staticmethod
    def _write_csv(filepath: Path, time_s, voltage_v, meta: dict):
        """
        Write a self-contained CSV with metadata header + time/voltage columns.

        Format
        ------
        # key, value          ← metadata rows (prefix #)
        # ...
        time_s, voltage_V     ← column headers
        data rows ...
        """
        with open(filepath, "w", newline="") as f:
            writer = csv.writer(f)

            # Metadata header
            for key, value in meta.items():
                writer.writerow([f"# {key}", value])
            writer.writerow([])   # blank separator

            # Data
            writer.writerow(["time_s", "voltage_V"])
            for t, v in zip(time_s, voltage_v):
                writer.writerow([f"{t:.9e}", f"{v:.6e}"])

    # Acquisition controlloer

    def run(self):
        """Start continuous acquisition."""
        self._dev.write("ACQuire:STATE RUN")

    def stop(self):
        """Stop acquisition."""
        self._dev.write("ACQuire:STATE STOP")

    def single(self):
        """Single acquisition (stops after one trigger event)."""
        self._dev.write("ACQuire:STATE SEQuence")
