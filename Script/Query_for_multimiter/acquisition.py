#!/usr/bin/env python3
"""
Acquisizione generica (corrente / tensione / resistenza) da strumento VISA.

Tutti i parametri sono nel file JSON di configurazione.
Uso:
    python acquisition.py                 # usa config.json
    python acquisition.py mia_config.json
"""

import argparse
import collections
import datetime
import json
import math
import os
import shutil
import sys
import time

import pyvisa


# ============================================================
# STRUMENTO
# ============================================================

class Instrument:
    """Wrapper PyVISA con riconnessione."""

    def __init__(self, cfg):
        self.resource_string = cfg["resource_string"]
        self.timeout = cfg["timeout_ms"]
        self.do_id_query = cfg.get("do_id_query", True)
        self.do_reset = cfg.get("do_reset", False)
        self.do_clear = cfg.get("do_clear", False)
        self.echo = cfg.get("echo_commands", False)
        self.rm = None
        self.inst = None

    def connect(self, first_time=True):
        self.rm = pyvisa.ResourceManager()
        self.inst = self.rm.open_resource(self.resource_string)
        self.inst.timeout = self.timeout

        # ID, reset e clear solo alla prima connessione:
        # dopo una riconnessione un reset cancellerebbe la configurazione.
        if first_time:
            if self.do_id_query:
                print("Instrument ID:", self.query("*IDN?").strip())
            if self.do_reset:
                self.write("*RST")
            if self.do_clear:
                self.inst.clear()

    def reconnect(self):
        self.close()
        self.connect(first_time=False)

    def write(self, command):
        if self.echo:
            print(command)
        self.inst.write(command)

    def query(self, command):
        if self.echo:
            print(command)
        return self.inst.query(command)

    def close(self):
        try:
            if self.inst is not None:
                self.inst.close()
        except Exception:
            pass
        try:
            if self.rm is not None:
                self.rm.close()
        except Exception:
            pass
        self.inst = None
        self.rm = None


def configure(instr, setup_commands):
    for cmd in setup_commands:
        instr.write(cmd)


def read_value(instr, query_cmd, setup_commands, rec_cfg):
    """Legge un valore; in caso di errore di comunicazione prova a riconnettersi."""
    max_retries = rec_cfg.get("max_retries", 5)
    delay = rec_cfg.get("retry_delay_s", 5)
    attempts = 0

    while True:
        try:
            return float(instr.query(query_cmd))

        except ValueError as e:
            # risposta non numerica: riprova senza riconnettere
            attempts += 1
            print("\n[WARN] Risposta non valida ({}), tentativo {}/{}".format(
                e, attempts, max_retries))
            if attempts > max_retries:
                raise
            time.sleep(delay)

        except (pyvisa.VisaIOError, OSError) as e:
            attempts += 1
            print("\n[WARN] Errore di comunicazione ({}), tentativo {}/{}".format(
                e, attempts, max_retries))
            if attempts > max_retries:
                raise
            time.sleep(delay)
            try:
                instr.reconnect()
                configure(instr, setup_commands)
                print("[INFO] Riconnesso allo strumento.")
            except Exception as e2:
                print("[WARN] Riconnessione fallita:", e2)


# ============================================================
# GRAFICO LIVE
# ============================================================

class LivePlot:
    def __init__(self, label, unit, max_points):
        import matplotlib.pyplot as plt
        self.plt = plt
        plt.ion()
        self.t = collections.deque(maxlen=max_points)
        self.v = collections.deque(maxlen=max_points)
        self.fig, self.ax = plt.subplots()
        (self.line,) = self.ax.plot([], [], marker=".", linewidth=1)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("{} ({})".format(label, unit))
        self.ax.grid(True)
        self.fig.show()

    def alive(self):
        return self.plt.fignum_exists(self.fig.number)

    def update(self, t, v):
        self.t.append(t)
        self.v.append(v)
        self.line.set_data(self.t, self.v)
        self.ax.relim()
        self.ax.autoscale_view()
        self.fig.canvas.draw_idle()

    def pause(self, seconds):
        self.plt.pause(max(seconds, 0.001))


def wait_until(target, plot):
    """Attende fino a `target` (perf_counter), mantenendo vivo il grafico."""
    while True:
        remaining = target - time.perf_counter()
        if remaining <= 0:
            return
        if plot is not None and plot.alive():
            plot.pause(min(remaining, 0.2))
        else:
            time.sleep(min(remaining, 0.5))


# ============================================================
# MAIN
# ============================================================

def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Acquisizione da strumento VISA")
    parser.add_argument("config", nargs="?", default="config.json",
                        help="file JSON di configurazione (default: config.json)")
    args = parser.parse_args()

    cfg = load_config(args.config)

    inst_cfg = cfg["instrument"]
    meas_cfg = cfg["measurement"]
    acq_cfg = cfg["acquisition"]
    out_cfg = cfg["output"]
    rec_cfg = cfg.get("reconnection", {})
    plot_cfg = cfg.get("plot", {"enabled": False})

    # --- Grandezza da misurare ---
    quantity = meas_cfg["quantity"]
    quantities = meas_cfg["quantities"]
    if quantity not in quantities:
        sys.exit("Grandezza '{}' non definita. Disponibili: {}".format(
            quantity, ", ".join(quantities)))
    q = quantities[quantity]
    query_cmd = q["query"]
    unit = q.get("unit", "")
    label = q.get("label", quantity)
    setup_commands = q.get("setup_commands", [])

    duration = acq_cfg["duration_s"]
    interval = acq_cfg["sampling_interval_s"]
    print_every = max(1, acq_cfg.get("print_every", 100))

    # --- File di output ---
    directory = out_cfg.get("directory", "Data")
    os.makedirs(directory, exist_ok=True)
    delim = out_cfg.get("delimiter", ",")
    ext = out_cfg.get("extension", "csv").lstrip(".")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    base = "{}_{}_{}".format(out_cfg["filename"], quantity, stamp)
    filepath = os.path.join(directory, base + "." + ext)

    if out_cfg.get("save_config_copy", True):
        shutil.copyfile(args.config, os.path.join(directory, base + "_config.json"))

    # --- Grafico (opzionale) ---
    plot = None
    if plot_cfg.get("enabled", False):
        try:
            plot = LivePlot(label, unit, plot_cfg.get("max_points", 500))
        except Exception as e:
            print("[WARN] Grafico non disponibile ({}), continuo senza.".format(e))

    instr = Instrument(inst_cfg)
    count = 0

    try:
        instr.connect(first_time=True)
        configure(instr, setup_commands)

        print("\nStarting {} acquisition...\n".format(label.lower()))

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(delim.join(["id", "time_s", "timestamp",
                                "value_{}".format(unit) if unit else "value"]) + "\n")

            t0 = time.perf_counter()
            next_tick = t0

            while (time.perf_counter() - t0) < duration:

                value = read_value(instr, query_cmd, setup_commands, rec_cfg)
                elapsed = time.perf_counter() - t0
                ts = datetime.datetime.now().isoformat(timespec="milliseconds")

                f.write(delim.join([
                    str(count),
                    "{:.6f}".format(elapsed),
                    ts,
                    "{:.12e}".format(value),
                ]) + "\n")
                f.flush()

                if count % print_every == 0:
                    print("Event: {} | Time: {:.2f} s | {}: {:.8e} {}".format(
                        count, elapsed, label, value, unit))

                if plot is not None:
                    if plot.alive():
                        plot.update(elapsed, value)
                    else:
                        plot = None

                count += 1

                # --- Temporizzazione senza deriva ---
                next_tick += interval
                now = time.perf_counter()
                if next_tick < now:
                    # la lettura ha impiegato piu' dell'intervallo: salta i tick persi
                    missed = int((now - next_tick) // interval) + 1
                    next_tick += missed * interval
                    print("\n[WARN] Intervallo superato, saltati {} campioni.".format(missed))
                if next_tick - t0 >= duration:
                    break
                wait_until(next_tick, plot)

        print("\nAcquisition completed!")

    except KeyboardInterrupt:
        print("\nAcquisition interrupted by user.")

    except Exception as e:
        print("\nERROR:", e)

    finally:
        instr.close()
        print("Total measurements: {}".format(count))
        print("Data saved in: {}".format(filepath))


if __name__ == "__main__":
    main()
