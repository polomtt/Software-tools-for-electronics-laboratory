#!/bin/bash
set -euo pipefail

SESSION_NAME="caen-hv"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"
CONFIG_DIR="$SCRIPT_DIR/config_file"

HOST="127.0.0.1"
PORT="8005"
RELOAD_FLAG="--reload"


# ============================================================
# ARGOMENTI
# ============================================================

while [ $# -gt 0 ]; do
    case "$1" in
        --lan)
            HOST="0.0.0.0"
            shift
            ;;
        --port)
            if [ $# -lt 2 ]; then
                echo "Errore: --port richiede una porta."
                exit 1
            fi
            PORT="$2"
            shift 2
            ;;
        --no-reload)
            RELOAD_FLAG=""
            shift
            ;;
        *)
            echo "Argomento sconosciuto: $1"
            exit 1
            ;;
    esac
done


# ============================================================
# CONTROLLO TMUX
# ============================================================

if ! command -v tmux >/dev/null 2>&1; then
    echo "Errore: tmux non è installato."
    echo
    echo "Installa con:"
    echo "  sudo apt install tmux"
    exit 1
fi


# ============================================================
# CONTROLLO SESSIONE GIÀ ESISTENTE
# ============================================================

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "La sessione '$SESSION_NAME' è già attiva."
    echo
    echo "Per collegarti:"
    echo "  tmux attach -t $SESSION_NAME"
    echo
    exit 0
fi


# ============================================================
# SELEZIONE CONFIGURAZIONE
# ============================================================

CONFIG=$(find "$CONFIG_DIR" \
    -maxdepth 1 \
    -name "config_*.json" \
    -printf "%f\n" |
    sed 's/^config_//; s/\.json$//' |
    zenity --list \
        --title="Selezione configurazione" \
        --text="Quale configurazione vuoi utilizzare?" \
        --column="Configurazione")

if [ -z "$CONFIG" ]; then
    echo "Nessuna configurazione selezionata."
    exit 1
fi

export CAEN_CONFIG_PATH="$CONFIG_DIR/config_${CONFIG}.json"


# ============================================================
# CONTROLLO VENV
# ============================================================

if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment non trovato:"
    echo "$VENV_DIR"
    echo
    echo "Esegui prima:"
    echo "./install.sh"
    exit 1
fi


# ============================================================
# CREAZIONE COMANDO
# ============================================================

if [ -n "$RELOAD_FLAG" ]; then
    UVICORN_CMD="python -m uvicorn main:app --host $HOST --port $PORT --reload"
else
    UVICORN_CMD="python -m uvicorn main:app --host $HOST --port $PORT"
fi


# ============================================================
# AVVIO TMUX
# ============================================================

echo
echo "Avvio server dentro tmux..."
echo
echo "Sessione: $SESSION_NAME"
echo "Config:   $CAEN_CONFIG_PATH"
echo "URL:      http://$HOST:$PORT"
echo


tmux new-session \
    -d \
    -s "$SESSION_NAME" \
    -c "$BACKEND_DIR" \
    "source '$VENV_DIR/bin/activate' && export CAEN_CONFIG_PATH='$CAEN_CONFIG_PATH' && echo '========================================' && echo ' CAEN HV Control' && echo '========================================' && echo 'Config: $CAEN_CONFIG_PATH' && echo 'URL: http://$HOST:$PORT' && echo && $UVICORN_CMD"


# ============================================================
# CONTROLLO AVVIO
# ============================================================

sleep 1

if tmux has-session -t "$SESSION_NAME" 2>/dev/null; then
    echo "Server avviato correttamente."
    echo
    echo "Il server continua a funzionare anche se chiudi il terminale."
    echo
    echo "Per vedere il server:"
    echo "  tmux attach -t $SESSION_NAME"
    echo
    echo "Per uscire da tmux senza fermarlo:"
    echo "  CTRL+B"
    echo "  poi D"
    echo
    echo "Per fermare completamente il server:"
    echo "  tmux kill-session -t $SESSION_NAME"
    echo
else
    echo "ERRORE: il server non è rimasto attivo."
    echo
    echo "Controlla con:"
    echo "  tmux ls"
    echo
    exit 1
fi
