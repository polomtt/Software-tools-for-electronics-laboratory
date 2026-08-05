import pyvisa
import time
import csv
import threading
import queue
from datetime import datetime

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib
matplotlib.use('TkAgg')
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

GPIB_RESOURCE = 'GPIB0::5::INSTR'  # verifica indirizzo GPIB sul pannello strumento
QUERY_COMMAND = 'R_A?'
POLL_INTERVAL_S = 1.0

# Palette colori
COLOR_BG = '#1e1e2e'
COLOR_PANEL = '#292a3d'
COLOR_TEXT = '#e0e0f0'
COLOR_ACCENT = '#7aa2f7'
COLOR_START = '#4caf7d'
COLOR_START_ACTIVE = '#3d9c6a'
COLOR_STOP = '#e05c6b'
COLOR_STOP_ACTIVE = '#c94a58'
COLOR_ENTRY_BG = '#33344a'


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


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('Newport 2832C - Acquisizione Corrente')
        self.geometry('900x680')
        self.configure(bg=COLOR_BG)

        self._setup_style()

        self.data_queue = queue.Queue()
        self.error_queue = queue.Queue()
        self.stop_event = threading.Event()
        self.acq_thread = None
        self.csv_file = None
        self.csv_writer = None

        self.times = []
        self.values = []

        self._build_ui()
        self._poll_queues()

    def _setup_style(self):
        style = ttk.Style(self)
        # 'clam' e' il tema piu' malleabile: gli unici temi ttk che rispettano
        # colori custom sui bottoni sono clam/alt/default. I temi nativi
        # (es. 'aqua' su mac, 'vista' su windows) ignorano bg/fg sui Button.
        style.theme_use('clam')

        style.configure('TFrame', background=COLOR_BG)
        style.configure('TLabel', background=COLOR_BG, foreground=COLOR_TEXT, font=('Segoe UI', 10))
        style.configure('Status.TLabel', background=COLOR_BG, foreground=COLOR_ACCENT, font=('Segoe UI', 9, 'italic'))

        style.configure('TEntry', fieldbackground=COLOR_ENTRY_BG, foreground=COLOR_TEXT,
                         insertcolor=COLOR_TEXT, borderwidth=0, padding=6)

        style.configure('Browse.TButton', background=COLOR_PANEL, foreground=COLOR_TEXT,
                         font=('Segoe UI', 10), borderwidth=0, padding=8)
        style.map('Browse.TButton', background=[('active', COLOR_ACCENT)])

        style.configure('Start.TButton', background=COLOR_START, foreground='white',
                         font=('Segoe UI', 11, 'bold'), borderwidth=0, padding=10)
        style.map('Start.TButton',
                  background=[('disabled', '#3a3a3a'), ('active', COLOR_START_ACTIVE)],
                  foreground=[('disabled', '#888888')])

        style.configure('Stop.TButton', background=COLOR_STOP, foreground='white',
                         font=('Segoe UI', 11, 'bold'), borderwidth=0, padding=10)
        style.map('Stop.TButton',
                  background=[('disabled', '#3a3a3a'), ('active', COLOR_STOP_ACTIVE)],
                  foreground=[('disabled', '#888888')])

    def _build_ui(self):
        top_frame = ttk.Frame(self, padding=15)
        top_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(top_frame, text='Sample:').pack(side=tk.LEFT)
        self.filename_var = tk.StringVar(value='acquisizione.csv')
        self.filename_entry = ttk.Entry(top_frame, textvariable=self.filename_var, width=35)
        self.filename_entry.pack(side=tk.LEFT, padx=8)

        browse_btn = ttk.Button(top_frame, text='Sfoglia...', style='Browse.TButton', command=self._browse_file)
        browse_btn.pack(side=tk.LEFT, padx=5)

        self.start_btn = ttk.Button(top_frame, text='▶  Start', style='Start.TButton', command=self._start_acquisition)
        self.start_btn.pack(side=tk.LEFT, padx=(25, 5))

        self.stop_btn = ttk.Button(top_frame, text='■  Stop', style='Stop.TButton',
                                    command=self._stop_acquisition, state=tk.DISABLED)
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        second_frame = ttk.Frame(self, padding=(15, 0, 15, 15))
        second_frame.pack(side=tk.TOP, fill=tk.X)

        ttk.Label(second_frame, text='beam_current:').pack(side=tk.LEFT)
        self.beam_current_var = tk.StringVar(value='')
        self.beam_current_entry = ttk.Entry(second_frame, textvariable=self.beam_current_var, width=35)
        self.beam_current_entry.pack(side=tk.LEFT, padx=8)

        self.status_var = tk.StringVar(value='Pronto.')
        status_label = ttk.Label(self, textvariable=self.status_var, style='Status.TLabel', padding=(15, 0, 15, 10))
        status_label.pack(side=tk.TOP, fill=tk.X)

        self.fig = Figure(figsize=(8, 5), dpi=100)
        self.fig.patch.set_facecolor(COLOR_BG)
        self.ax = self.fig.add_subplot(111)
        self.ax.set_facecolor(COLOR_PANEL)
        self.ax.set_xlabel('Tempo (s)', color=COLOR_TEXT)
        self.ax.set_ylabel('Corrente', color=COLOR_TEXT)
        self.ax.set_title('Corrente vs Tempo', color=COLOR_TEXT, fontsize=13, fontweight='bold')
        self.ax.tick_params(colors=COLOR_TEXT)
        for spine in self.ax.spines.values():
            spine.set_color('#555566')
        self.ax.grid(True, color='#3f4059', linewidth=0.6)
        self.line, = self.ax.plot([], [], '-o', color=COLOR_ACCENT, markersize=3, linewidth=1.5)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self)
        self.canvas.get_tk_widget().configure(bg=COLOR_BG, highlightthickness=0)
        self.canvas.get_tk_widget().pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

    def _browse_file(self):
        path = filedialog.asksaveasfilename(
            defaultextension='.csv',
            filetypes=[('CSV files', '*.csv')],
            initialfile=self.filename_var.get()
        )
        if path:
            self.filename_var.set(path)

    def _start_acquisition(self):
        filename = self.filename_var.get().strip()
        if not filename:
            messagebox.showerror('Errore', 'Specifica un nome di file CSV.')
            return

        try:
            self.csv_file = open(filename, 'w', newline='')
        except Exception as e:
            messagebox.showerror('Errore', f'Impossibile aprire il file:\n{e}')
            return

        self.csv_writer = csv.writer(self.csv_file)
        self.csv_writer.writerow(['timestamp', 'tempo_s', 'corrente'])

        self.times = []
        self.values = []
        self.line.set_data([], [])
        self.ax.relim()
        self.ax.autoscale_view()
        self.canvas.draw_idle()

        self.stop_event.clear()
        self.acq_thread = AcquisitionThread(self.data_queue, self.stop_event, self.error_queue)
        self.acq_thread.start()

        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.filename_entry.config(state=tk.DISABLED)
        self.status_var.set(f'Acquisizione in corso -> {filename}')

    def _stop_acquisition(self):
        self.stop_event.set()
        if self.acq_thread is not None:
            self.acq_thread.join(timeout=3)
        self.acq_thread = None

        if self.csv_file is not None:
            self.csv_file.close()
            self.csv_file = None
            self.csv_writer = None

        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.filename_entry.config(state=tk.NORMAL)
        self.status_var.set('Acquisizione fermata.')

    def _poll_queues(self):
        updated = False
        while not self.data_queue.empty():
            timestamp, elapsed, value = self.data_queue.get_nowait()
            self.times.append(elapsed)
            self.values.append(value)
            if self.csv_writer is not None:
                self.csv_writer.writerow([timestamp, f'{elapsed:.3f}', value])
                self.csv_file.flush()
            updated = True

        while not self.error_queue.empty():
            err = self.error_queue.get_nowait()
            self.status_var.set(f'Errore: {err}')

        if updated:
            self.line.set_data(self.times, self.values)
            self.ax.relim()
            self.ax.autoscale_view()
            self.canvas.draw_idle()

        self.after(200, self._poll_queues)

    def on_close(self):
        self.stop_event.set()
        if self.acq_thread is not None:
            self.acq_thread.join(timeout=3)
        if self.csv_file is not None:
            self.csv_file.close()
        self.destroy()


if __name__ == '__main__':
    app = App()
    app.protocol('WM_DELETE_WINDOW', app.on_close)
    app.mainloop()