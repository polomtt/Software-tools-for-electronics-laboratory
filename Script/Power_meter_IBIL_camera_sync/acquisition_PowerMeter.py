"""
Modulo di acquisizione dati dal powermeter Newport 2832C.
Contiene il thread di polling GPIB e le funzioni di comunicazione ZMQ.
"""

import time
import threading
from datetime import datetime

import pyvisa

GPIB_RESOURCE = 'GPIB0::5::INSTR'  # verifica indirizzo GPIB sul pannello strumento
QUERY_COMMAND = 'R_A?'
POLL_INTERVAL_S = 1.0


class AcquisitionThread(threading.Thread):
    """Interroga lo strumento ogni POLL_INTERVAL_S secondi e mette i dati in una coda."""

    def __init__(self, data_queue, stop_event, error_queue):
        super().__init__(daemon=True)
        self.data_queue = data_queue
        self.stop_event = stop_event
        self.error_queue = error_queue

    def run(self):
        try:
            rm = pyvisa.ResourceManager('@py')
            inst = rm.open_resource(GPIB_RESOURCE)
            inst.timeout = 5000
        except Exception as e:
            self.error_queue.put(f'Errore apertura strumento: {e}')
            return

        t0 = time.time()
        try:
            while not self.stop_event.is_set():
                loop_start = time.time()
                try:
                    response = inst.query(QUERY_COMMAND).strip()
                    value = float(response)
                    elapsed = time.time() - t0
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                    self.data_queue.put((timestamp, elapsed, value))
                except ValueError:
                    self.error_queue.put(f'Risposta non numerica: "{response}"')
                except Exception as e:
                    self.error_queue.put(f'Errore query: {e}')

                sleep_time = POLL_INTERVAL_S - (time.time() - loop_start)
                if sleep_time > 0:
                    self.stop_event.wait(sleep_time)
        finally:
            try:
                inst.close()
            except Exception:
                pass
