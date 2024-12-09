
%host = '10.196.31.208';
%username = 'chadwick';
%password = '1111';

%comando = 'python3 save_to_file.py -e -f "beo"';

% Inizializza la connessione SSH
%ssh2_conn = ssh2_config(host, username, password);
%ssh2_conn = ssh2_command(ssh2_conn, 'ls -la *ninjas*');
%command_output = ssh2_simple_command(host, username, password,'ls -la *ninjas*');

%disp(command_output)

host = 'chadwick@10.196.31.208'; % Utente e indirizzo del server
command = 'python3 /home/chadwick/abcd/bin/save_to_file.py -e -f "beo" ';

% Chiave SSH (opzionale)
keyFile = '1111';

% Esegui il comando SSH
system(['ssh ', host, ' "', command, '"']);