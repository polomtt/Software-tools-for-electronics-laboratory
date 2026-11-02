#!/bin/bash

conda activate SHINE

SESSION="Acquisizione_SHINE"

# Comando comune: attiva conda e poi lancia lo script.
# "; exec bash" tiene la finestra aperta se lo script termina o va in errore.
ACTIVATE="source \"$(conda info --base)/etc/profile.d/conda.sh\" && conda activate SHINE"

# Chiudo la sessione precedente (se esiste)
tmux kill-session -t "$SESSION" 2>/dev/null

# Finestra 1: main (PowerMeter)
tmux new-session -d -s "$SESSION" -n PowerMeter \
  "$ACTIVATE && python main.py; exec bash"

# Finestra 2: IBIL
tmux new-window -t "$SESSION" -n IBIL \
  "$ACTIVATE && python acquisition_IBIL.py; exec bash"

# Finestra 3: logger
tmux new-window -t "$SESSION" -n logger \
  "$ACTIVATE && python create_logger.py; exec bash"

echo "Sessione tmux '$SESSION' avviata in background."
echo "Per collegarti: tmux attach -t $SESSION"
