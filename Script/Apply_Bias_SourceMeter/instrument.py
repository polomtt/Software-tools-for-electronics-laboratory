"""
Wrapper minimale attorno a PyVISA per pilotare lo strumento (SMU) usato per
le misure I-V / bias. E' la stessa logica dello script originale
set_voltage.py, solo riorganizzata in una classe cosi' puo' essere
richiamata dal server web (app.py).
"""

import pyvisa as visa


class Instrument:
    def __init__(self, resource_string, timeout=10000, echo=False):
        self.resource_string = resource_string
        self.timeout = timeout
        self.echo = echo
        self.rm = None
        self.inst = None

    def connect(self, do_id_query=True, do_reset=False, do_clear=False):
        self.rm = visa.ResourceManager()
        self.inst = self.rm.open_resource(self.resource_string)
        self.inst.timeout = self.timeout
        self.inst.write_termination = "\n"
        self.inst.read_termination = "\n"

        idn = None
        if do_id_query:
            idn = self.inst.query("*IDN?")
        if do_reset:
            self.write("*RST")
        if do_clear:
            self.inst.clear()
        return idn

    def write(self, cmd):
        if self.echo:
            print(cmd)
        self.inst.write(cmd)

    def query(self, cmd):
        if self.echo:
            print(cmd)
        return self.inst.query(cmd)

    def read_current(self):
        return float(self.query(":MEAS:CURR?"))

    def set_voltage(self, v):
        self.write(":SOUR:VOLT {:.4f}".format(v))

    def get_voltage(self):
        return float(self.query(":SOUR:VOLT?"))

    def configure_source(self, current_compliance):
        """Sequenza di setup identica allo script originale: spegne
        l'uscita, azzera la tensione, imposta il limite di corrente e
        riattiva l'uscita."""
        self.write(":OUTP:STAT OFF")
        self.write(":ABOR")
        self.write(":SOUR:FUNC VOLT")
        self.write(":SOUR:VOLT 0")
        self.write(":SOURce:VOLT:ILIM {}".format(current_compliance))
        self.write(":TRIG:BLOC:BUFF:CLE 1")
        self.write(":TRIG:BLOC:MEAS 1")
        self.write(":INIT")
        self.write(":OUTP:STAT ON")

    def safe_shutdown(self):
        """Spegne l'uscita e resetta lo strumento. Non solleva eccezioni:
        va chiamata anche quando qualcosa e' andato storto."""
        try:
            self.write(":OUTP:STAT OFF")
            self.write("*RST")
        except Exception:
            pass

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
