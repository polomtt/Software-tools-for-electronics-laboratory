import zmq
import json
import time
from datetime import datetime

from zmq_comm import read_socket
from converto_nm_to_color import wavelength_to_hex

import os

# =========================
# ZMQ
# =========================

context = zmq.Context()
socket = context.socket(zmq.SUB)
socket.connect("tcp://localhost:5555")
socket.subscribe("")
socket.setsockopt(zmq.RCVTIMEO, 1000)

t0 = 0

id_file = 1
folder = "logger"
os.makedirs(folder, exist_ok=True)

log_filename = f"logger/logger_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
logfile = open(log_filename, "w")

logfile.write(
    f"{'Id':>6} | "
    f"{'Datetime':<19} | "
    f"{'Sample':<25} | "
    f"{'Beam_I':>6} | "
    f"{'IBIL':>4} | "
    f"{'Integr[ms]':>11} | "
    f"{'Avg':>6} |"
    f"{'Tacq [s]':>10} |\n"
)

logfile.flush()

try:
    while True:
        
        try:
            value, filename_part, time_integr, num_histo_avg, IBIL_activated  = read_socket(socket)
            num_histo = 0 
            
            if value:
                ibil_file = "IBIL_{}".format(filename_part)
                info_vect = filename_part.split("_")

                timestamp = info_vect[0]+" "+info_vect[1]
                dt = datetime.strptime(timestamp, "%Y%m%d %H%M%S")
                time_formatted = dt.strftime("%Y/%m/%d %H:%M:%S")
                
                sample_used = info_vect[2]
                current_used = info_vect[3]
                IBIL_status =""
                
                if IBIL_activated:
                    IBIL_status = 	"✔"
                else:
                    IBIL_status = 	"✕"

                logfile.write(
                    f"{id_file:>6} | "
                    f"{time_formatted:<19} | "
                    f"{sample_used:<25} | "
                    f"{current_used:>6} | "
                    f"{IBIL_status:>4} | "
                    f"{time_integr:>11} | "
                    f"{num_histo_avg:>6} |"
                )
                
                
                logfile.flush()
                
                id_file = id_file +1
                t0 = time.time()
            else:

                elapsed = int(time.time() - t0)

                logfile.write(f"{elapsed:>10} |\n")
                logfile.flush()
                print("Flusso dati file id: {}".format(id_file))


        except zmq.Again:
            time.sleep(1)

except KeyboardInterrupt:
    print("\nChiusura richiesta dall'utente :)")

finally:
    logfile.close()
    socket.close()
    context.term()

    print("Chiusura Logger :)")

