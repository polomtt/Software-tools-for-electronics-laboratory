import pyvisa as visa
import time
import datetime
import os

# ============================================================
# CONFIGURAZIONE
# ============================================================

filename = "cobra"
instrument_resource_string = "TCPIP0::10.196.31.73::inst0::INSTR"

CANALE = "CH1"          # canale da misurare: CH1, CH2, CH3, CH4

# Misure da acquisire. Commenta/scommenta quelle che vuoi.
# Formato: "nome_colonna": "TIPO_SCPI Tektronix"
MISURE = {
    "pk2pk":     "PK2pk",       # picco-picco
    # "amplitude": "AMPlitude",   # ampiezza (high - low)
    # "risetime":  "RISe",        # tempo di salita
    # "falltime":  "FALL",        # tempo di discesa
    # "mean":    "MEAN",
    # "rms":     "RMS",
    # "freq":    "FREQuency",
    # "maximum": "MAXimum",
    # "minimum": "MINImum",
}

acq_time = 600          # durata totale acquisizione (secondi)
sampling_interval = 1   # intervallo tra due letture (secondi)
print_every = 10        # stampa a schermo ogni N misure

echo_commands = 0
INVALID_THRESHOLD = 9.0e37   # il Tektronix restituisce 9.91E37 se la misura non e' valida


# ============================================================
# FUNZIONI
# ============================================================

def instrument_connect(resource_mgr, resource_string, timeout,
                       do_id_query, do_reset, do_clear):
    instr = resource_mgr.open_resource(resource_string)
    instr.timeout = timeout

    if do_id_query:
        print(instrument_query(instr, "*IDN?"))
    if do_reset:
        instrument_write(instr, "*RST")
    if do_clear:
        instr.clear()

    return resource_mgr, instr


def instrument_write(instr, cmd):
    if echo_commands:
        print(cmd)
    instr.write(cmd)


def instrument_query(instr, cmd):
    if echo_commands:
        print(cmd)
    return instr.query(cmd)


def instrument_disconnect(instr):
    instr.close()


def misura_singola(instr, canale, tipo):
    """Imposta sorgente e tipo, poi legge il valore (misura immediata)."""
    instrument_write(instr, "MEASUrement:IMMed:SOURCE1 {}".format(canale))
    instrument_write(instr, "MEASUrement:IMMed:TYPe {}".format(tipo))
    valore = float(instrument_query(instr, "MEASUrement:IMMed:VALue?"))

    if abs(valore) > INVALID_THRESHOLD:
        return float("nan")   # misura non valida (nessun fronte, segnale assente, ecc.)
    return valore


# ============================================================
# MAIN
# ============================================================

os.makedirs("Data", exist_ok=True)

filename_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
filepath = "Data/{}_{}.txt".format(filename, filename_time)

resource_manager = visa.ResourceManager()
my_instr = None
count = 0

try:
    resource_manager, my_instr = instrument_connect(
        resource_manager, instrument_resource_string,
        20000,   # timeout ms
        1,       # *IDN?
        0,       # *RST (NON resettare: perderesti la configurazione dello scope)
        0        # clear
    )

    print("\nInizio acquisizione ({}): {}\n".format(CANALE, ", ".join(MISURE.keys())))

    time_start = time.time()

    with open(filepath, "w") as f:
        f.write("id,time," + ",".join(MISURE.keys()) + "\n")

        while (time.time() - time_start) < acq_time:
            valori = []
            for nome, tipo in MISURE.items():
                valori.append(misura_singola(my_instr, CANALE, tipo))

            elapsed = time.time() - time_start

            riga = "{},{:.6f},".format(count, elapsed)
            riga += ",".join("{:.12e}".format(v) for v in valori)
            f.write(riga + "\n")
            f.flush()

            if count % print_every == 0:
                dettagli = " | ".join(
                    "{}: {:.4e}".format(n, v) for n, v in zip(MISURE.keys(), valori)
                )
                print("N: {} | t: {:.2f} s | {}".format(count, elapsed, dettagli))

            count += 1
            time.sleep(sampling_interval)

    print("\nAcquisizione completata!")

except KeyboardInterrupt:
    print("\nAcquisizione interrotta dall'utente.")

except Exception as e:
    print("\nERRORE:", e)

finally:
    if my_instr is not None:
        instrument_disconnect(my_instr)
    resource_manager.close()

    print("Misure totali: {}".format(count))
    print("Dati salvati in: {}".format(filepath))

