import os
import time

import numpy as np
import matplotlib.pyplot as plt
import zmq

from seabreeze.spectrometers import Spectrometer
from zmq_comm import read_socket
from converto_nm_to_color import wavelength_to_hex

# ===========================
# Configurazione di default
# ===========================

INTEGRATION_TIME_MS_DEFAULT = 100  # tempo integrazione in millisecondi
NUMERO_HISTO_AVG_DEFAULT = 1       # quanti spettri mediare
PAUSE_S = 1.0                      # pausa tra un'acquisizione e la successiva
DATA_DIR = "Data"


# =========================
# Connessione spettrometro (una sola volta, all'avvio)
# =========================

print("Connessione allo spettrometro...")
spec = Spectrometer.from_first_available()

print("Trovato:")
print("  Modello :", spec.model)
print("  Seriale :", spec.serial_number)

spec.integration_time_micros(INTEGRATION_TIME_MS_DEFAULT * 1000)
print(f"Tempo integrazione default: {INTEGRATION_TIME_MS_DEFAULT} ms")
print(f"Numero spettri da mediare default: {NUMERO_HISTO_AVG_DEFAULT}")

wavelengths = spec.wavelengths()


def apply_params(time_integr, num_histo_avg):
    """Imposta tempo di integrazione e numero di spettri da mediare.

    Ritorna (time_integr_ms, n_avg) effettivamente usati. In caso di errore
    usa i default e stampa il motivo.
    """
    try:
        t_ms = int(round(float(time_integr)))
        n_avg = int(round(float(num_histo_avg)))
        if t_ms <= 0 or n_avg <= 0:
            raise ValueError(f"valori non validi (tempo={time_integr}, avg={num_histo_avg})")
        spec.integration_time_micros(t_ms * 1000)
        print(f"Tempo integrazione nuovo: {t_ms} ms")
        print(f"Numero spettri mediati nuovo: {n_avg}")
        return t_ms, n_avg
    except Exception as e:
        print(f"Errore caricamento nuovi parametri ({e})! Uso valori di default :(")
        spec.integration_time_micros(INTEGRATION_TIME_MS_DEFAULT * 1000)
        return INTEGRATION_TIME_MS_DEFAULT, NUMERO_HISTO_AVG_DEFAULT


def read_averaged_spectrum(n_avg):
    """Media a mano n_avg spettri (spec.scans_to_average non esiste in seabreeze)."""
    if n_avg <= 1:
        return spec.intensities()
    return np.mean([spec.intensities() for _ in range(n_avg)], axis=0)


def save_figure(fig, output_dir):
    if fig is None or output_dir is None:
        return
    try:
        fig.savefig(os.path.join(output_dir, "FIG_IBIL.png"), dpi=480)
    except Exception as e:
        print(f"Impossibile salvare la figura: {e}")


# =========================
# ZMQ
# =========================

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")
socket.subscribe("")
socket.setsockopt(zmq.RCVTIMEO, 1000)

plt.ion()

fig = None
ax_spec = None
ax_peak = None
output_dir = None  # cartella dell'acquisizione in corso

try:
    while True:
        # Attesa di un comando (RCVTIMEO = 1 s: zmq.Again fa da pausa)
        try:
            value, filename_part, time_integr, num_histo_avg, IBIL_activated = read_socket(socket)
        except zmq.Again:
            continue

        # Parte solo se start E IBIL attivato
        if not (value and IBIL_activated):
            continue

        output_dir = os.path.join(DATA_DIR, "IBIL_" + filename_part)
        os.makedirs(output_dir, exist_ok=True)

        t_integr_ms, n_avg = apply_params(time_integr, num_histo_avg)

        fig, (ax_spec, ax_peak) = plt.subplots(2, 1, figsize=(8, 8))

        num_histo = 0
        times = []
        peaks = []
        colors = []
        t0 = time.time()

        # ---- Loop di acquisizione ----
        while True:
            # ------------------------
            # Acquisizione reale dallo spettrometro
            # ------------------------
            intensities = read_averaged_spectrum(n_avg)
            t_acq = time.time() - t0

            np.savetxt(
                os.path.join(output_dir, f"histo_num{num_histo}.csv"),
                np.column_stack((wavelengths, intensities)),
                delimiter=",",
                fmt="%.4e",
                header=(
                    f"#Time_acq{t_acq:.3f}s\n"
                    f"#Integration_time:{t_integr_ms}ms,AVG_histo:{n_avg}\n"
                    "#Wavelength[nm],Intensity[counts]"
                ),
                comments="",
            )
            num_histo += 1

            # ------------------------
            # Spettro
            # ------------------------
            ax_spec.cla()
            lambda_max = wavelengths[np.argmax(intensities)]
            color = wavelength_to_hex(lambda_max)

            ax_spec.plot(wavelengths, intensities, lw=1, color=color)
            ax_spec.set_xlabel("Lunghezza d'onda (nm)")
            ax_spec.set_ylabel("Intensità")
            ax_spec.set_title(f"Ocean Optics {spec.model} - {spec.serial_number}")
            ax_spec.grid(True)

            # ------------------------
            # Picco in funzione del tempo
            # ------------------------
            peaks.append(intensities.max())
            times.append(t_acq)
            colors.append(color)

            ax_peak.cla()
            ax_peak.plot(times, peaks, "-", color="gray", lw=1, zorder=1)           # linea di collegamento
            ax_peak.scatter(times, peaks, c=colors, s=30, zorder=2)                 # punti colorati
            ax_peak.set_xlabel("Time [s]")
            ax_peak.set_ylabel("Peak height")
            ax_peak.grid(True) height")
            ax_peak.grid(True)

            fig.tight_layout()
            fig.canvas.draw_idle()
            plt.pause(0.01)

            # ------------------------
            # Pausa + controllo comando di stop, senza bloccare:
            # poll() esce subito se arriva un messaggio, altrimenti dopo PAUSE_S
            # ------------------------
            stop_requested = False
            if socket.poll(int(PAUSE_S * 1000)):
                try:
                    value, _, _, _, IBIL_activated = read_socket(socket)
                except zmq.Again:
                    value = True
                if not value:
                    stop_requested = True

            if stop_requested:
                save_figure(fig, output_dir)
                plt.close(fig)
                fig = None
                ax_spec = None
                ax_peak = None
                output_dir = None
                print("Acquisizione IBIL terminata.")
                break

except KeyboardInterrupt:
    print("\nChiusura richiesta dall'utente")

finally:
    # Se si esce con Ctrl+C durante un'acquisizione, salva comunque la figura
    save_figure(fig, output_dir)
    if fig is not None:
        plt.close(fig)

    socket.close()
    context.term()

    print("Chiusura spettrometro...")
    spec.close()

# import zmq
# import json
# import time
# import numpy as np
# import matplotlib.pyplot as plt

# import os

# from seabreeze.spectrometers import Spectrometer
# from zmq_comm import read_socket
# from converto_nm_to_color import wavelength_to_hex

# # ===========================
# # Configurazione di default
# # ===========================

# INTEGRATION_TIME_MS_DEFAULT = 100  # tempo integrazione in millisecondi
# NUMERO_HISTO_AVG_DEFAULT    = 1    # quanti histogrammi mediare


# # =========================
# # Connessione spettrometro (una sola volta, all'avvio)
# # =========================

# print("Connessione allo spettrometro...")
# spec = Spectrometer.from_first_available()

# print("Trovato:")
# print("  Modello :", spec.model)
# print("  Seriale :", spec.serial_number)

# spec.integration_time_micros(INTEGRATION_TIME_MS_DEFAULT * 1000)
# print(f"Tempo integrazione default: {INTEGRATION_TIME_MS_DEFAULT} ms")

# spec.scans_to_average = NUMERO_HISTO_AVG_DEFAULT
# print(f"Numero histo per mediare: {NUMERO_HISTO_AVG_DEFAULT}")

# wavelengths = spec.wavelengths()


# # =========================
# # ZMQ
# # =========================

# context = zmq.Context()
# socket = context.socket(zmq.SUB)
# socket.connect("tcp://localhost:5555")
# socket.subscribe("")
# socket.setsockopt(zmq.RCVTIMEO, 1000)

# plt.ion()

# fig = None
# ax_spec = None
# ax_peak = None

# filename_part = "fip.png"

# times = []
# peaks = []
# t0 = time.time()

# try:
#     while True:
#         try:
#             value, filename_part, time_integr, num_histo_avg, IBIL_activated = read_socket(socket)

#             output_dir = os.path.join("Data", "IBIL_" + filename_part)
#             os.makedirs(output_dir, exist_ok=True)

#             num_histo = 0 
#             try:
#                 spec.integration_time_micros(time_integr * 1000)
#                 print(f"Tempo integrazione nuovo: {time_integr} ms")

#                 spec.scans_to_average = num_histo_avg
#                 print(f"Numero histo per nuovo: {num_histo_avg}")
#             except:
#                 print("Errore caricamento nuovi parametri! Uso valori di default :( ")
#                 spec.integration_time_micros(INTEGRATION_TIME_MS_DEFAULT * 1000)
#                 spec.scans_to_average = NUMERO_HISTO_AVG_DEFAULT               

#             if value:

#                 # Crea la figura solo la prima volta che si attiva l'acquisizione
#                 if fig is None:
#                     fig, (ax_spec, ax_peak) = plt.subplots(2, 1, figsize=(8, 8))

#                 times = []
#                 peaks = []
#                 t0 = time.time()

#                 while True:

#                     # Controlla se è arrivato un nuovo comando (stop)
#                     try:
#                         value, filename_part, time_integr, num_histo_avg, IBIL_activated = read_socket(socket)

#                         output_dir = os.path.join("Data", "IBIL_" + filename_part)
#                         os.makedirs(output_dir, exist_ok=True)

#                         num_histo = 0 
#                         try:
#                             spec.integration_time_micros(time_integr * 1000)
#                             print(f"Tempo integrazione nuovo: {time_integr} ms")

#                             spec.scans_to_average = num_histo_avg
#                             print(f"Numero histo per nuovo: {num_histo_avg}")
#                         except:
#                             print("Errore caricamento nuovi parametri! Uso valori di default :( ")
#                             spec.integration_time_micros(INTEGRATION_TIME_MS_DEFAULT * 1000)
#                             spec.scans_to_average = NUMERO_HISTO_AVG_DEFAULT     

#                         if not value:
#                             plt.close(fig)
#                             fig = None
#                             ax_spec = None
#                             ax_peak = None
#                             break

#                     except zmq.Again:
#                         pass

#                     # ------------------------
#                     # Acquisizione reale dallo spettrometro
#                     # ------------------------
#                     intensities = spec.intensities()

#                     # ------------------------
#                     # Spettro
#                     # ------------------------
#                     ax_spec.cla()

#                     idx_max = np.argmax(intensities)
#                     lambda_max = wavelengths[idx_max]
                    
#                     ax_spec.plot(wavelengths, intensities, lw=1,color=wavelength_to_hex(lambda_max))
                    
#                     np.savetxt(
#                                 "Data/IBIL_{}/histo_num{}.csv".format(filename_part,num_histo),
#                                 np.column_stack((wavelengths, intensities)),
#                                 delimiter=",",
#                                 fmt="%.4e",
#                                 header="#Time_acq{:.3f}s\n#Integration_time:{}ms,AVG_histo:{}\n#Wavelength[nm],Intensity[counts]".format(time.time() - t0,time_integr, num_histo_avg),
#                                 comments=""
#                             )
#                     num_histo = num_histo +1
#                     ax_spec.set_xlabel("Lunghezza d'onda (nm)")
#                     ax_spec.set_ylabel("Intensità")
#                     ax_spec.set_title(f"Ocean Optics {spec.model} - {spec.serial_number}")
#                     ax_spec.grid(True)

#                     # Altezza massima dello spettro
#                     peak = intensities.max()

#                     peaks.append(peak)
#                     times.append(time.time() - t0)

#                     # ------------------------
#                     # Picco in funzione del tempo
#                     # ------------------------
#                     ax_peak.cla()

#                     ax_peak.plot(times, peaks, "-o")

#                     ax_peak.set_xlabel("Time [s]")
#                     ax_peak.set_ylabel("Peak hight")
#                     ax_peak.grid(True)

#                     # Aggiorna finestra
#                     fig.tight_layout()
#                     fig.canvas.draw_idle()
#                     plt.pause(0.01)

#                     time.sleep(1)

#             else:
#                 time.sleep(1)

#         except zmq.Again:
#             time.sleep(1)

# except KeyboardInterrupt:
#     print("\nChiusura richiesta dall'utente")

# finally:
#     if fig is not None:
#         plt.savefig("Data/IBIL_{}/FIG_IBIL.png".format(filename_part),dpi=480)
#         plt.close(fig)
        

#     socket.close()
#     context.term()

#     print("Chiusura spettrometro...")
#     spec.close()
