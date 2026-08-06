#!/bin/bash

tmux kill-session -t Acquisizione_SHINE

SESSION="Acquisizione_SHINE"

# Crea la sessione e avvia il main che gestisce il PowerMeter
tmux new-session -d -s $SESSION -n PowerMeter "python main.py"

# Crea la seconda window che gestisce l'IBIL
tmux new-window -t $SESSION -n IBIL "python acquisition_IBIL.py"

# tmux new-window -t $SESSION -n IBIL "python acquisition_IBIL_debug.py"

# Lascia la sessione in background
tmux detach -s $SESSION

echo "Sessione tmux '$SESSION' avviata in background."
echo "Per collegarti: tmux attach -t $SESSION"


