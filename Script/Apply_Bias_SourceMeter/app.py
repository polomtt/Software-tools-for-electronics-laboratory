"""
Server web per il controllo dello strumento (SMU): curva I-V e applicazione
di un bias fisso, con acquisizione Tempo/Tensione/Corrente in tempo reale.

Avvio:
    pip install -r requirements.txt
    python app.py
poi apri http://localhost:5000 nel browser.
"""

import os
import time
import threading
import datetime

from flask import Flask, jsonify, request, render_template

from instrument import Instrument

app = Flask(__name__)

DATA_FOLDER = "Data"
os.makedirs(DATA_FOLDER, exist_ok=True)

# ---- Configurazione di default, modificabile dalla tab "Impostazioni" ----
DEFAULT_CONFIG = {
    "instrument_resource": "TCPIP::10.196.31.238::inst0::INSTR",
    "sample_name": "Meas_Current_COBRA_IV_sensor_su_Kapton",
    "v_set": -100.0,
    "step_voltage": 1.0,
    "delay": 1.0,
    "current_compliance": 600e-6,
    "hold_sample_period": 1.0,  # periodo di campionamento durante il BIAS
}

NUMERIC_FIELDS = {
    "v_set",
    "step_voltage",
    "delay",
    "current_compliance",
    "hold_sample_period",
}


class MeasurementController:
    STATE_IDLE = "idle"
    STATE_RAMP_UP = "ramp_up"
    STATE_HOLD = "hold"
    STATE_RAMP_DOWN = "ramp_down"
    STATE_ERROR = "error"

    def __init__(self):
        self.lock = threading.Lock()
        self.config = dict(DEFAULT_CONFIG)
        self.state = self.STATE_IDLE
        self.mode = None  # "iv_curve" oppure "bias"
        self.stop_requested = False
        self.thread = None
        self.time_data = []
        self.voltage_data = []
        self.current_data = []
        self.error_message = None
        self.file_handle = None
        self.file_path = None
        self.t0 = None
        self.instrument = None

    # ------------------------------------------------------------------
    # API pubblica, chiamata dalle route Flask
    # ------------------------------------------------------------------

    def get_status(self):
        with self.lock:
            return {
                "state": self.state,
                "mode": self.mode,
                "error": self.error_message,
                "config": self.config,
                "n_points": len(self.time_data),
                "file": self.file_path,
                "last_voltage": self.voltage_data[-1] if self.voltage_data else None,
                "last_current": self.current_data[-1] if self.current_data else None,
            }

    def get_data(self, since=0):
        with self.lock:
            return {
                "t": self.time_data[since:],
                "v": self.voltage_data[since:],
                "i": self.current_data[since:],
                "n_points": len(self.time_data),
            }

    def update_config(self, new_cfg):
        with self.lock:
            if self.state != self.STATE_IDLE:
                return False, "Non si possono cambiare i parametri mentre una misura e' in corso."
            self.config.update(new_cfg)
            return True, None

    def start(self, mode):
        with self.lock:
            if self.state not in (self.STATE_IDLE, self.STATE_ERROR):
                return False, "Una misura e' gia' in corso."
            self.mode = mode
            self.stop_requested = False
            self.state = self.STATE_RAMP_UP
            self.error_message = None
            self.time_data = []
            self.voltage_data = []
            self.current_data = []
            self.t0 = time.time()

        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return True, None

    def stop(self):
        with self.lock:
            if self.state == self.STATE_IDLE:
                return False, "Nessuna misura in corso."
            self.stop_requested = True
        return True, None

    # ------------------------------------------------------------------
    # worker eseguito nel thread di background
    # ------------------------------------------------------------------

    def _acquire_point(self, voltage):
        current = self.instrument.read_current()
        t = time.time() - self.t0
        with self.lock:
            self.time_data.append(t)
            self.voltage_data.append(voltage)
            self.current_data.append(current)
        if self.file_handle:
            self.file_handle.write("{:.3f},{:.6f},{:.6e}\n".format(t, voltage, current))
            self.file_handle.flush()
        return current

    def _ramp(self, v_start, v_end, step, delay, interruptible=False):
        """Sposta la tensione da v_start a v_end un passo alla volta,
        acquisendo un punto ad ogni passo. Se interruptible=True e arriva
        una richiesta di stop, si interrompe subito restituendo l'ultima
        tensione effettivamente applicata (senza saltare a v_end)."""
        direction = 1 if v_end >= v_start else -1
        step = abs(step) * direction
        v = v_start
        last_v = v_start
        while (direction > 0 and v <= v_end) or (direction < 0 and v >= v_end):
            if interruptible and self.stop_requested:
                return last_v
            self.instrument.set_voltage(v)
            self._acquire_point(v)
            last_v = v
            time.sleep(delay)
            v += step
        self.instrument.set_voltage(v_end)
        self._acquire_point(v_end)
        return v_end

    def _run(self):
        cfg = dict(self.config)
        try:
            self.instrument = Instrument(cfg["instrument_resource"], echo=False)
            self.instrument.connect(do_id_query=True, do_reset=False, do_clear=False)
            self.instrument.configure_source(cfg["current_compliance"])

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            self.file_path = os.path.join(
                DATA_FOLDER, "{}_{}.txt".format(cfg["sample_name"], timestamp)
            )
            self.file_handle = open(self.file_path, "w")
            self.file_handle.write("#time[s],voltage[V],current[A]\n")

            v_set = cfg["v_set"]
            step = cfg["step_voltage"]
            delay = cfg["delay"]

            # ---- fase di salita: 0 -> V_set (interrompibile) ----
            with self.lock:
                self.state = self.STATE_RAMP_UP
            last_v = self._ramp(0.0, v_set, step, delay, interruptible=True)
            reached_v_set = abs(last_v - v_set) < 1e-9

            if self.mode == "bias" and reached_v_set and not self.stop_requested:
                # ---- si resta a V_set finche' non arriva lo stop ----
                with self.lock:
                    self.state = self.STATE_HOLD
                while not self.stop_requested:
                    self._acquire_point(v_set)
                    time.sleep(cfg["hold_sample_period"])
                last_v = v_set

            # ---- rampa di discesa verso 0, sempre eseguita fino in fondo
            #      (curva IV: subito dopo la salita; bias/stop: dopo il
            #      mantenimento o dopo un'interruzione a meta' salita) ----
            with self.lock:
                self.state = self.STATE_RAMP_DOWN
            self._ramp(last_v, 0.0, step, delay, interruptible=False)

            self.instrument.write(":OUTP:STAT OFF")
            self.instrument.write("*RST")

        except Exception as e:
            with self.lock:
                self.state = self.STATE_ERROR
                self.error_message = str(e)
        finally:
            if self.instrument is not None:
                self.instrument.close()
            if self.file_handle is not None:
                self.file_handle.close()
                self.file_handle = None
            with self.lock:
                if self.state != self.STATE_ERROR:
                    self.state = self.STATE_IDLE
                self.mode = None
                self.stop_requested = False


controller = MeasurementController()


# ---------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/status")
def api_status():
    return jsonify(controller.get_status())


@app.route("/api/data")
def api_data():
    since = request.args.get("since", default=0, type=int)
    return jsonify(controller.get_data(since))


@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        return jsonify({"config": controller.config})

    raw = request.get_json(force=True, silent=True) or {}
    new_cfg = {}
    for key, value in raw.items():
        if key in NUMERIC_FIELDS:
            new_cfg[key] = float(value)
        elif key in ("instrument_resource", "sample_name"):
            new_cfg[key] = str(value)
    ok, msg = controller.update_config(new_cfg)
    return jsonify({"ok": ok, "error": msg, "config": controller.config})


@app.route("/api/start", methods=["POST"])
def api_start():
    body = request.get_json(force=True, silent=True) or {}
    mode = body.get("mode")
    if mode not in ("iv_curve", "bias"):
        return jsonify({"ok": False, "error": "Modalita' non valida."}), 400
    ok, msg = controller.start(mode)
    return jsonify({"ok": ok, "error": msg})


@app.route("/api/stop", methods=["POST"])
def api_stop():
    ok, msg = controller.stop()
    return jsonify({"ok": ok, "error": msg})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False, threaded=True)
