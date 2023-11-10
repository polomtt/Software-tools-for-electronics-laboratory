
%parameter to be set
curr_compl      = '1e-4'; % [Ampere]
max_voltage     = -4.0;    % value with sign [Volt]
voltage_step    = 1.0;     % absolute value  [Volt]
filename = "pad";
filename_format = ".txt"; %filename strucutre: filename + datetime + .txt
Keithley2470.IP = '10.196.37.68' ; % to check and modify each time

% Create and init Keithley TCPIP object.

Keithley2470.P = tcpip(Keithley2470.IP,5025); %create TCPIP object
fopen(Keithley2470.P); %connect TCPIP object
fprintf(Keithley2470.P,'*RST'); %reset
fprintf(Keithley2470.P,':SOUR:VOLT 0'); %voltage 0V
fprintf(Keithley2470.P,':OUTP:STAT OFF'); %output off
pause(2)
fprintf(Keithley2470.P,':ABOR'); %abort
fprintf(Keithley2470.P,':TRIG:BLOC:BUFF:CLE 1'); %clear buffer
fprintf(Keithley2470.P,':TRIG:BLOC:MEAS 1'); %init buffer
fprintf(Keithley2470.P,':INIT');
fprintf(Keithley2470.P,'*WAI');
fprintf(Keithley2470.P,':SOUR:FUNC VOLT'); 
fprintf(Keithley2470.P,':SENS:CURR:RANG:AUTO ON');

string = [':SOUR:VOLT:ILIM ',curr_compl];
fprintf(Keithley2470.P,string);

voltage_vector = [];
voltage_vector_meas = [];
current_vector = [];
Keithley2470.cont=0;
Keithley2470.cond_t = 0;
Keithley2470.kei_comp = 20;
Keithley2470.kei_volt = max_voltage; %voltage sweep
Keithley2470.kei_curr = 0;
Keithley2470.kei_volt_step = voltage_step; %voltage step
Keithley2470.kei_volt_act = 0;
Keithley2470.steps = 0;
Keithley2470.steps_back = 0;
Keithley2470.time = 1;
Keithley2470.exit_cycle = 0;
Keithley2470.meas = 0;
Keithley2470.steps = abs(floor(Keithley2470.kei_volt/Keithley2470.kei_volt_step));
Keithley2470.data_curr = [];
Keithley2470.data_volt = [];
Keithley2470.cont=0;

fprintf(Keithley2470.P,':OUTP:STAT ON');

while Keithley2470.cont < 2*Keithley2470.steps + 1
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
            Keithley2470.kei_volt_act = Keithley2470.kei_volt_act-Keithley2470.kei_volt_step;
        elseif Keithley2470.kei_volt < 0
            Keithley2470.kei_volt_act = Keithley2470.kei_volt_act+Keithley2470.kei_volt_step;
        end
    end
    string = [':SOUR:VOLT ',num2str(Keithley2470.kei_volt_act)];
    fprintf(Keithley2470.P,string);
    Keithley2470.data_volt = Keithley2470.kei_volt_act;
    Keithley2470.ActualvoltageVEditField.Value=Keithley2470.kei_volt_act;           
    Keithley2470.meas = query(Keithley2470.P,':MEAS:CURR?');
    
    measure_curr = query(Keithley2470.P,':MEAS:CURR?');
    Keithley2470.data_time = [1:1:Keithley2470.time];  
    
    %save data into vetor
    voltage_vector(Keithley2470.time)=Keithley2470.kei_volt_act;
    current_vector(Keithley2470.time)=str2num(measure_curr);
    fprintf("%0.3f,%0.3e\n",Keithley2470.kei_volt_act,str2num(measure_curr));
    Keithley2470.time = Keithley2470.time + 1;
    Keithley2470.cont = Keithley2470.cont+1;
    pause(1-toc);
    if Keithley2470.cont == 2*Keithley2470.steps + 1
        fprintf(Keithley2470.P,':OUTP:STAT OFF');
    end
end
fclose(Keithley2470.P);

%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%%
datetime.setDefaultFormats('default','yyyyMMdd_hhmm')
t = datetime("now");
filename_to_use = strcat(filename,"_",char(t),filename_format);
filename_to_use_for_figure = strcat(filename,"_",char(t),".png");
fileID = fopen(filename_to_use,'w');
fprintf(fileID,"voltage[V],current[A]\n")
for i = 1:length(voltage_vector)
    fprintf(fileID,"%0.3f,%0.3e\n",voltage_vector(i),current_vector(i));
end 
fclose(fileID);

f1 = figure;
datetime.setDefaultFormats('default','yyyy-MM-dd hh:mm')
t = datetime("now");
figure_title = strcat(filename," ",char(t));
plot(voltage_vector,current_vector,'-bo');
title(figure_title);
xlabel('Voltage [V]');
ylabel('Current [A]');
saveas(f1,filename_to_use_for_figure);
hold off;
