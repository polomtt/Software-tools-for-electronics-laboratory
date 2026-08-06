"""
Entry point dell'applicazione: crea il contesto ZMQ e avvia la GUI.
"""

import time

from gui import App
from zmq_comm import create_socket, close_socket


def main():
    context, socket = create_socket()

    time.sleep(1)

    app = App(socket)
    app.protocol('WM_DELETE_WINDOW', app.on_close)
    app.mainloop()

    close_socket(context, socket)


if __name__ == '__main__':
    main()
