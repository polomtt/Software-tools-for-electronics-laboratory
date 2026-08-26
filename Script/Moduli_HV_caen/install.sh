#!/usr/bin/env bash
#
# install.sh
# ==========
# Installa tutto il necessario per far girare la web app CAEN HV Control
# (lato Python/FastAPI). Le librerie CAEN native NON possono essere
# scaricate qui perché richiedono un account gratuito sul sito CAEN —
# questo script le installa automaticamente SOLO se trova i pacchetti
# .deb/.run già scaricati in ./caen-installers (vedi sotto), altrimenti
# stampa le istruzioni.
#
# Servono due gruppi di librerie native, a seconda dei moduli che usi
# (vedi backend/config.json):
#   - driver "dpp"       (es. DT5780): CAENComm + CAENDigitizer + CAENDPPLib
#   - driver "hvwrapper"  (es. V6533):  CAENVMELib + CAENHVWrapper
#
# Uso:
#   ./install.sh
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
CAEN_INSTALLERS_DIR="$SCRIPT_DIR/caen-installers"

echo "== CAEN HV Control — installazione =="
echo "Cartella progetto: $SCRIPT_DIR"
echo

# --------------------------------------------------------------------- #
# 1. Dipendenze di sistema
# --------------------------------------------------------------------- #
if command -v apt-get >/dev/null 2>&1; then
    echo "-- Installo dipendenze di sistema (apt) --"
    # '|| true': se un repository di terze parti e' irraggiungibile/rotto,
    # apt-get update esce con errore anche se i repo principali (Ubuntu,
    # security, ecc.) sono stati letti correttamente. Non e' un problema
    # nostro, quindi non blocchiamo l'installazione per questo.
    sudo apt-get update -y || echo "  (alcuni repository non erano raggiungibili, proseguo comunque)"
    sudo apt-get install -y \
        python3 \
        python3-venv \
        python3-pip \
        build-essential \
        libusb-1.0-0 \
        libusb-1.0-0-dev
else
    echo "!! apt-get non trovato: salto l'installazione delle dipendenze di sistema."
    echo "   Assicurati manualmente di avere: python3, python3-venv, pip, libusb-1.0."
fi
echo

# --------------------------------------------------------------------- #
# 2. Virtual environment Python
# --------------------------------------------------------------------- #
echo "-- Creo/aggiorno il virtual environment in $VENV_DIR --"
if [ ! -d "$VENV_DIR" ]; then
    python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

pip install --upgrade pip
pip install -r "$BACKEND_DIR/requirements.txt"

echo
echo "-- Dipendenze Python installate nel venv --"
echo

# --------------------------------------------------------------------- #
# 3. Librerie CAEN native
# --------------------------------------------------------------------- #
echo "-- Verifica librerie CAEN native --"

if [ -d "$CAEN_INSTALLERS_DIR" ]; then
    echo "Trovata cartella $CAEN_INSTALLERS_DIR: provo a installare i pacchetti CAEN presenti."

    shopt -s nullglob
    deb_files=("$CAEN_INSTALLERS_DIR"/*.deb)
    run_files=("$CAEN_INSTALLERS_DIR"/*.run)
    shopt -u nullglob

    if [ ${#deb_files[@]} -gt 0 ]; then
        for f in "${deb_files[@]}"; do
            echo "  dpkg -i $f"
            sudo dpkg -i "$f" || sudo apt-get install -f -y
        done
    fi

    if [ ${#run_files[@]} -gt 0 ]; then
        for f in "${run_files[@]}"; do
            echo "  eseguo installer $f"
            chmod +x "$f"
            sudo "$f" --mode unattended || sudo "$f"
        done
    fi

    if [ ${#deb_files[@]} -eq 0 ] && [ ${#run_files[@]} -eq 0 ]; then
        echo "  Nessun .deb o .run trovato in $CAEN_INSTALLERS_DIR."
    fi
else
    echo "  Cartella $CAEN_INSTALLERS_DIR non trovata: nessuna installazione automatica."
fi

echo
echo "-- Verifico che il binding Python trovi le librerie native --"

DPP_OK=0
HVWRAP_OK=0

if python3 -c "from caen_libs import caendpplib" >/dev/null 2>&1; then
    echo "  OK: caen_libs.caendpplib si importa correttamente (moduli driver=\"dpp\", es. DT5780)."
    DPP_OK=1
else
    echo "  MANCA: caen_libs.caendpplib non si importa (serve per moduli driver=\"dpp\", es. DT5780)."
fi

if python3 -c "from caen_libs import caenhvwrapper" >/dev/null 2>&1; then
    echo "  OK: caen_libs.caenhvwrapper si importa correttamente (moduli driver=\"hvwrapper\", es. V6533)."
    HVWRAP_OK=1
else
    echo "  MANCA: caen_libs.caenhvwrapper non si importa (serve per moduli driver=\"hvwrapper\", es. V6533)."
fi

if [ "$DPP_OK" -eq 0 ] || [ "$HVWRAP_OK" -eq 0 ]; then
    cat <<'EOF'

  !! Una o entrambe le librerie native CAEN non risultano ancora
     installate/visibili. Installa solo quelle che ti servono in base ai
     moduli che hai in backend/config.json.

  Passi manuali (serve un account gratuito su caen.it):
    1. Vai su https://www.caen.it/download/ e scarica, per il tuo OS:

       Per moduli driver="dpp" (es. DT5780):
         - Driver USB CAEN (o driver A2818/A3818 se usi il link ottico)
         - CAENComm
         - CAENDigitizer
         - CAENDPPLib

       Per moduli driver="hvwrapper" (es. V6533, via bridge V1718/V2718):
         - CAENVMELib
         - CAENHVWrapper

       Installa i pacchetti nell'ordine indicato sopra, per il gruppo che
       ti serve (puoi installarli entrambi se usi entrambi i tipi di modulo).

    2. In alternativa: metti i file .deb/.run scaricati nella cartella
         ./caen-installers
       e rilancia questo script: proverà a installarli automaticamente
       con dpkg/eseguendo l'installer.

    3. Ricontrolla con:
         source backend/venv/bin/activate
         python3 -c "from caen_libs import caendpplib"
         python3 -c "from caen_libs import caenhvwrapper"

EOF
fi

echo
echo "== Installazione completata =="
echo "Avvia la web app con:  ./start.sh"
