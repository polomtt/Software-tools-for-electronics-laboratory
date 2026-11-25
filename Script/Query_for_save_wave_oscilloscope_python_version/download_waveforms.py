import os
import sys
import json
import time
import datetime
import numpy as np
import pyvisa as visa
import matplotlib.pyplot as plt

# ============================================================================
#   PARAMETRI (letti da file JSON)
#   uso:  python download_waveforms.py [config.json]
# ============================================================================
CONFIG_FILE = sys.argv[1] if len(sys.argv) > 1 else "config.json"

with open(CONFIG_FILE, "r") as _f:
    _cfg = json.load(_f)

IP_ADDRESS      = _cfg["ip_address"]
VISA_TIMEOUT_MS = _cfg.get("visa_timeout_ms", 20000)

CH1_ACTIVE      = _cfg.get("ch1_active", True)
CH2_ACTIVE      = _cfg.get("ch2_active", False)

N_POINTS        = _cfg.get("n_points", 1000)
BYTES_PER_POINT = _cfg.get("bytes_per_point", 1)    # 1 -> int8, 2 -> int16

N_WAVEFORMS     = _cfg.get("n_waveforms", 100)      # null = illimitato
ACQ_TIME        = _cfg.get("acq_time", None)        # secondi, null = illimitato
TRIGGER_TIMEOUT = _cfg.get("trigger_timeout", 10)   # secondi per ogni trigger

OUTPUT_DIR      = _cfg.get("output_dir", "Data")
FILENAME        = _cfg.get("filename", "waveforms")

PLOT            = _cfg.get("plot", True)
N_PLOT          = _cfg.get("n_plot", 20)

ECHO_COMMANDS   = _cfg.get("echo_commands", False)
# ============================================================================


def write(inst, cmd):
    if ECHO_COMMANDS:
        print(cmd)
    inst.write(cmd)


def query(inst, cmd):
    if ECHO_COMMANDS:
        print(cmd)
    return inst.query(cmd)


def connect(ip, timeout_ms):
    rm = visa.ResourceManager()
    inst = rm.open_resource(f"TCPIP0::{ip}::inst0::INSTR")
    inst.timeout = timeout_ms
    print("Connesso a:", query(inst, "*IDN?").strip())
    return rm, inst


def acquire_single(inst, timeout_s):
    """Arma una singola acquisizione e aspetta il trigger.
    Ritorna True se l'acquisizione e' completata, False se timeout."""
    write(inst, "ACQuire:STOPAfter SEQuence")
    write(inst, "ACQuire:STATE ON")
    t0 = time.time()
    while int(float(query(inst, "ACQuire:STATE?"))) != 0:
        if time.time() - t0 > timeout_s:
            write(inst, "ACQuire:STATE STOP")
            return False
        time.sleep(0.005)
    return True


def setup_transfer(inst, n_points, bytes_per_point):
    write(inst, "DATA:ENCdg RIBinary")
    write(inst, f"DATA:WIDTH {bytes_per_point}")
    write(inst, "DATA:START 1")
    write(inst, f"DATA:STOP {n_points}")


def download_waveform(inst, channel, bytes_per_point):
    """Scarica la waveform del canale indicato (es. 'CH1').
    Ritorna (tempo [s], tensione [V])."""
    write(inst, f"DATA:SOURCE {channel}")

    # parametri di scala (vanno letti dopo aver scelto la sorgente)
    y_mult = float(query(inst, "WFMPRE:YMULT?"))
    y_off  = float(query(inst, "WFMPRE:YOFF?"))
    y_zero = float(query(inst, "WFMPRE:YZERO?"))
    x_incr = float(query(inst, "WFMPRE:XINCR?"))
    x_zero = float(query(inst, "WFMPRE:XZERO?"))

    inst.write("CURVE?")
    raw = inst.read_raw()

    # header binario: #<n cifre><n cifre = numero di byte><dati>
    if raw[0:1] != b"#":
        raise ValueError("Formato binario non valido.")
    header_len = int(raw[1:2])
    n_bytes = int(raw[2:2 + header_len])
    start = 2 + header_len
    payload = raw[start:start + n_bytes]

    dtype = ">i1" if bytes_per_point == 1 else ">i2"
    data = np.frombuffer(payload, dtype=dtype)

    voltage = (data - y_off) * y_mult + y_zero
    time_axis = x_zero + x_incr * np.arange(len(data))
    return time_axis, voltage


# ============================================================================
#   MAIN
# ============================================================================
if __name__ == "__main__":
    channels = []
    if CH1_ACTIVE:
        channels.append("CH1")
    if CH2_ACTIVE:
        channels.append("CH2")
    if not channels:
        raise SystemExit("Nessun canale attivo: imposta CH1_ACTIVE e/o CH2_ACTIVE.")
    if N_WAVEFORMS is None and ACQ_TIME is None:
        print("Attenzione: nessun limite impostato, stop con Ctrl+C.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(OUTPUT_DIR, f"{FILENAME}_{stamp}.npz")

    rm, inst = connect(IP_ADDRESS, VISA_TIMEOUT_MS)
    setup_transfer(inst, N_POINTS, BYTES_PER_POINT)

    waves = {ch: [] for ch in channels}
    time_axis = None
    count = 0
    t_start = time.time()

    try:
        while (N_WAVEFORMS is None or count < N_WAVEFORMS) and \
              (ACQ_TIME is None or time.time() - t_start < ACQ_TIME):

            if not acquire_single(inst, TRIGGER_TIMEOUT):
                print("Timeout trigger, riprovo...")
                continue

            for ch in channels:
                t, v = download_waveform(inst, ch, BYTES_PER_POINT)
                waves[ch].append(v)
                if time_axis is None:
                    time_axis = t

            count += 1
            if count % 10 == 0:
                print(f"Waveform salvate: {count} -- tempo: {time.time() - t_start:.1f} s")

    except KeyboardInterrupt:
        print("Misura interrotta manualmente.")

    finally:
        inst.close()
        rm.close()

    # salvataggio: un array (n_waveform, n_punti) per canale + asse dei tempi
    if count > 0:
        save_dict = {"time": time_axis}
        for ch in channels:
            save_dict[ch.lower()] = np.array(waves[ch])
        np.savez_compressed(out_path, **save_dict)
        print(f"Salvate {count} waveform in {out_path}")

        if PLOT:
            fig, axes = plt.subplots(len(channels), 1, sharex=True, squeeze=False)
            for ax, ch in zip(axes[:, 0], channels):
                for v in waves[ch][:N_PLOT]:
                    ax.plot(time_axis, v, alpha=0.5)
                ax.set_ylabel(f"{ch} [V]")
            axes[-1, 0].set_xlabel("Tempo [s]")
            plt.show()
    else:
        print("Nessuna waveform acquisita.")
