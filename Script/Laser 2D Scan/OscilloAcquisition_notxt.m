function [wave_data] = OscilloAcquisition_notxt(OSCI_IP,ch1_enable,ch2_enable,num_wave)
% OscilloAcquisition is the function used to acquire the oscilloscope
% wave without saving on a txt file.
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
myScope.InputBufferSize = 1e8;

% Set the |ByteOrder| to match the requirement of the instrument
myFgen.ByteOrder = 'littleEndian';

% Open the connection to the oscilloscope
fopen(myScope);

% Turn headers off, this makes parsing easier
fprintf(myScope, 'HEADER OFF');
fprintf(myScope, 'HORizontal:RECOrdlength 10000');
% Get record length value
recordLength = query(myScope, 'HOR:RECO?');
% Ensure that the start and stop values for CURVE query match the full
% record length
fprintf(myScope, ['DATA:START 1;DATA:STOP' recordLength]);

% Initialising empty wave matrix
wave_data = zeros(3,str2double(recordLength))';
mean_data = zeros(num_wave,str2double(recordLength))';


if ch1_enable
    % Read YMULT to calculate the vertical values
    fprintf(myScope, 'DATa:SOUrce CH1');
    verticalScale  = query(myScope,'WFMOUTPRE:YMULT?');
    % Read YOFFSET to calculate the vertical values
    yOffset = query(myScope, 'WFMO:YOFF?');

elseif ch2_enable
    fprintf(myScope, 'DATa:SOUrce CH2');
    verticalScale_2  = query(myScope,'WFMOUTPRE:YMULT?');
    disp('vertical_scale');
    disp(verticalScale);
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
for i=1:num_wave

    if ch1_enable
        fprintf(myScope, 'DATa:SOUrce CH1');
        fprintf(myScope, 'CURVE?');
        data = (str2double(verticalScale) * (binblockread(myScope,'int8')))' - str2double(yOffset)*str2double(verticalScale);
        mean_data(:,i) = data(:);
    elseif ch2_enable
        fprintf(myScope, 'DATa:SOUrce CH2');
        fprintf(myScope, 'CURVE?');
        data = (str2double(verticalScale_2) * (binblockread(myScope,'int8')))' - str2double(yOffset2)*str2double(verticalScale_2);
        mean_data(:,i) = data(:);
    end
    flushinput(myScope);
end

t2 = datetime('now');

disp(between(t2,t1));

% Saving the acquired data
wave_data(:,1) = time(:);

if ch1_enable
    for i=1:num_wave
    wave_data(:,2) = wave_data(:,2) + mean_data(:,i)*(1/num_wave);
    end
end

if ch2_enable
    for i=1:num_wave
    wave_data(:,3) = wave_data(:,2) + mean_data(:,i)*(1/num_wave);
    end
end
% Clean up Close the connection
fclose(myScope);
% Clear the variable
clear myScope;
end
