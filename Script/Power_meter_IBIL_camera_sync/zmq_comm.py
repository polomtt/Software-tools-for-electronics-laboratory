"""
Modulo di comunicazione ZMQ tra questa applicazione e il processo di
acquisizione IBIL.
"""

import json
import zmq

ZMQ_BIND_ADDRESS = "tcp://*:5555"

def create_socket(bind_address=ZMQ_BIND_ADDRESS):
    """Crea contesto e socket ZMQ (tipo PUB) e lo mette in bind sull'indirizzo dato.

    Ritorna la coppia (context, socket): il context va tenuto in vita finche'
    il socket e' in uso e chiuso a fine programma con context.term().
    """
    context = zmq.Context()
    socket = context.socket(zmq.PUB)
    socket.bind(bind_address)
    return context, socket


def close_socket(context, socket):
    """Chiude ordinatamente socket e contesto ZMQ."""
    socket.close()
    context.term()

def send_true(socket, filename, integration_time, avg_spectrum):
    message = {"value": True, "filename": filename, "integration_time": integration_time, "avg_spectrum": avg_spectrum}
    socket.send_string(json.dumps(message))

def send_false(socket):
    message = {"value": False, "filename": "", "integration_time": 100, "avg_spectrum": 1}
    socket.send_string(json.dumps(message))



def read_socket(socket):
    message = socket.recv_string()
    data = json.loads(message)
    return data["value"], data["filename"], data["integration_time"], data["avg_spectrum"]

