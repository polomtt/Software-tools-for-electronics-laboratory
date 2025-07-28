function [wave_data] = OscilloAcquisition(OSCI_IP,ch1_enable,ch2_enable,num_wave_mean)
% OscilloAcquisition is the function used to acquire the oscilloscope
% wave.
%
%__________________________________________________________________________
%
% OSCI_IP must be in the form of: 'TCPIP0::10.196.31.127::inst0::INSTR'
% ch1_enable (true or false) -> enable channel 1 of oscilloscope
% ch2_enable (true or flase) -> enable channel 2 of oscilloscope
% num_wave -> number of wave to save
% filename -> name of the .txt file where to save the acquired data

% Clear MATLAB workspace of any previous instrument connections
instrreset;

% Create a VISA object and set the |InputBufferSize| to allow for transfer
% of waveform from oscilloscope to MATLAB. Tek VISA needs to be installed.
myScope = visa('ni', OSCI_IP);
myScope.InputBufferSize = 1e7;

% Set the |ByteOrder| to match the requirement of the instrument
myFgen.ByteOrder = 'littleEndian';

% Open the connection to the oscilloscope
fopen(myScope);

% Turn headers off, this makes parsing easier
fprintf(myScope, 'HEADER OFF');
fprintf(myScope, 'HORizontal:RECOrdlength 1000');
pause(0.1); % tempo per assestamento
% Get record length value
recordLength = query(myScope, 'HOR:RECO?');
% Ensure that the start and stop values for CURVE query match the full
% record length
fprintf(myScope, ['DATA:START 1;DATA:STOP ' recordLength]);

disp(recordLength)

% Initialising empty wave matrix
wave_data = zeros(3,str2double(recordLength))';

if ch1_enable
    % Read YMULT to calculate the vertical values
    fprintf(myScope, 'DATa:SOUrce CH1');
    verticalScale  = query(myScope,'WFMOUTPRE:YMULT?');
    % Read YOFFSET to calculate the vertical values
    yOffset = query(myScope, 'WFMO:YOFF?');

if ch2_enable
    fprintf(myScope, 'DATa:SOUrce CH2');
    verticalScale_2  = query(myScope,'WFMOUTPRE:YMULT?');
    disp('vertical_scale');
    disp(verticalScale_2);
    % Read YOFFSET to calculate the vertical values
    yOffset2 = query(myScope, 'WFMO:YOFF?');
end

% Time scale
hor_scale = str2double(query(myScope,'HORizontal:SCAle?'));
sample_time = (hor_scale*10)/str2double(recordLength);

time = zeros(1,str2double(recordLength))';

for i=1:str2double(recordLength)
    time(i)=i*sample_time;
end

t1 = datetime('now');

% Request 8 bit binary data on the CURVE query
fprintf(myScope, 'DATA:ENCDG RIBINARY;WIDTH 1');
hold on

if ch1_enable
    fprintf(myScope, 'DATa:SOUrce CH1');
    
    % Imposta modalità di acquisizione su AVERAGE con 4 acquisizioni
    fprintf(myScope, 'ACQuire:MODe AVERage');
    fprintf(myScope, 'ACQuire:NUMAVg %d', num_wave_mean);

    % Aspetta che le medie siano completate (puoi usare *OPC? oppure *WAI se supportato)
    fprintf(myScope, '*WAI');

    fprintf(myScope, 'CURVE?');
    wave_data(:,2) = (str2double(verticalScale) * (binblockread(myScope,'int8')))' - str2double(yOffset)*str2double(verticalScale);
end

if ch2_enable
    fprintf(myScope, 'DATa:SOUrce CH2');

    % Imposta modalità di acquisizione su AVERAGE con 4 acquisizioni
    fprintf(myScope, 'ACQuire:MODe AVERage');
    fprintf(myScope, 'ACQuire:NUMAVg %d', num_wave_mean);

    % Aspetta che le medie siano completate (puoi usare *OPC? oppure *WAI se supportato)
    fprintf(myScope, '*WAI');

    fprintf(myScope, 'CURVE?');
    wave_data(:,3) = (str2double(verticalScale_2) * (binblockread(myScope,'int8')))' - str2double(yOffset2)*str2double(verticalScale_2);
end

flushinput(myScope);

t2 = datetime('now');

disp(between(t2,t1));

% Saving the acquired data
wave_data(:,1) = time(:);

% str_file_mean = strcat('data\',filename,'_mean','.txt');
% fid_mean = fopen(str_file_mean, 'w');
% fprintf(fid_mean,'time,ch1_mean,ch2_mean\n');
% 
% for j=1:str2double(recordLength)
%     help1=0;
%     help2=0;
%     if ch1_enable
%         help1 = wave_data(j,2);
%     elseif ch2_enable
%         help2 = wave_data(j,3);
%     end
%     fprintf(fid_mean,'%e,%f,%f\n',sample_time*j,help1,help2);
% end
% 
% fclose(fid_mean);

% Clean up Close the connection
fclose(myScope);
% Clear the variable
clear myScope;
end

