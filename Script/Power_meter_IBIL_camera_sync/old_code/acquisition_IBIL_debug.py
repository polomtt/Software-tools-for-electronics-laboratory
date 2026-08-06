import zmq
import json
import time
import numpy as np
import matplotlib.pyplot as plt


def read_bool(socket):
    message = socket.recv_string()
    data = json.loads(message)
    print(data)
    return data["value"], data["filename"]


context = zmq.Context()

socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")
socket.subscribe("")

# aspetta massimo 1 secondo sulla recv
socket.setsockopt(zmq.RCVTIMEO, 1000)

plt.ion()

fig = None
ax_hist = None
ax_peak = None

times = []
peaks = []
t0 = time.time()

try:
    while True:
        try:
            value, filename_part = read_bool(socket)
            
            if value:

                # Crea la figura solo la prima volta
                if fig is None:
                    fig, (ax_hist, ax_peak) = plt.subplots(
                        2, 1, figsize=(8, 8)
                    )

                    times = []
                    peaks = []
                    t0 = time.time()

                while True:

                    # Controlla se è arrivato un nuovo comando
                    try:
                        value, filename_part = read_bool(socket)

                        if not value:
                            plt.close(fig)
                            fig = None
                            ax_hist = None
                            ax_peak = None
                            break

                    except zmq.Again:
                        pass


                    # Genera dati casuali
                    data = np.random.normal(30, 5, 10000)


                    # ------------------------
                    # Istogramma
                    # ------------------------
                    ax_hist.cla()

                    counts, bins, _ = ax_hist.hist(
                        data,
                        bins=100,
                        range=(0, 100)
                    )

                    ax_hist.set_xlim(0, 100)
                    ax_hist.set_ylim(0, 900)
                    ax_hist.set_ylabel("Conteggi")
                    ax_hist.set_title("Distribuzione corrente")


                    # Altezza gaussiana
                    peak = counts.max()

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
        plt.close(fig)

    socket.close()
    context.term()