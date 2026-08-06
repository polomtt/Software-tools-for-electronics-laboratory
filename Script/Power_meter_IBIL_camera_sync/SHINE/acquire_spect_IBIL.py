#!/usr/bin/env python3

import time
import numpy as np
import matplotlib.pyplot as plt

from seabreeze.spectrometers import Spectrometer


# =========================
# Configurazione
# =========================

INTEGRATION_TIME_MS = 10   # tempo integrazione in millisecondi
CSV_FILENAME = "spettro_qe65000.csv"


# =========================
# Connessione spettrometro
# =========================

print("Connessione al QE65000...")

spec = Spectrometer.from_first_available()

print("Trovato:")
print("  Modello :", spec.model)
print("  Seriale :", spec.serial_number)

# tempo di integrazione in microsecondi
spec.integration_time_micros(INTEGRATION_TIME_MS * 1000)

print(f"Tempo integrazione: {INTEGRATION_TIME_MS} ms")


# =========================
# Prima acquisizione
# =========================

wavelengths = spec.wavelengths()
intensities = spec.intensities()


# =========================
# Grafico
# =========================

plt.ion()

fig, ax = plt.subplots(figsize=(10, 5))

line, = ax.plot(wavelengths, intensities, lw=1)

ax.set_xlabel("Lunghezza d'onda (nm)")
ax.set_ylabel("Intensità")
ax.set_title(
    f"Ocean Optics {spec.model} - {spec.serial_number}"
)

ax.grid(True)

plt.show()


# =========================
# Loop acquisizione
# =========================

print()
print("Comandi:")
print("  s = salva spettro CSV")
print("  q = esci")
print()

last_wavelengths = wavelengths
last_intensities = intensities


try:
    while True:

        # acquisizione
        intensities = spec.intensities()

        last_intensities = intensities

        # aggiorna grafico
        line.set_ydata(intensities)

        ax.relim()
        ax.autoscale_view()

        fig.canvas.draw()
        fig.canvas.flush_events()

        # controllo tastiera non bloccante
        key = input(
            "Comando (invio=continua, s=salva, q=esci): "
        )

        if key.lower() == "s":

            data = np.column_stack(
                (last_wavelengths, last_intensities)
            )

            np.savetxt(
                CSV_FILENAME,
                data,
                delimiter=",",
                header="wavelength_nm,intensity",
                comments=""
            )

            print(
                f"Spettro salvato in {CSV_FILENAME}"
            )


        elif key.lower() == "q":
            break


except KeyboardInterrupt:
    pass


finally:

    print("Chiusura spettrometro...")
    spec.close()

    plt.close()

    print("Fine.")
