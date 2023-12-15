# IV curve with Keithley2470

Programma Matlab da usare per effettuare misure di curve IV con il Keithley 2470.
Per far funzionare il programma bisogna settare i seguenti paramteri che si trovano nella parte iniziale del codice:

+ `current_compliance`


current_compliance      = '100e-6';         % [A]
max_voltage     = -5;               % value with sign [V]
voltage_step    = 1;                % absolute value  [V]
voltage_step_back = 1;              % absolute value [V]
filename = 'pad';
filename_format = '.txt';           % filename structure: filename + datetime + .txt
Keithley2470.IP = '10.196.31.142' ; % check and modify each time

<ul>
<li>10/11/2023 File Creation
It allows you to perform a linear voltage sweep and current measurement.
Creates a text file with the data and displays the figure with the data
<\hl>
