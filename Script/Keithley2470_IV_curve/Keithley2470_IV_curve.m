%% Initialization
clc;
clearvars;
close all;

%% parameter to be set
current_compliance      = '100e-6';         % [A]
max_voltage     = -5;               % value with sign [V]
voltage_step    = 1;                % absolute value  [V]
voltage_step_back = 1;              % absolute value [V]
filename = 'pad';
filename_format = '.txt';           % filename structure: filename + datetime + .txt
Keithley2470.IP = '10.196.31.142' ; % check and modify each time

%% Create and init Keithley TCPIP object
Keithley2470.P = tcpip(Keithley2470.IP,5025);                % Create the TCPIP object
fopen(Keithley2470.P);                                       % Connect TCPIP object
fprintf(Keithley2470.P,'*RST');                              % Reset
fprintf(Keithley2470.P,':SOUR:VOLT 0');                      % Voltage 0V
fprintf(Keithley2470.P,':OUTP:STAT OFF');                    % Output off
pause(2)
fprintf(Keithley2470.P,':ABOR');                             % Abort
fprintf(Keithley2470.P,':TRIG:BLOC:BUFF:CLE 1');             % Clear buffer
fprintf(Keithley2470.P,':TRIG:BLOC:MEAS 1');                 % Init buffer
fprintf(Keithley2470.P,':INIT');
fprintf(Keithley2470.P,'*WAI');
fprintf(Keithley2470.P,':SOUR:FUNC VOLT'); 
fprintf(Keithley2470.P,':SENS:CURR:RANG:AUTO ON');           % Current set range AUTO
fprintf(Keithley2470.P,':SOUR:VOLT:RANG 200');               % Voltage set range 200V

if abs(max_voltage)>200
    fprintf(Keithley2470.P,':SOUR:VOLT:RANG 1000');               % Voltage set range 2000V
end

string = [':SOUR:VOLT:ILIM ',current_compliance];
fprintf(Keithley2470.P,string);

Keithley2470.cont=0;
Keithley2470.cond_t = 0;
Keithley2470.kei_volt = max_voltage;                    % voltage sweep
Keithley2470.kei_curr = 0;
Keithley2470.kei_volt_step = voltage_step;              % voltage step during curve
Keithley2470.kei_volt_step_back = voltage_step_back;    % voltage step during returning curve
Keithley2470.kei_volt_act = 0;
Keithley2470.steps = abs(floor(Keithley2470.kei_volt/Keithley2470.kei_volt_step));
Keithley2470.steps_back = abs(floor(Keithley2470.kei_volt/Keithley2470.kei_volt_step_back));
Keithley2470.time = 1;
Keithley2470.exit_cycle = 0;
Keithley2470.meas = 0;
Keithley2470.cont_lmt = Keithley2470.steps + Keithley2470.steps_back + 1;
Keithley2470.data_curr = [];
Keithley2470.data_volt = [];
Keithley2470.cont=0;

fprintf(Keithley2470.P,':OUTP:STAT ON');

if mod(Keithley2470.kei_volt,Keithley2470.kei_volt_step) ~= 0
    fprintf('Invalid step size.\n')
    fclose(Keithley2470.P);
    return
elseif mod(Keithley2470.kei_volt,Keithley2470.kei_volt_step_back) ~= 0
    fprintf('Invalid returning curve step size.\n')
    fclose(Keithley2470.P);
    return
end

% Preallocating memory
voltage_vector = zeros(Keithley2470.cont_lmt,1);
voltage_vector_meas = zeros(Keithley2470.cont_lmt,1);
current_vector =zeros(Keithley2470.cont_lmt,1);

f1 = figure;
ax = gca;
ax.YScale = 'log';

%% Working cycle
while Keithley2470.cont < Keithley2470.cont_lmt
    tic
    if Keithley2470.cont == 0
        Keithley2470.kei_volt_act = 0;
    elseif Keithley2470.cont < Keithley2470.steps + 1
        if Keithley2470.kei_volt > 0
            Keithley2470.kei_volt_act = Keithley2470.kei_volt_act+Keithley2470.kei_volt_step;
        elseif Keithley2470.kei_volt < 0
            Keithley2470.kei_volt_act = Keithley2470.kei_volt_act-Keithley2470.kei_volt_step;
        end
    else
        if Keithley2470.kei_volt > 0
            Keithley2470.kei_volt_act = Keithley2470.kei_volt_act-Keithley2470.kei_volt_step_back;
        elseif Keithley2470.kei_volt < 0
            Keithley2470.kei_volt_act = Keithley2470.kei_volt_act+Keithley2470.kei_volt_step_back;
        end
    end

    % Printing values of voltage and current
    string = [':SOUR:VOLT ',num2str(Keithley2470.kei_volt_act)];
    fprintf(Keithley2470.P,string);
    Keithley2470.data_volt = Keithley2470.kei_volt_act;
    Keithley2470.ActualvoltageVEditField.Value=Keithley2470.kei_volt_act;           
    Keithley2470.meas = query(Keithley2470.P,':MEAS:CURR?');
    
    measure_curr = query(Keithley2470.P,':MEAS:CURR?');
    Keithley2470.data_time = 1:1:Keithley2470.time;      
    help_curr = abs(str2num(measure_curr));
        
    % saving data into vector
    if help_curr<(1)
        voltage_vector(Keithley2470.time)=Keithley2470.kei_volt_act;
        current_vector(Keithley2470.time)=help_curr;
    end
    fprintf('%0.3f,%0.3e\n',Keithley2470.kei_volt_act,help_curr);
    Keithley2470.time = Keithley2470.time + 1;
    Keithley2470.cont = Keithley2470.cont+1;
    pause(1-toc);
    
    plot(voltage_vector(1:Keithley2470.cont),current_vector(1:Keithley2470.cont),'-ob');
    xlabel('Voltage [V]');
    ylabel('Current [A]');
    
    if Keithley2470.cont == Keithley2470.cont_lmt
        fprintf(Keithley2470.P,':OUTP:STAT OFF');
    end
end
fclose(Keithley2470.P);

%% Data plot and saving
datetime.setDefaultFormats('default','yyyyMMdd_hhmm')
t = datetime('now');
filename_to_use = strcat(filename,'_',char(t),filename_format);
filename_to_use_for_figure = strcat(filename,'_',char(t),'.png');
fileID = fopen(filename_to_use,'w');
fprintf(fileID,'voltage[V],current[A]\n')
for i = 1:length(voltage_vector)
    fprintf(fileID,'%0.3f,%0.3e\n',voltage_vector(i),current_vector(i));
end 
fclose(fileID);


datetime.setDefaultFormats('default','yyyy-MM-dd hh:mm')
t = datetime('now');
figure_title = strcat(filename,' ',char(t));
title(figure_title);
saveas(f1,filename_to_use_for_figure);
