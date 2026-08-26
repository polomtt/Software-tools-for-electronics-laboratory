#!/usr/bin/env bash
#
# start.sh
# ========
# Avvia il backend (che serve anche il frontend statico) indipendentemente
# dalla cartella da cui viene lanciato questo script.
#
# Uso:
#   ./start.sh                 # porta 8000, solo localhost
#   ./start.sh --lan           # accessibile anche da altri dispositivi in rete locale
#   ./start.sh --port 9000     # porta custom
#   ./start.sh --no-reload     # disabilita l'auto-reload (consigliato in "produzione")
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$SCRIPT_DIR/backend"
VENV_DIR="$BACKEND_DIR/venv"

HOST="127.0.0.1"
PORT="8000"
RELOAD_FLAG="--reload"

while [ $# -gt 0 ]; do
    case "$1" in
        --lan)
            HOST="0.0.0.0"
            shift
            ;;
        --port)
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

if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment non trovato in $VENV_DIR."
    echo "Esegui prima ./install.sh"
    exit 1
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

cd "$BACKEND_DIR"

echo "== Avvio CAEN HV Control =="
echo "Config:  ${CAEN_CONFIG_PATH:-$BACKEND_DIR/config.json}"
echo "URL:     http://$HOST:$PORT"
echo

# shellcheck disable=SC2086
exec python -m uvicorn main:app --host "$HOST" --port "$PORT" $RELOAD_FLAG
