import os
import time
from datetime import datetime

import zmq

from zmq_comm import read_socket

# =========================
# ZMQ
# =========================

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")
socket.subscribe("")
socket.setsockopt(zmq.RCVTIMEO, 1000)

# =========================
# File di log
# =========================

folder = "logger"
os.makedirs(folder, exist_ok=True)

log_filename = os.path.join(folder, f"logger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
# utf-8 necessario per i simboli ✔/✕ (su Windows l'encoding di default è cp1252)
logfile = open(log_filename, "w", encoding="utf-8")

logfile.write(
    f"{'Id':>6} | "
    f"{'Datetime':<19} | "
    f"{'Sample':<25} | "
    f"{'Beam_I':>6} | "
    f"{'IBIL':>4} | "
    f"{'Integr[ms]':>11} | "
    f"{'Avg':>6} | "
    f"{'Tacq [s]':>10} |\n"
)
logfile.flush()


def parse_filename_part(filename_part):
    """Da 'YYYYMMDD_HHMMSS_<sample>_<corrente>' ricava (datetime, sample, corrente).

    Il sample può contenere '_': si spezza solo sui primi due '_' (timestamp)
    e sull'ultimo (corrente).
    """
    date, hour, rest = filename_part.split("_", 2)
    sample_used, current_used = rest.rsplit("_", 1)
    dt = datetime.strptime(f"{date} {hour}", "%Y%m%d %H%M%S")
    return dt.strftime("%Y/%m/%d %H:%M:%S"), sample_used, current_used


def close_open_row(text):
    """Completa la riga lasciata aperta (colonna Tacq + a capo)."""
    logfile.write(f"{text:>10} |\n")
    logfile.flush()


id_file = 0          # id dell'ultima acquisizione registrata
run_open = False     # True se c'è una riga iniziata e non ancora chiusa
t0 = 0.0

try:
    while True:
        try:
            value, filename_part, time_integr, num_histo_avg, IBIL_activated = read_socket(socket)
        except zmq.Again:
            continue  # il timeout di 1 s fa già da pausa

        if value:
            # Nuovo start: se la precedente non era stata chiusa, chiudila
            if run_open:
                close_open_row("n/d")
                run_open = False

            try:
                time_formatted, sample_used, current_used = parse_filename_part(filename_part)
            except ValueError:
                print(f"Nome file non interpretabile: '{filename_part}'")
                time_formatted = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
                sample_used = filename_part
                current_used = "?"

            if IBIL_activated:
                IBIL_status = "✔"
                integr_txt = f"{int(round(float(time_integr)))}"
                avg_txt = f"{int(round(float(num_histo_avg)))}"
            else:
                IBIL_status = "✕"
                integr_txt = "-"
                avg_txt = "-"

            id_file += 1
            logfile.write(
                f"{id_file:>6} | "
                f"{time_formatted:<19} | "
                f"{sample_used:<25} | "
                f"{current_used:>6} | "
                f"{IBIL_status:>4} | "
                f"{integr_txt:>11} | "
                f"{avg_txt:>6} | "
            )
            logfile.flush()

            run_open = True
            t0 = time.time()

        else:
            # Stop senza start visto: nessuna riga da completare
            if not run_open:
                continue

            elapsed = int(time.time() - t0)
            close_open_row(str(elapsed))
            run_open = False
            print(f"Flusso dati file id: {id_file}")

except KeyboardInterrupt:
    print("\nChiusura richiesta dall'utente :)")

finally:
    # Se si esce durante un'acquisizione, non lasciare la riga monca
    if run_open:
        close_open_row(str(int(time.time() - t0)) + "*")
    logfile.close()
    socket.close()
    context.term()

    print("Chiusura Logger :)")

# import zmq
# import json
# import time
# from datetime import datetime

# from zmq_comm import read_socket
# from converto_nm_to_color import wavelength_to_hex

# import os

# # =========================
# # ZMQ
# # =========================

# context = zmq.Context()
# socket = context.socket(zmq.SUB)
# socket.connect("tcp://localhost:5555")
# socket.subscribe("")
# socket.setsockopt(zmq.RCVTIMEO, 1000)

# t0 = 0

# id_file = 1
# folder = "logger"
# os.makedirs(folder, exist_ok=True)

# log_filename = f"logger/logger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
# logfile = open(log_filename, "w")

# logfile.write(
#     f"{'Id':>6} | "
#     f"{'Datetime':<19} | "
#     f"{'Sample':<25} | "
#     f"{'Beam_I':>6} | "
#     f"{'IBIL':>4} | "
#     f"{'Integr[ms]':>11} | "
#     f"{'Avg':>6} |"
#     f"{'Tacq [s]':>10} |\n"
# )

# logfile.flush()

# try:
#     while True:
        
#         try:
#             value, filename_part, time_integr, num_histo_avg, IBIL_activated  = read_socket(socket)
#             num_histo = 0 
            
#             if value:
#                 ibil_file = "IBIL_{}".format(filename_part)
#                 info_vect = filename_part.split("_")

#                 timestamp = info_vect[0]+" "+info_vect[1]
#                 dt = datetime.strptime(timestamp, "%Y%m%d %H%M%S")
#                 time_formatted = dt.strftime("%Y/%m/%d %H:%M:%S")
                
#                 sample_used = info_vect[2]
#                 current_used = info_vect[3]
#                 IBIL_status =""
                
#                 if IBIL_activated:
#                     IBIL_status = 	"✔"
#                 else:
#                     IBIL_status = 	"✕"

#                 logfile.write(
#                     f"{id_file:>6} | "
#                     f"{time_formatted:<19} | "
#                     f"{sample_used:<25} | "
#                     f"{current_used:>6} | "
#                     f"{IBIL_status:>4} | "
#                     f"{time_integr:>11} | "
#                     f"{num_histo_avg:>6} |"
#                 )
                
                
#                 logfile.flush()
                
#                 id_file = id_file +1
#                 t0 = time.time()
#             else:

#                 elapsed = int(time.time() - t0)

#                 logfile.write(f"{elapsed:>10} |\n")
#                 logfile.flush()
#                 print("Flusso dati file id: {}".format(id_file))


#         except zmq.Again:
#             time.sleep(1)

# except KeyboardInterrupt:
#     print("\nChiusura richiesta dall'utente :)")

# finally:
#     logfile.close()
#     socket.close()
#     context.term()

#     print("Chiusura Logger :)")

