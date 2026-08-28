# CAEN HV Control ⚡

Web app per connettersi a uno o più moduli CAEN, impostare/accendere/
spegnere le HV di ogni canale e monitorare tensione e corrente in tempo
reale. Nessuna modalità simulata: parla sempre con l'hardware reale.

Supporta due famiglie di moduli, con lo stesso frontend:

- **`driver: "dpp"`** (default) — schede digitizer/DPP con HV integrata,
  tipo **DT5780**, via **CAENDPPLib**, USB/link ottico diretto.
- **`driver: "hvwrapper"`** — moduli HV standalone, tipo **V6533** (o
  altre board V65xx/SY-crate), via **CAENHVWrapper** + **CAENVMELib**,
  tipicamente attraverso un bridge VME-USB come il **V1718**.

```
caen-webapp/
Moduli_HV_caen/
├── install.sh              Installa dipendenze di sistema + Python + verifica librerie CAEN
├── start.sh                Avvia il backend (funziona da qualunque cartella)
├── backend/
│   ├── config.json          <-- qui definisci moduli, canali, VSet, rampe
│   ├── config_loader.py     Carica/valida config.json
│   ├── errors.py            Eccezione condivisa tra i driver
│   ├── hvwrapper_driver.py  Driver per moduli HV standalone (parla con CAENHVWrapper) — es. V6533
│   ├── main.py              FastAPI: API REST + WebSocket di monitor
│   ├── manager.py           Tiene un driver per ogni modulo di config.json (sceglie dpp/hvwrapper)
│   ├── module_driver.py     Driver per schede DPP (parla con CAENDPPLib) — es. DT5780
│   └── requirements.txt
├── caen-installers/         (opzionale) metti qui i .deb/.run CAEN scaricati
└── frontend/
    └── index.html            Dashboard: un pannello per modulo, canali come sotto-blocchi
```

## 1. Installazione

```bash
./install.sh
```

Fa questo:
- installa le dipendenze di sistema (Python, venv, libusb) via apt
- crea un virtual environment in `backend/venv` e installa `requirements.txt`
- controlla **separatamente** se il binding Python trova le librerie
  native di entrambe le famiglie:
  - `caen_libs.caendpplib` → serve per i moduli `driver: "dpp"`
  - `caen_libs.caenhvwrapper` → serve per i moduli `driver: "hvwrapper"`

  Ti serve solo quella dei moduli che hai davvero in `config.json` — se
  manca, lo script stampa le istruzioni per scaricarla da caen.it (serve
  account gratuito), oppure, se metti i `.deb`/`.run` già scaricati in
  `./caen-installers/`, li installa da solo al prossimo lancio.

Librerie native richieste, a seconda del driver:

| Driver | Librerie native |
|---|---|
| `dpp` (es. DT5780) | driver USB/ottico CAEN, **CAENComm**, **CAENDigitizer**, **CAENDPPLib** |
| `hvwrapper` (es. V6533) | **CAENVMELib**, **CAENHVWrapper** |

## 2. Configurazione — `backend/config.json`

Un blocco per ogni modulo fisico collegato:

```json
{
  "modules": [
    {
      "name": "DT5780_A",
      "model": "DT5780",
      "connection": {
        "link_type": "USB",
        "link_num": 0,
        "conet_node": 0,
        "vme_base": "0"
      },
      "n_channels": 2,
      "channels": [
        { "channel": 0, "vset": 800.0,  "ramp_up": 50.0, "ramp_down": 50.0, "polarity": "+", "iset": 5.0 },
        { "channel": 1, "vset": 1000.0, "ramp_up": 50.0, "ramp_down": 50.0, "polarity": "+", "iset": 5.0 }
      ]
    },
    {
      "name": "V6533_A",
      "model": "V65XX",
      "driver": "hvwrapper",
      "connection": {
        "link_type": "USB",
        "link_num": 0,
        "conet_node": 0,
        "vme_base": "12345678"
      },
      "n_channels": 6,
      "channels": [
        { "channel": 0, "vset": 500.0, "ramp_up": 25.0, "ramp_down": 25.0 }
      ]
    }
  ]
}
```

Campi comuni a ogni modulo:
- **`name`** — identificativo libero e univoco, usato da API e UI.
- **`model`** — nome scheda (es. `"DT5780"`, `"V65XX"`) usato per
  verificare che l'hardware collegato sia quello atteso.
- **`driver`** — `"dpp"` (default, si può omettere) o `"hvwrapper"`.
- **`n_channels`** — deve combaciare col numero di elementi in `channels`.
- **`connection`** — `link_type`/`link_num`/`conet_node`/`vme_base`.
  Per `hvwrapper` via bridge USB (es. V1718), `vme_base` è l'indirizzo
  VME impostato fisicamente sui dip-switch/rotary switch della board
  (es. `"12345678"`), e va cambiato se sposti il modulo su un'altra
  scheda con indirizzo diverso.

Campi per ogni canale (solo `channel`/`vset`/`ramp_up`/`ramp_down` sono
obbligatori, gli altri sono opzionali):
- **`vset`** (V) — applicato automaticamente alla connessione.
- **`ramp_up`** / **`ramp_down`** (V/s) — applicati automaticamente alla
  connessione.
- **`iset`** (µA, opzionale) — limite di corrente. Se presente, viene
  applicato automaticamente alla connessione/"Applica config" come
  vset/rampe; se assente, il driver **non tocca** il valore già
  impostato sulla board.
- **`polarity`** (opzionale, `"+"` o `"-"`) — su **DT5780** è l'unico modo
  di mostrarla in UI, perché CAENDPPLib non la espone come parametro
  leggibile: scrivila guardando l'etichetta vicino al connettore HV o il
  datasheet del tuo modulo. Su **hvwrapper** (V6533), se la scrivi qui ha
  la precedenza sulla lettura automatica dall'hardware.

Il power (ON/OFF) non viene mai toccato automaticamente: resta sempre
un'azione esplicita dalla UI, anche subito dopo la connessione.

Puoi ricaricare `config.json` senza riavviare il backend con il pulsante
"Ricarica config.json" nella UI, o via `POST /api/config/reload` (un
modulo già connesso mantiene la vecchia config finché non lo disconnetti,
per non toccare hardware attivo di sorpresa).

## 3. Avvio

```bash
./start.sh                # solo localhost, porta 8000
./start.sh --lan          # accessibile da altri dispositivi in rete locale
./start.sh --port 9000    # porta diversa
./start.sh --no-reload    # senza auto-reload
```

Apri `http://localhost:8000` (o l'IP della macchina se hai usato `--lan`).

## 4. Uso della dashboard

Ogni modulo di `config.json` ha il proprio pannello con **Connetti** /
**Disconnetti** / **Applica config**. Dentro il pannello trovi un
sotto-blocco per ogni canale (`CH 0`, `CH 1`, ...), organizzato in due
tab:

- **Monitor**:
  - Box **Vmon** / **Imon**, aggiornati via WebSocket ogni 0.5s, con
    barra di livello sotto.
  - Box **Vset** (stesso stile grande di Vmon, editabile) + pulsante
    azzurro **Imposta**.
  - Box **Iset** (limite di corrente, stesso stile) + pulsante azzurro
    **Imposta**. Se la board (hvwrapper) non espone questo parametro,
    scrivere qui dà un errore che elenca i parametri reali disponibili.
  - Pulsanti **ON** (verde) / **OFF** (rosso) — quello corrispondente
    allo stato attuale del canale resta evidenziato pieno.
- **Rampa** — box **Ramp Up** / **Ramp Down** (V/s, stesso stile grande)
  + pulsante azzurro **Applica rampa**.

Tutti i campi editabili (Vset, Iset, Ramp Up, Ramp Down) si precompilano
da soli col valore letto dall'hardware al primo aggiornamento dopo la
connessione, e si ripopolano ad ogni riconnessione — dopodiché restano
liberi, così non ti sovrascrive quello che stai digitando.

Altri dettagli visivi:
- **LED** accanto al nome canale: fisso rosso = canale acceso e stabile,
  lampeggiante ambra = rampa in corso, lampeggiante rosso veloce =
  sovracorrente, spento = OFF.
- **Status pill** colorata sotto al LED (grigio=OFF, verde=ON, ambra
  pulsante=rampa, rosso=errore/sovracorrente) — più leggibile del solo
  testo.
- **Badge polarità** (`+HV` / `−HV`) accanto al nome canale, su
  **entrambi** i tipi di modulo: su DT5780 arriva solo da `polarity` in
  config.json, su hvwrapper viene letta dall'hardware (a meno che non la
  fissi anche lì in config.json). È statica, mostrata una volta per
  connessione.
- Se la lettura del monitor di un canale fallisce, compare un **testo
  rosso** sotto al canale con il messaggio d'errore esatto, senza
  bloccare gli altri canali/moduli né i comandi ON/OFF/VSet/ISet/rampa
  (che contano come riusciti appena arrivano all'hardware, indipendentemente
  dall'esito della rilettura successiva).

## API principali

| Metodo | Path | Cosa fa |
|---|---|---|
| GET | `/api/modules` | Elenco moduli da config.json |
| GET | `/api/status` | Stato di tutti i moduli |
| POST | `/api/config/reload` | Ricarica config.json |
| POST | `/api/modules/{name}/connect` | Connette il modulo (applica config di default) |
| POST | `/api/modules/{name}/disconnect` | Disconnette il modulo |
| POST | `/api/modules/{name}/apply-config` | Riapplica VSet/ISet/rampe da config.json |
| POST | `/api/modules/{name}/channels/{ch}/vset` | Imposta VSet |
| POST | `/api/modules/{name}/channels/{ch}/iset` | Imposta ISet (limite di corrente) |
| POST | `/api/modules/{name}/channels/{ch}/power` | ON/OFF |
| POST | `/api/modules/{name}/channels/{ch}/ramp` | Imposta rampe |
| WS | `/ws/monitor` | Stato live di tutti i moduli, push ogni 0.5s |

Identiche per entrambi i tipi di driver — `manager.py` sceglie la classe
giusta in base al campo `driver` del modulo, `main.py` e il frontend non
sanno (né devono sapere) con quale libreria sta parlando davvero.

## Note per allineare i driver alla tua installazione

- **`module_driver.py`** (driver `dpp`) usa le chiamate `caen_libs.caendpplib`
  verificate contro `CAENDPPLib.h`/`_caendpplibtypes.py` di riferimento.
  Se la tua versione installata espone nomi/firme leggermente diversi,
  allinea i punti in `_refresh_channel`, `set_vset`, `set_iset`,
  `set_power`, `set_ramp`, `connect`.
- **`hvwrapper_driver.py`** (driver `hvwrapper`) **scopre a runtime** i
  nomi dei parametri di canale (VSet, VMon, IMon, ISet, Pw, rampe,
  polarità) invece di averli hardcoded, provando un elenco di alias
  comuni (`_PARAM_ALIASES` in cima al file). Se alla connessione un
  modulo dà errore tipo `non trovo i parametri [...] tra quelli esposti
  dalla board (...)`, l'elenco tra parentesi mostra i nomi reali:
  aggiungili agli alias giusti in `_PARAM_ALIASES`. Lo stesso vale se
  scrivi su `iset` e la board non lo trova: l'errore elenca i parametri
  realmente disponibili.
- Se sul tuo V6533 la polarità non compare, guarda il terminale di
  uvicorn subito dopo la connessione: c'è una riga `[hvwrapper] Modulo
  '...' : nessun parametro polarita' trovato...` con l'elenco reale dei
  parametri — usalo per capire il nome giusto, oppure aggira il problema
  scrivendo `"polarity"` a mano in config.json per quel modulo.
- Il limite di tensione nel form (0–8000 V) e di corrente (0–10000 µA)
  sono generosi apposta per coprire varianti; se vuoi un tetto più
  stretto, aggiorna `Field(le=...)` in `main.py` (classi `VSetRequest` /
  `ISetRequest`).