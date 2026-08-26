# Acquisizione SHINE — PowerMeter + IBIL

Sistema di acquisizione dati sincronizzata per due strumenti:

- **Newport 2832C (PowerMeter)** — misura di corrente/potenza via GPIB, gestito da una GUI Tkinter.
- **Spettrometro Ocean Optics (IBIL)** — acquisizione spettri, avviato/fermato in automatico insieme al PowerMeter tramite un canale di comunicazione ZMQ.

I due processi girano in parallelo (in due finestre `tmux` separate) e si scambiano comandi via ZMQ: quando l'utente avvia l'acquisizione dalla GUI, viene inviato un segnale che fa partire anche l'acquisizione dello spettrometro, se abilitata.

---

## Indice
- [Parte 1 — Guida per l'utente finale](#parte-2--guida-per-lutente-finale)
  - [Avvio rapido](#avvio-rapido)
  - [Uso della GUI](#uso-della-gui)
  - [Configurazione IBIL](#configurazione-ibil)
  - [Dove vengono salvati i dati](#dove-vengono-salvati-i-dati)
  - [Arresto dell'acquisizione](#arresto-dellacquisizione)
  - [Problemi comuni](#problemi-comuni)
- [Parte 2 — Guida per sviluppatori](#parte-1--guida-per-sviluppatori)
  - [Architettura](#architettura)
  - [Struttura dei file](#struttura-dei-file)
  - [Protocollo ZMQ](#protocollo-zmq)
  - [Descrizione dei moduli](#descrizione-dei-moduli)
  - [Dipendenze](#dipendenze)
  - [Come estendere il progetto](#come-estendere-il-progetto)
  - [Problemi noti / TODO](#problemi-noti--todo)

---

## Parte 1 — Guida per l'utente finale

### Avvio rapido

1. Apri un terminale nella cartella del progetto.
2. Lancia:
   ```bash
   ./start_acquisizione.sh
   ```
3. Questo comando apre una sessione `tmux` in background con due processi:
   - la **GUI del PowerMeter** (si apre automaticamente una finestra grafica);
   - il processo di **acquisizione IBIL** (in attesa, non ha una sua finestra grafica finché non attivi l'acquisizione).

Se vuoi vedere cosa succede nel terminale dei due processi (log, eventuali errori):
```bash
tmux attach -t Acquisizione_SHINE
```
Per uscire dalla vista `tmux` senza chiudere i processi: `Ctrl+B` poi `D`.

### Uso della GUI

Alla partenza si apre la finestra **"Newport 2832C - Acquisizione Corrente"**:

1. **Sample**: nome del campione in misura (usato per nominare i file di output).
2. **beam_current**: valore di corrente del fascio, anch'esso incluso nel nome dei file.
3. **Attiva acquisizione IBIL** (checkbox): se spuntata, all'avvio dell'acquisizione parte in automatico anche l'acquisizione dello spettro IBIL.
4. **CONFIG IBIL**: apre una finestra per impostare:
   - `Tempo_integrazione_[ms]` — tempo di integrazione dello spettrometro;
   - `Media_spettri` — numero di spettri da mediare per ogni misura.
   Premi **Salva** per confermare i valori (vengono usati solo se l'acquisizione IBIL viene poi attivata).
5. **▶ Start**: avvia l'acquisizione. Il grafico "Corrente vs Tempo" si aggiorna in tempo reale; se l'IBIL è attivo, si apre anche la finestra con lo spettro live e l'andamento del picco.
6. **■ Stop**: ferma l'acquisizione (sia PowerMeter che, se attiva, IBIL) e chiude i file di output.

Lo stato corrente (in corso, fermata, eventuali errori) è mostrato nella riga sotto ai comandi.

### Configurazione IBIL

I parametri impostati in "CONFIG IBIL" vengono inviati allo spettrometro **solo quando premi Start** con la checkbox "Attiva acquisizione IBIL" spuntata. Se modifichi i parametri mentre un'acquisizione è già in corso, i nuovi valori verranno applicati automaticamente al ciclo successivo (senza bisogno di fermare e riavviare).

### Dove vengono salvati i dati

Tutti i dati vengono salvati in una cartella `Data/` creata automaticamente accanto agli script:

```
Data/
├── Powermeter_<timestamp>_<sample>_<beam_current>.csv
└── IBIL_<timestamp>_<sample>_<beam_current>/
    ├── histo_num0.csv
    ├── histo_num1.csv
    └── ...
```

- **`Powermeter_....csv`**: colonne `timestamp`, `tempo_s`, `corrente` — un record al secondo.
- **`IBIL_..../histo_numN.csv`**: uno spettro completo per file, colonne `Wavelength[nm]`, `Intensity[counts]`, con intestazione che riporta tempo di acquisizione, tempo di integrazione e numero di spettri mediati.

### Arresto dell'acquisizione

Per fermare la misura in corso, usa il bottone **■ Stop** nella GUI: chiude correttamente i file CSV e ferma anche l'IBIL se era attivo.

Per terminare **tutti** i processi (GUI + IBIL) e chiudere la sessione in background:
```bash
./stop_acquisizione.sh
```

### Problemi comuni

| Sintomo | Possibile causa |
|---|---|
| La GUI si apre ma "Errore apertura strumento" nello stato | Il Newport 2832C non è collegato/acceso, oppure l'indirizzo GPIB (`GPIB0::5::INSTR`) non corrisponde a quello reale — va verificato nel pannello dello strumento. |
| Lo spettro IBIL non si apre nonostante la checkbox attiva | Il processo `acquisition_IBIL.py` potrebbe non essere partito correttamente (spettrometro Ocean Optics non collegato) — controlla con `tmux attach -t Acquisizione_SHINE` nella finestra `IBIL`. |
| "Risposta non numerica" nello stato | Lo strumento ha risposto con qualcosa di inatteso al comando `R_A?`: verifica lo stato/la configurazione del Newport 2832C. |
| Il comando di Start/Stop dell'IBIL sembra "perso" | Il processo IBIL non era ancora pronto a ricevere messaggi quando è partita la GUI; riavvia con `./stop_acquisizione.sh` seguito da `./start_acquisizione.sh`. |


## Parte 2 — Guida per sviluppatori

### Architettura

Il sistema è composto da **due processi Python indipendenti**, coordinati da ZMQ (pattern PUB/SUB) e lanciati insieme tramite uno script bash che apre una sessione `tmux` con due finestre:

```
                     ┌───────────────────────────┐
                     │        start_acquisizione.sh
                     └─────────────┬─────────────┘
                                    │ tmux new-session / new-window
             ┌──────────────────────┴───────────────────────┐
             ▼                                               ▼
   Finestra "PowerMeter"                            Finestra "IBIL"
   ┌─────────────────────┐                    ┌───────────────────────────┐
   │      main.py         │                    │    acquisition_IBIL.py    │
   │  crea socket ZMQ PUB │   tcp://*:5555     │   socket ZMQ SUB          │
   │  avvia gui.py (App)  │ ─────────────────▶ │   (subscribe a tutto)     │
   └─────────┬────────────┘                    └───────────────┬───────────┘
             │                                                  │
   ┌─────────▼─────────────┐                     ┌──────────────▼──────────┐
   │ acquisition_PowerMeter │                     │  seabreeze.Spectrometer │
   │  (thread GPIB/pyvisa)  │                     │  + converto_nm_to_color │
   └────────────────────────┘                     └──────────────────────────┘
```

- Il processo **PowerMeter** (`main.py` + `gui.py`) è il "master": la GUI comanda l'avvio/stop dell'acquisizione di corrente e, se l'utente lo richiede, invia via ZMQ il comando per far partire anche l'acquisizione IBIL.
- Il processo **IBIL** (`acquisition_IBIL.py`) resta in ascolto sul socket ZMQ e reagisce ai messaggi ricevuti, avviando o fermando il ciclo di acquisizione dello spettrometro.

### Struttura dei file

| File | Ruolo |
|---|---|
| `main.py` | Entry point del processo PowerMeter/GUI. Crea il socket ZMQ (PUB) e avvia `App`. |
| `gui.py` | Interfaccia grafica Tkinter: gestisce input utente, grafico corrente/tempo, salvataggio CSV, invio comandi ZMQ. |
| `acquisition_PowerMeter.py` | Thread di polling GPIB sul Newport 2832C, disaccoppiato dalla GUI tramite `queue.Queue`. |
| `acquisition_IBIL.py` | Processo standalone: riceve comandi ZMQ, pilota lo spettrometro Ocean Optics, mostra grafici live e salva gli spettri su CSV. |
| `converto_nm_to_color.py` | Utility: converte una lunghezza d'onda (nm) nel colore RGB/hex visibile corrispondente, usata per colorare il plot dello spettro. |
| `zmq_comm.py` | Funzioni condivise per creare/chiudere i socket ZMQ e per serializzare/deserializzare i messaggi di comando (JSON). |
| `start_acquisizione.sh` | Avvia una sessione `tmux` con le due finestre (`PowerMeter` e `IBIL`) in background. |
| `stop_acquisizione.sh` | Termina la sessione `tmux` (kill di entrambi i processi). |

### Protocollo ZMQ

- **Pattern**: `PUB`/`SUB`.
- **Bind**: il processo PowerMeter fa da server e si mette in bind su `tcp://*:5555` (`zmq_comm.create_socket`).
- **Connect**: il processo IBIL si connette come subscriber a `tcp://localhost:5555` con subscribe su tutti i topic (`""`) e timeout di ricezione di 1000 ms (`zmq.RCVTIMEO`).

I messaggi sono stringhe JSON con questo schema:

```json
{
  "value": true,
  "filename": "20250101_120000_sample_0",
  "integration_time": 100,
  "avg_spectrum": 1
}
```

| Campo | Tipo | Significato |
|---|---|---|
| `value` | bool | `true` = avvia acquisizione IBIL, `false` = fermala |
| `filename` | str | Prefisso cartella/file, generato dalla GUI (timestamp + sample + corrente) |
| `integration_time` | float | Tempo di integrazione dello spettrometro in ms |
| `avg_spectrum` | float | Numero di spettri da mediare (`scans_to_average`) |

Funzioni helper in `zmq_comm.py`:
- `send_true(socket, filename, integration_time, avg_spectrum)` — invia il comando di start.
- `send_false(socket)` — invia il comando di stop (valori di default per gli altri campi).
- `read_socket(socket)` — riceve e deserializza, ritorna la tupla `(value, filename, integration_time, avg_spectrum)`.

> ⚠️ **Nota**: essendo `PUB/SUB`, se `acquisition_IBIL.py` non è ancora connesso quando parte `main.py`, il primo messaggio può andare perso (comportamento tipico di ZMQ PUB/SUB, non c'è buffering per i subscriber non ancora connessi). Per questo `main.py` aspetta 1 secondo (`time.sleep(1)`) dopo la creazione del socket prima di avviare la GUI.

### Descrizione dei moduli

#### `main.py`
Entry point minimale: crea `context`/`socket` ZMQ, attende 1s, istanzia `App(socket)`, imposta l'handler di chiusura finestra e avvia il main loop Tkinter. Alla chiusura chiude socket e context.

#### `gui.py`
Classe `App(tk.Tk)`:
- Costruisce l'interfaccia (campi `Sample` e `beam_current`, bottoni Start/Stop, grafico corrente/tempo, checkbox "Attiva acquisizione IBIL", bottone "CONFIG IBIL").
- `_start_acquisition()`: crea la cartella `Data/` (e `Data/IBIL_<filename_part>/` se l'IBIL è abilitato), apre il CSV di output, invia via ZMQ il comando di start (se IBIL abilitato) e avvia `AcquisitionThread`.
- `_stop_acquisition()`: invia il comando di stop via ZMQ, ferma il thread, chiude il CSV.
- `_poll_queues()`: eseguita ogni 200ms (`self.after`), svuota le code dati/errori del thread di acquisizione, aggiorna grafico e CSV.
- `open_config_ibil()`: finestra modale per impostare `Tempo_integrazione_[ms]` e `Media_spettri` da inviare all'IBIL.

#### `acquisition_PowerMeter.py`
Classe `AcquisitionThread(threading.Thread)`: apre la risorsa GPIB (`pyvisa`, resource `GPIB0::5::INSTR`), interroga lo strumento ogni `POLL_INTERVAL_S` (1s) con il comando `R_A?`, mette `(timestamp, elapsed, value)` nella `data_queue`. Gli errori (di apertura, di parsing della risposta, di query) vanno nella `error_queue`. Il thread termina quando viene settato `stop_event`.

#### `acquisition_IBIL.py`
Script standalone (non un modulo importabile in modo pulito — va lanciato come processo a sé):
- Si connette allo spettrometro alla prima esecuzione (`Spectrometer.from_first_available()`).
- Resta in loop in ascolto sul socket ZMQ; quando riceve `value=True` apre una figura Matplotlib con due subplot (spettro live + andamento del picco nel tempo), acquisisce continuamente finché non riceve `value=False`.
- Ad ogni ciclo salva lo spettro corrente in `Data/IBIL_<filename_part>/histo_num<N>.csv`.
- Applica i parametri `integration_time`/`avg_spectrum` ricevuti dal messaggio ad ogni iterazione (con fallback ai valori di default in caso di errore).

#### `converto_nm_to_color.py`
`wavelength_to_hex(wavelength)`: converte una lunghezza d'onda in nm (range valido 380–750 nm) in un colore esadecimale approssimato, usato solo per colorare la curva dello spettro nel plot in base al picco. Fuori range ritorna nero (`#000000`).

#### `zmq_comm.py`
Vedi [Protocollo ZMQ](#protocollo-zmq).

### Dipendenze

```
pyzmq
numpy
matplotlib
seabreeze          # libreria Ocean Optics per lo spettrometro
pyvisa             # comunicazione GPIB
pyvisa-py          # backend @py usato da pyvisa.ResourceManager('@py')
```

Richiede inoltre:
- Driver/permessi per accedere allo spettrometro Ocean Optics (seabreeze).
- Un backend VISA funzionante e accesso al bus GPIB per il Newport 2832C.
- `tmux` installato sul sistema per usare gli script di avvio/stop.

### Come estendere il progetto

- **Aggiungere un nuovo strumento sincronizzato**: seguire il modello IBIL — creare uno script standalone che si connette come `SUB` sullo stesso indirizzo `tcp://localhost:5555` e reagisce ai messaggi `read_socket`. Se serve un canale a parte, usare una porta ZMQ diversa per non interferire col protocollo esistente.
- **Aggiungere nuovi parametri di configurazione IBIL**: estendere il dizionario `ibil_params` in `gui.py`, il payload JSON in `send_true`/`read_socket` (`zmq_comm.py`) e la relativa lettura in `acquisition_IBIL.py`.
- **Cambiare indirizzo/porta ZMQ**: modificare `ZMQ_BIND_ADDRESS` in `zmq_comm.py` (lato server) e la stringa `tcp://localhost:5555` in `acquisition_IBIL.py` (lato client) — al momento sono hardcoded in due punti separati, andrebbero centralizzati in un unico file di configurazione.

### Problemi noti / TODO

- L'indirizzo ZMQ è duplicato (hardcoded sia in `zmq_comm.py` che in `acquisition_IBIL.py`): conviene centralizzarlo.
- Pattern PUB/SUB senza conferma di ricezione: un comando può perdersi se il subscriber non è ancora connesso o si disconnette temporaneamente.
- `acquisition_IBIL.py` non è strutturato come modulo/funzione (tutto a livello di script), quindi non è testabile facilmente né importabile da altri script.
- Gestione errori con `except:` generico in più punti (es. in `acquisition_IBIL.py`), che nasconde la causa reale in caso di problemi.

---
