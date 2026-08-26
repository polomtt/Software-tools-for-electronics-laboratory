"""
errors.py
=========
Eccezioni condivise tra i vari driver (module_driver.py, hvwrapper_driver.py, ...)
cosi' main.py puo' riconoscerle con un solo isinstance() indipendentemente
da quale driver le ha sollevate.
"""


class ConnectionError_(Exception):
    """Errore di connessione/comunicazione con un modulo CAEN (di qualunque tipo)."""
