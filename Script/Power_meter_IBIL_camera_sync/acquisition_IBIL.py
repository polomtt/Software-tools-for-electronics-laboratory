import zmq
import json
import time
import numpy as np
import matplotlib.pyplot as plt

from seabreeze.spectrometers import Spectrometer
from zmq_comm import read_socket
from converto_nm_to_color import wavelength_to_hex

# ===========================
# Configurazione di default
# ===========================

INTEGRATION_TIME_MS_DEFAULT = 100  # tempo integrazione in millisecondi
NUMERO_HISTO_AVG_DEFAULT    = 1    # quanti histogrammi mediare


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

spec.scans_to_average = NUMERO_HISTO_AVG_DEFAULT
print(f"Numero histo per mediare: {NUMERO_HISTO_AVG_DEFAULT}")

wavelengths = spec.wavelengths()


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

filename_part = "fip.png"

times = []
peaks = []
t0 = time.time()

try:
    while True:
        try:
            value, filename_part, time_integr, num_histo_avg = read_socket(socket)
            num_histo = 0 
            try:
                spec.integration_time_micros(time_integr * 1000)
                print(f"Tempo integrazione nuovo: {time_integr} ms")

                spec.scans_to_average = num_histo_avg
                print(f"Numero histo per nuovo: {num_histo_avg}")
            except:
                print("Errore caricamento nuovi parametri! Uso valori di default :( ")
                spec.integration_time_micros(INTEGRATION_TIME_MS_DEFAULT * 1000)
                spec.scans_to_average = NUMERO_HISTO_AVG_DEFAULT               

            if value:

                # Crea la figura solo la prima volta che si attiva l'acquisizione
                if fig is None:
                    fig, (ax_spec, ax_peak) = plt.subplots(2, 1, figsize=(8, 8))

                times = []
                peaks = []
                t0 = time.time()

                while True:

                    # Controlla se è arrivato un nuovo comando (stop)
                    try:
                        value, filename_part, time_integr, num_histo_avg  = read_socket(socket)
                        num_histo = 0 
                        try:
                            spec.integration_time_micros(time_integr * 1000)
                            print(f"Tempo integrazione nuovo: {time_integr} ms")

                            spec.scans_to_average = num_histo_avg
                            print(f"Numero histo per nuovo: {num_histo_avg}")
                        except:
                            print("Errore caricamento nuovi parametri! Uso valori di default :( ")
                            spec.integration_time_micros(INTEGRATION_TIME_MS_DEFAULT * 1000)
                            spec.scans_to_average = NUMERO_HISTO_AVG_DEFAULT     

                        if not value:
                            plt.close(fig)
                            fig = None
                            ax_spec = None
                            ax_peak = None
                            break

                    except zmq.Again:
                        pass

                    # ------------------------
                    # Acquisizione reale dallo spettrometro
                    # ------------------------
                    intensities = spec.intensities()

                    # ------------------------
                    # Spettro
                    # ------------------------
                    ax_spec.cla()

                    idx_max = np.argmax(intensities)
                    lambda_max = wavelengths[idx_max]
                    
                    ax_spec.plot(wavelengths, intensities, lw=1,color=wavelength_to_hex(lambda_max))
                    
                    np.savetxt(
                                "Data/IBIL_{}/histo_num{}.csv".format(filename_part,num_histo),
                                np.column_stack((wavelengths, intensities)),
                                delimiter=",",
                                fmt="%.4e",
                                header="#Time_acq{:.3f}s\n#Integration_time:{}ms,AVG_histo:{}\n#Wavelength[nm],Intensity[counts]".format(time.time() - t0,time_integr, num_histo_avg),
                                comments=""
                            )
                    num_histo = num_histo +1
                    ax_spec.set_xlabel("Lunghezza d'onda (nm)")
                    ax_spec.set_ylabel("Intensità")
                    ax_spec.set_title(f"Ocean Optics {spec.model} - {spec.serial_number}")
                    ax_spec.grid(True)

                    # Altezza massima dello spettro
                    peak = intensities.max()

                    peaks.append(peak)
                    times.append(time.time() - t0)

                    # ------------------------
                    # Picco in funzione del tempo
                    # ------------------------
                    ax_peak.cla()

                    ax_peak.plot(times, peaks, "-o")

                    ax_peak.set_xlabel("Tempo [s]")
                    ax_peak.set_ylabel("Altezza picco")
                    ax_peak.grid(True)

                    # Aggiorna finestra
                    fig.tight_layout()
                    fig.canvas.draw_idle()
                    plt.pause(0.01)

                    time.sleep(1)

            else:
                time.sleep(1)

        except zmq.Again:
            time.sleep(1)

except KeyboardInterrupt:
    print("\nChiusura richiesta dall'utente")

finally:
    if fig is not None:
        plt.savefig("Data/IBIL_{}/FIG_IBIL.png".format(filename_part),dpi=480)
        plt.close(fig)
        

    socket.close()
    context.term()

    print("Chiusura spettrometro...")
    spec.close()
