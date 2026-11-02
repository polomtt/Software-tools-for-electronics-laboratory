import os
import tkinter as tk
from tkinter import ttk
import pandas as pd
import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import math

from converto_nm_to_color import wavelength_to_hex


import os
import tkinter as tk
from tkinter import ttk
from datetime import datetime

import pandas as pd

folder = r"logger"  # <-- cambia qui


def scegli_da_menu(titolo, opzioni):
    """Menu a tendina + check box 'Plotta tutto'.
    Restituisce (opzione_scelta, plotta_tutto)."""
    risultato = {"valore": None, "plotta_tutto": False}

    root = tk.Tk()
    root.title(titolo)
    root.geometry("400x160")

    tk.Label(root, text=titolo).pack(pady=(15, 5))

    scelta = tk.StringVar()
    combo = ttk.Combobox(root, textvariable=scelta, values=opzioni,
                         state="readonly", width=50)
    combo.pack(pady=5)
    if opzioni:
        combo.current(0)

    plotta_tutto = tk.BooleanVar(value=False)
    ttk.Checkbutton(root, text="Plotta tutto", variable=plotta_tutto).pack(pady=5)

    def conferma():
        risultato["valore"] = scelta.get()
        risultato["plotta_tutto"] = plotta_tutto.get()
        root.destroy()

    ttk.Button(root, text="OK", command=conferma).pack(pady=5)

    root.mainloop()
    return risultato["valore"], risultato["plotta_tutto"]


def scegli_riga(titolo, df):
    """Mostra il DataFrame in una tabella e restituisce la posizione
    della riga selezionata."""
    risultato = {"indice": None}

    root = tk.Tk()
    root.title(titolo)
    root.geometry("1000x500")

    frame = ttk.Frame(root)
    frame.pack(fill="both", expand=True, padx=10, pady=10)

    colonne = list(df.columns)
    tree = ttk.Treeview(frame, columns=colonne, show="headings",
                        selectmode="browse")

    for c in colonne:
        tree.heading(c, text=str(c))
        tree.column(c, width=120, anchor="w")

    # Inserisco le righe: l'iid è la posizione nel DataFrame
    for i, riga in enumerate(df.itertuples(index=False)):
        tree.insert("", "end", iid=str(i), values=list(riga))

    # Scrollbar verticale e orizzontale
    vsb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    frame.rowconfigure(0, weight=1)
    frame.columnconfigure(0, weight=1)

    def conferma(event=None):
        sel = tree.selection()
        if sel:
            risultato["indice"] = int(sel[0])
            root.destroy()

    tree.bind("<Double-1>", conferma)  # doppio click = conferma
    ttk.Button(root, text="OK", command=conferma).pack(pady=(0, 10))

    root.mainloop()
    return risultato["indice"]


def costruisci_nomi(riga):
    """Dato una riga del logbook, costruisce i nomi dei due file."""
    dt = datetime.strptime(riga["Datetime"], "%Y/%m/%d %H:%M:%S")
    filename_part = dt.strftime("%Y%m%d_%H%M%S")
    ibil = "Data/IBIL_{}_{}_{}".format(filename_part, riga["Sample"], riga["Beam_I"])
    power = "Data/Powermeter_{}_{}_{}".format(filename_part, riga["Sample"], riga["Beam_I"])
    return ibil, power


def trova_il_file():
    """Ritorna:
    - plotta_tutto = False -> (ibil_file, powermeter_file) della riga scelta
    - plotta_tutto = True  -> lista di tuple (ibil_file, powermeter_file)
                              per tutte le righe del logbook
    """
    # 1) Menu con i file nella cartella + check box "Plotta tutto"
    files = sorted(f for f in os.listdir(folder)
                   if os.path.isfile(os.path.join(folder, f)))

    if not files:
        raise SystemExit(f"Nessun file trovato in: {folder}")

    file_scelto, plotta_tutto = scegli_da_menu("Seleziona il file", files)
    if not file_scelto:
        raise SystemExit("Nessun file selezionato.")

    # 2) Leggo il CSV
    df = pd.read_csv(os.path.join(folder, file_scelto), sep="|", skipinitialspace=True)

    df.columns = df.columns.str.strip()
    df = df.map(lambda x: x.strip() if isinstance(x, str) else x)

    # 3a) Plotta tutto: ritorno i nomi di tutte le righe
    if plotta_tutto:
        tutti = [costruisci_nomi(riga) for _, riga in df.iterrows()]
        print(f"Trovati {len(tutti)} file nel logbook '{file_scelto}'")
        return tutti

    # 3b) Altrimenti: finestra "Seleziona la riga"
    posizione = scegli_riga(f"Seleziona la riga ({file_scelto})", df)
    if posizione is None:
        raise SystemExit("Nessuna riga selezionata.")

    riga_scelta = df.iloc[posizione]
    return [costruisci_nomi(riga_scelta)]


fontsize_to_use = 15

# Ritorna SEMPRE una lista di tuple (ibil_file, powermeter_file):
# - con "Plotta tutto" spuntato: una tupla per ogni riga del logbook
# - altrimenti: una sola tupla, quella della riga selezionata
file_list = trova_il_file()

num_fig = 1

for ibil_file, powermeter_file in file_list:
    ibil_fig_name = ibil_file.replace("Data","Figure") + ".png"
    power_fig_name = powermeter_file.replace("Data","Figure") + ".png"

    plt.figure("Powermeter_{}".format(num_fig))
    df_power_meter = pd.read_csv("{}.csv".format(powermeter_file))
    df_baseline = df_power_meter[0:10]
    baseline = np.mean(df_baseline["corrente[A]"])
    threshold = (np.max(df_power_meter["corrente[A]"])-baseline)*0.25

    curr_to_average = []

    for curr in (df_power_meter["corrente[A]"]-baseline):
        curr_to_average.append(curr)
        
    curr_avg = np.mean(curr_to_average)
    curr_std = np.std(curr_to_average)/math.sqrt(len(curr_to_average))

    plt.plot(df_power_meter["tempo[]"],df_power_meter["corrente[A]"]-baseline,label="Avg: {:.2e} +- {:.2e}".format(curr_avg,curr_std))
    plt.axhline(y=threshold, color='red', linestyle='--', label='Threshold')
    plt.title(powermeter_file,fontsize=fontsize_to_use)
    plt.xlabel("Time [s]",fontsize=fontsize_to_use)
    plt.ylabel("Current [A]",fontsize=fontsize_to_use)
    plt.legend(fontsize=fontsize_to_use)
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(power_fig_name)

    fig, (ax1, ax2) = plt.subplots(2, 1,figsize=(12, 8),num="IBIL_{}".format(num_fig))

    fig.suptitle(ibil_file)

    max_vector = []
    time_vector = []

    for num in range(0,1000):
        try:
            file = "{}/histo_num{}.csv".format(ibil_file, num)

            # Leggo il tempo di integrazione
            prima_riga = pd.read_csv(file, header=None, nrows=1).iloc[0, 0]
            help = prima_riga.replace("#Time_acq","")
            help = help.replace("s","")
            df_ibil = pd.read_csv(file,skiprows=2)
            
            idx_max = df_ibil["Intensity[counts]"].idxmax()
            max_intensity = df_ibil.loc[idx_max, "Intensity[counts]"]
            max_wavelength = df_ibil.loc[idx_max, "#Wavelength[nm]"]
            
            ax1.plot(df_ibil["#Wavelength[nm]"], df_ibil["Intensity[counts]"],color=wavelength_to_hex(max_wavelength))
            ax2.plot(float(help),max_intensity,color=wavelength_to_hex(max_wavelength),marker="o",ms=4)
            max_vector.append(max_intensity)
            time_vector.append(float(help))
            
            ax1.set_xlabel("Wavelenght [nm]")
            ax1.set_ylabel("Intensity [-]")
            ax1.grid(True)
            
        except:
            pass
        

    ax2.plot(time_vector,max_vector,lw=0.75,color="black",ls="--")
    ax2.set_xlabel("Time [s]")
    ax2.set_ylabel("Max [-]")
    ax2.grid(True)
    plt.tight_layout()
    plt.savefig(ibil_fig_name)
    num_fig=num_fig+1


plt.show()
