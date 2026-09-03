#!/bin/bash

SESSION="test"

tmux new-session -d -s "$SESSION" 'python3 set_voltage.py'
tmux split-window -h 'python3 /run/media/bragg/LAB_ELETTRO/Script/Query_fot_a34411a_multimeter/set_voltage.py'
tmux select-pane -L
tmux attach-session -t "$SESSION"
