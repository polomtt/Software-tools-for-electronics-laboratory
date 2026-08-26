#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GUI di acquisizione per camera The Imaging Source DFK 33UX178 (Ubuntu).

La camera viene vista da Ubuntu come un normale device V4L2/UVC
(es. /dev/video2), quindi si accede con OpenCV: nessun bisogno di
tiscamera/GStreamer/PyGObject.

Requisiti:
    pip install opencv-python numpy Pillow ttkbootstrap --break-system-packages
    sudo apt install v4l-utils     # per elencare correttamente le camere per nome

Per capire quale device è la DFK (utile solo per debug manuale):
    v4l2-ctl --list-devices

FUNZIONAMENTO SOCKET:
    Il programma apre un server TCP (default 0.0.0.0:5050) che resta in
    ascolto per TUTTA la durata dell'esecuzione. Chi si connette può
    inviare un pacchetto JSON terminato da newline, del tipo:

        {"filename": "campione_042"}

    Il nome ricevuto diventa il nome base del prossimo scatto (o serie
    di scatti). Il campo "Nome file" nella GUI si aggiorna in automatico.
"""

import os
import re
import cv2
import json
import time
import socket
import queue
import subprocess
import threading
import numpy as np
import tkinter as tk
from tkinter import filedialog, messagebox
from datetime import datetime
from PIL import Image, ImageTk

import ttkbootstrap as tb
from ttkbootstrap.constants import *

# Parole chiave usate per riconoscere automaticamente la DFK tra le camere
# collegate. Se il nome della tua camera non viene riconosciuto, aggiungi
# qui una parola presente nell'output di 'v4l2-ctl --list-devices'.
PAROLE_CHIAVE_CAMERA = ["33UX178", "33U", "DFK", "IMAGING SOURCE", "TIS"]


def elenca_dispositivi_video():
    """Interroga v4l2-ctl per ottenere {nome_camera: [/dev/videoN, ...]}.
    Ritorna un dizionario vuoto se v4l2-ctl non è installato o non trova nulla."""
    dispositivi = {}
    try:
        output = subprocess.run(
            ["v4l2-ctl", "--list-devices"],
            capture_output=True, text=True, timeout=5
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return dispositivi

    blocco_corrente = None
    for riga in output.splitlines():
        if riga.strip() == "":
            continue
        if not riga.startswith("\t") and not riga.startswith(" "):
            nome = re.sub(r"\s*\(.*\)\s*:?\s*$", "", riga).strip()
            blocco_corrente = nome
            dispositivi[blocco_corrente] = []
        elif blocco_corrente is not None and "/dev/video" in riga:
            dispositivi[blocco_corrente].append(riga.strip())
    return dispositivi


def sembra_essere_la_dfk(nome_camera):
    nome_upper = nome_camera.upper()
    return any(parola in nome_upper for parola in PAROLE_CHIAVE_CAMERA)


class CameraController:
    """Wrapper attorno a cv2.VideoCapture per la DFK 33UX178 (device V4L2)."""

    def __init__(self, device="/dev/video0", log_fn=print):
        self.device = device
        self.log = log_fn
        self.cap = None
        self._lock = threading.Lock()

    def apri(self, device=None):
        if device is not None:
            self.device = device
        with self._lock:
            if self.cap is not None:
                self.cap.release()
            self.cap = cv2.VideoCapture(self.device, cv2.CAP_V4L2)
            if self.cap.isOpened():
                larghezza = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                altezza = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        if not self.cap.isOpened():
            raise RuntimeError(
                f"Impossibile aprire {self.device}. "
                f"Controlla con 'v4l2-ctl --list-devices' quale path usare."
            )
        self.log(f"Camera aperta su {self.device} — risoluzione rilevata: {larghezza}x{altezza}")

    def chiudi(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def imposta_esposizione(self, valore):
        if self.cap is None:
            raise RuntimeError("Camera non aperta.")
        with self._lock:
            self.cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1)
            self.cap.set(cv2.CAP_PROP_EXPOSURE, float(valore))
        self.log(f"Esposizione impostata a {valore}")

    def imposta_gain(self, valore):
        if self.cap is None:
            raise RuntimeError("Camera non aperta.")
        with self._lock:
            self.cap.set(cv2.CAP_PROP_GAIN, float(valore))
        self.log(f"Gain impostato a {valore}")

    def leggi_frame(self):
        if self.cap is None:
            return None
        with self._lock:
            ret, frame = self.cap.read()
        return frame if ret else None

    def scatta(self, path_file):
        frame = self.leggi_frame()
        if frame is None:
            raise RuntimeError("Nessun frame disponibile dalla camera.")
        cv2.imwrite(path_file, frame)


class ServerNomeFile(threading.Thread):
    def __init__(self, host, port, callback_nome, log_fn=print):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.callback_nome = callback_nome
        self.log = log_fn
        self._stop_event = threading.Event()
        self._server_sock = None

    def run(self):
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self.host, self.port))
        self._server_sock.listen(5)
        self._server_sock.settimeout(1.0)
        self.log(f"Server in ascolto su {self.host}:{self.port}")

        while not self._stop_event.is_set():
            try:
                conn, addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(target=self._gestisci_client, args=(conn, addr), daemon=True).start()

        if self._server_sock:
            self._server_sock.close()

    def _gestisci_client(self, conn, addr):
        buffer = b""
        with conn:
            conn.settimeout(5.0)
            try:
                while True:
                    dati = conn.recv(4096)
                    if not dati:
                        break
                    buffer += dati
                    while b"\n" in buffer:
                        riga, buffer = buffer.split(b"\n", 1)
                        self._processa_riga(riga, addr)
            except socket.timeout:
                pass
            if buffer.strip():
                self._processa_riga(buffer, addr)

    def _processa_riga(self, riga, addr):
        try:
            testo = riga.decode("utf-8").strip()
            if not testo:
                return
            pacchetto = json.loads(testo)
            nome = pacchetto.get("filename")
            if nome:
                self.log(f"Ricevuto da {addr}: nome file = '{nome}'")
                self.callback_nome(nome)
            else:
                self.log(f"Pacchetto da {addr} senza campo 'filename': {pacchetto}")
        except json.JSONDecodeError:
            self.log(f"Pacchetto non JSON valido da {addr}: {riga!r}")

    def stop(self):
        self._stop_event.set()
        if self._server_sock:
            try:
                self._server_sock.close()
            except OSError:
                pass


class App(tb.Window):
    def __init__(self):
        super().__init__(themename="darkly")
        self.title("DFK 33UX178 — Acquisizione")
        self.geometry("620x760")
        self.resizable(False, False)

        self.coda_log = queue.Queue()
        self.cam = CameraController(log_fn=self._log_da_thread)
        self.nome_file_corrente = tk.StringVar(value="scatto")
        self.cartella_output = tk.StringVar(value=os.path.join(os.getcwd(), "foto"))
        self.dispositivi_disponibili = {}

        self._costruisci_gui()
        self._aggiorna_elenco_camere()
        self._avvia_camera()
        self._avvia_server_socket()
        self.after(150, self._svuota_coda_log)
        self.after(1000, self._aggiorna_anteprima)

    # ---------------------- costruzione GUI ----------------------
    def _costruisci_gui(self):
        contenitore = tb.Frame(self, padding=16)
        contenitore.pack(fill=BOTH, expand=YES)

        tb.Label(contenitore, text="📷 DFK 33UX178", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        tb.Label(contenitore, text="Controllo acquisizione", font=("Segoe UI", 10),
                 bootstyle="secondary").pack(anchor="w", pady=(0, 12))

        # ---- Camera ----
        box_cam = tb.Labelframe(contenitore, text=" Camera ", padding=12, bootstyle="info")
        box_cam.pack(fill=X, pady=6)

        riga = tb.Frame(box_cam)
        riga.pack(fill=X)
        self.var_camera_scelta = tk.StringVar(value="")
        self.combo_camere = tb.Combobox(riga, textvariable=self.var_camera_scelta,
                                         state="readonly", bootstyle="info")
        self.combo_camere.pack(side=LEFT, fill=X, expand=YES, padx=(0, 8))
        self.combo_camere.bind("<<ComboboxSelected>>", self._cambia_camera)
        tb.Button(riga, text="⟳ Aggiorna", command=self._aggiorna_elenco_camere,
                  bootstyle="info-outline", width=10).pack(side=LEFT)

        self.label_stato_camera = tb.Label(box_cam, text="● Nessuna camera aperta",
                                            bootstyle="secondary")
        self.label_stato_camera.pack(anchor="w", pady=(8, 0))

        # ---- Configurazione ----
        box_conf = tb.Labelframe(contenitore, text=" Impostazioni acquisizione ", padding=12, bootstyle="primary")
        box_conf.pack(fill=X, pady=6)
        box_conf.columnconfigure(1, weight=1)

        self.var_esposizione = tk.StringVar(value="-4")
        self.var_gain = tk.StringVar(value="0")
        self.var_num_scatti = tk.StringVar(value="1")
        self.var_intervallo = tk.StringVar(value="1.0")

        campi = [
            ("Esposizione", self.var_esposizione),
            ("Gain", self.var_gain),
            ("N. scatti consecutivi", self.var_num_scatti),
            ("Intervallo tra scatti (s)", self.var_intervallo),
        ]
        for i, (etichetta, var) in enumerate(campi):
            tb.Label(box_conf, text=etichetta).grid(row=i, column=0, sticky="w", pady=4)
            tb.Entry(box_conf, textvariable=var).grid(row=i, column=1, sticky="ew", padx=(10, 0), pady=4)

        tb.Button(box_conf, text="Applica impostazioni camera", command=self._applica_impostazioni,
                  bootstyle="primary-outline").grid(row=len(campi), column=0, columnspan=2, sticky="ew", pady=(10, 0))

        # ---- Anteprima ----
        box_prev = tb.Labelframe(contenitore, text=" Anteprima live (1 fps) ", padding=8, bootstyle="secondary")
        box_prev.pack(fill=X, pady=6)
        self.label_anteprima = tb.Label(box_prev, text="In attesa del primo frame...", anchor="center")
        self.label_anteprima.pack(pady=4)

        # ---- Salvataggio ----
        box_file = tb.Labelframe(contenitore, text=" Salvataggio ", padding=12, bootstyle="secondary")
        box_file.pack(fill=X, pady=6)
        box_file.columnconfigure(1, weight=1)

        tb.Label(box_file, text="Cartella output").grid(row=0, column=0, sticky="w", pady=4)
        tb.Entry(box_file, textvariable=self.cartella_output).grid(row=0, column=1, sticky="ew", padx=(10, 6), pady=4)
        tb.Button(box_file, text="Sfoglia", command=self._scegli_cartella,
                  bootstyle="secondary-outline").grid(row=0, column=2, pady=4)

        tb.Label(box_file, text="Nome file").grid(row=1, column=0, sticky="w", pady=4)
        tb.Entry(box_file, textvariable=self.nome_file_corrente).grid(
            row=1, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)
        tb.Label(box_file, text="↳ può arrivare anche via socket JSON su porta 5050",
                 bootstyle="secondary", font=("Segoe UI", 8)).grid(row=2, column=1, columnspan=2, sticky="w")

        # ---- Start ----
        self.btn_start = tb.Button(contenitore, text="▶  START", command=self._avvia_sequenza_scatti,
                                    bootstyle="success", width=20)
        self.btn_start.pack(pady=12, ipady=6)

        self.barra_stato = tb.Progressbar(contenitore, mode="determinate", bootstyle="success-striped")
        self.barra_stato.pack(fill=X, pady=(0, 10))

        # ---- Log ----
        box_log = tb.Labelframe(contenitore, text=" Log ", padding=8, bootstyle="dark")
        box_log.pack(fill=BOTH, expand=YES)
        self.testo_log = tk.Text(box_log, height=10, state="disabled", wrap="word",
                                  bg="#1e1e1e", fg="#d0d0d0", relief="flat", font=("Consolas", 9))
        self.testo_log.pack(fill=BOTH, expand=YES)

        self.protocol("WM_DELETE_WINDOW", self._chiudi_applicazione)

    # ---------------------- azioni GUI ----------------------
    def _scegli_cartella(self):
        cartella = filedialog.askdirectory(initialdir=self.cartella_output.get())
        if cartella:
            self.cartella_output.set(cartella)

    def _applica_impostazioni(self):
        try:
            self.cam.imposta_esposizione(float(self.var_esposizione.get()))
            self.cam.imposta_gain(float(self.var_gain.get()))
        except Exception as e:
            messagebox.showerror("Errore impostazioni", str(e))

    def _avvia_sequenza_scatti(self):
        try:
            num_scatti = int(self.var_num_scatti.get())
            intervallo = float(self.var_intervallo.get())
            if num_scatti < 1 or intervallo < 0:
                raise ValueError("Numero scatti deve essere >=1 e intervallo >=0.")
        except ValueError as e:
            messagebox.showerror("Parametri non validi", str(e))
            return

        self._applica_impostazioni()
        os.makedirs(self.cartella_output.get(), exist_ok=True)
        self.btn_start.config(state="disabled")
        self.barra_stato["maximum"] = num_scatti
        self.barra_stato["value"] = 0

        threading.Thread(
            target=self._esegui_scatti,
            args=(num_scatti, intervallo, self.cartella_output.get(), self.nome_file_corrente.get()),
            daemon=True,
        ).start()

    def _esegui_scatti(self, num_scatti, intervallo, cartella, nome_base):
        for i in range(1, num_scatti + 1):
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            nome_file = f"{nome_base}_{i:03d}_{timestamp}.png"
            percorso = os.path.join(cartella, nome_file)
            try:
                self.cam.scatta(percorso)
                self._log_da_thread(f"✔ Scatto {i}/{num_scatti} salvato: {percorso}")
            except Exception as e:
                self._log_da_thread(f"✘ Errore durante lo scatto {i}: {e}")
            self.coda_log.put(("progresso", i))
            if i < num_scatti and intervallo > 0:
                time.sleep(intervallo)

        self.coda_log.put(("fine_sequenza", None))

    # ---------------------- anteprima ----------------------
    def _aggiorna_anteprima(self):
        try:
            frame_bgr = self.cam.leggi_frame()
            if frame_bgr is not None:
                frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
                immagine = Image.fromarray(frame_rgb)
                larghezza_max = 520
                rapporto = larghezza_max / immagine.width
                immagine = immagine.resize((larghezza_max, int(immagine.height * rapporto)))
                self._img_anteprima_tk = ImageTk.PhotoImage(immagine)
                self.label_anteprima.config(image=self._img_anteprima_tk, text="")
        except Exception as e:
            self._log_da_thread(f"Errore aggiornamento anteprima: {e}")
        finally:
            self.after(1000, self._aggiorna_anteprima)

    # ---------------------- camera e socket ----------------------
    def _aggiorna_elenco_camere(self):
        trovati = elenca_dispositivi_video()
        self.dispositivi_disponibili = {}
        etichette = []
        etichetta_dfk_trovata = None

        for nome, paths in trovati.items():
            for path in paths:
                etichetta = f"{nome}  ({path})"
                self.dispositivi_disponibili[etichetta] = path
                etichette.append(etichetta)
                if etichetta_dfk_trovata is None and sembra_essere_la_dfk(nome):
                    etichetta_dfk_trovata = etichetta

        if not etichette:
            self._log_da_thread(
                "Nessuna camera trovata via v4l2-ctl. Installa v4l-utils "
                "('sudo apt install v4l-utils') per un rilevamento corretto. Uso /dev/video0 come fallback."
            )
            etichette = ["/dev/video0"]
            self.dispositivi_disponibili["/dev/video0"] = "/dev/video0"

        self.combo_camere["values"] = etichette

        if etichetta_dfk_trovata:
            self.var_camera_scelta.set(etichetta_dfk_trovata)
            self._log_da_thread(f"Camera riconosciuta automaticamente: {etichetta_dfk_trovata}")
        else:
            self.var_camera_scelta.set(etichette[0])
            self._log_da_thread(
                "Nessuna camera con nome riconoscibile come DFK trovata: "
                f"seleziono manualmente dal menu tra: {', '.join(etichette)}"
            )

    def _cambia_camera(self, event=None):
        etichetta = self.var_camera_scelta.get()
        path = self.dispositivi_disponibili.get(etichetta)
        if not path:
            return
        try:
            self.cam.apri(device=path)
            self.label_stato_camera.config(text=f"● Connessa: {etichetta}", bootstyle="success")
        except Exception as e:
            self.label_stato_camera.config(text="● Errore apertura camera", bootstyle="danger")
            messagebox.showerror("Errore camera", f"Impossibile aprire la camera: {e}")

    def _avvia_camera(self):
        etichetta = self.var_camera_scelta.get()
        path = self.dispositivi_disponibili.get(etichetta, "/dev/video0")
        try:
            self.cam.apri(device=path)
            self.label_stato_camera.config(text=f"● Connessa: {etichetta}", bootstyle="success")
        except Exception as e:
            self.label_stato_camera.config(text="● Errore apertura camera", bootstyle="danger")
            messagebox.showerror("Errore camera", f"Impossibile aprire la camera: {e}")

    def _avvia_server_socket(self):
        self.server = ServerNomeFile(
            host="0.0.0.0", port=5050,
            callback_nome=lambda nome: self.coda_log.put(("nome_file", nome)),
            log_fn=self._log_da_thread,
        )
        self.server.start()

    # ---------------------- log thread-safe ----------------------
    def _log_da_thread(self, messaggio):
        self.coda_log.put(("log", messaggio))

    def _svuota_coda_log(self):
        try:
            while True:
                tipo, valore = self.coda_log.get_nowait()
                if tipo == "log":
                    self.testo_log.config(state="normal")
                    self.testo_log.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {valore}\n")
                    self.testo_log.see("end")
                    self.testo_log.config(state="disabled")
                elif tipo == "nome_file":
                    self.nome_file_corrente.set(valore)
                elif tipo == "progresso":
                    self.barra_stato["value"] = valore
                elif tipo == "fine_sequenza":
                    self.btn_start.config(state="normal")
        except queue.Empty:
            pass
        self.after(150, self._svuota_coda_log)

    def _chiudi_applicazione(self):
        try:
            self.server.stop()
        except Exception:
            pass
        try:
            self.cam.chiudi()
        except Exception:
            pass
        self.destroy()


if __name__ == "__main__":
    app = App()
    app.mainloop()
