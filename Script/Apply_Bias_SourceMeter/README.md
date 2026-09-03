# SMU Control — Curva IV / Bias

Interfaccia web per pilotare lo strumento (SMU via PyVISA/VISA su TCPIP) al
posto dello script `set_voltage.py`: stessi comandi SCPI, ma con controllo
da browser, avvio/stop, e grafico Tempo-Corrente in tempo reale.

## Installazione

```bash
cd iv_webapp
pip install -r requirements.txt
python app.py
```

Poi apri **http://localhost:5000** (o l'IP del PC, se ti connetti da
un'altra macchina sulla stessa rete).

## Come funziona

**Tab "Misura"**
- Menu a tendina per scegliere la modalita':
  - **Curva IV**: rampa 0 → V_set con lo step impostato, poi ridiscende
    subito a 0. Il grafico e il file si compilano durante tutta la rampa,
    esattamente come nello script originale.
  - **Applico BIAS**: rampa 0 → V_set, poi resta a V_set continuando a
    campionare la corrente (periodo impostabile in "Impostazioni") finche'
    non premi **STOP**; a quel punto ridiscende a 0 con lo stesso step/ritardo.
- **START/STOP**: se premi STOP durante una rampa o durante il bias, lo
  strumento scende comunque in modo controllato fino a 0 V prima di
  fermarsi (non stacca mai la tensione di colpo).
- I riquadri mostrano tensione/corrente correnti, tempo trascorso, numero
  di punti acquisiti e il percorso del file `.txt` che si sta scrivendo in
  `Data/` (stesso formato `time[s],voltage[V],current[A]` di prima).

**Tab "Impostazioni"**
- Nome campione, indirizzo VISA dello strumento, V_set, step di tensione,
  ritardo tra i passi, compliance di corrente e periodo di campionamento
  durante il bias.
- Il pulsante **SETTA PARAMETRI** salva i valori lato server; sono
  modificabili solo quando non c'e' una misura in corso.

**Grafico**
- Tempo vs Corrente, aggiornato in tempo reale durante l'acquisizione.

## Struttura dei file

```
iv_webapp/
├── app.py            # server Flask + macchina a stati della misura
├── instrument.py      # wrapper PyVISA (stessa logica di set_voltage.py)
├── requirements.txt
├── templates/
│   └── index.html
├── static/
│   ├── style.css
│   └── main.js
└── Data/               # qui vengono salvati i file .txt delle misure
```

## Note

- Il salvataggio su file e la sequenza di comandi SCPI (`:SOUR:FUNC VOLT`,
  `:SOUR:VOLT:ILIM`, `:OUTP:STAT`, ecc.) sono identici allo script
  originale: ho solo riorganizzato la logica in una classe (`Instrument`)
  e in una macchina a stati (`MeasurementController`) eseguita in un
  thread separato, cosi' il server Flask resta reattivo mentre la rampa e'
  in corso.
- Se vuoi il grafico finale Tensione-Corrente (come nello script
  originale, con `plt.savefig`) lo possiamo aggiungere come export a fine
  misura: al momento l'interfaccia mostra Tempo-Corrente live, come
  richiesto.
