function [current,voltage_applied]=inizialize_keithley (voltage,R)
    % Find and create GPIB object.
    obj1 = instrfind('Type', 'gpib', 'BoardIndex', 0, 'PrimaryAddress', 24, 'Tag', '');
    if isempty(obj1)
        obj1 = gpib('NI', 0, 24);%%cambio 0 con 1
    else
        fclose(obj1);
        obj1 = obj1(1);
    end
    fopen(obj1);
    
 fprintf(obj1, ':TRIG:SOUR IMM;:SYST:FRSW FRONT;:SOUR1:FUNC VOLT;:SOUR1:VOLT:MODE FIX;:SOUR1:VOLT:RANGE:AUTO ON;:SENSE:CURR:NPLC 4.00;:SENSE:CURR:PROT:LEV 50e-6;:SENSE:CURR:RANGE:AUTO ON;:SENSE:FUNC:CONC ON;:SENSE:FUNC "VOLT","CURR";:FORM:ELEM VOLT,CURR;' ) 
%
pause (1)

 fprintf(obj1, 'OUTP:STATE ON;')
pause (1)


% 1) trovo la tensione attuale
% 2) definisco un incremento/decremento =2.5
% 3) tensione da applicare / 10
% 4) mi calcolo il vettore di tensioni che via via applicherò
% 5) ciclo for che lo fa


fprintf(obj1, ':READ?')
pause (1)
results = str2num(fscanf(obj1));

applied_voltage= abs(results(1)-voltage);

num_step=ceil(applied_voltage/2.5);

%ce la faccio in num_step punti


steps=linspace(results(1),voltage,num_step);

for i=1:length(steps)
 volt= num2str(steps(i));
fprintf(obj1, ['SOUR1:VOLT:LEV:IMM:AMPL ', volt]) 
fprintf(obj1, 'OUTP:STATE ON;')
pause(3)
end


fprintf(obj1, ':READ?')
pause (1)
results = str2num(fscanf(obj1));

voltage_applied=round(results(1));
current=results(2);

%---
%prova con resistenze:


applied_voltage = voltage_applied-R*current;
error = 2.5;

 
while ( (abs(applied_voltage - voltage)) >= error)
  
   
    fprintf(obj1, ':READ?') %leggo valore
    pause (1)
    results = str2num(fscanf(obj1)); 
    
    voltage_applied=round(results(1));
    current = results(2);
    
%     voltage_test = abs(results(1)-(voltage+R*current));%10->voltage

    num_step=ceil((R*current)/(2.5));

    %ce la faccio in num_step punti


    steps=linspace(results(1),(voltage+R*current),num_step);

    for i=1:length(steps)
     volt= num2str(steps(i));
    fprintf(obj1, ['SOUR1:VOLT:LEV:IMM:AMPL ', volt]) 
    fprintf(obj1, 'OUTP:STATE ON;')
    pause(3)
    end
    
    fprintf(obj1, ':READ?')
    pause (1)
    results = str2num(fscanf(obj1));

    voltage_applied=round(results(1));
    current=results(2);
    
    applied_voltage = voltage_applied-R*current;
    
end

fprintf(obj1, ':READ?')
pause (1)
results = str2num(fscanf(obj1));

voltage_applied=round(results(1));
current=results(2);
%---

% Disconnect from instrument object, obj1.
handle_keithley = obj1; 




 fclose(obj1);
 end

