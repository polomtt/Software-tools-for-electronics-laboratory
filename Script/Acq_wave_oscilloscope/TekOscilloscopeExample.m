%% MATLAB script to transfer acquired waveforms from Tektronix MSO5000 series oscilloscope 
%{
    #                                                                                                    
   # #    ####   ####      ####   ####   ####  # #      #       ####   ####   ####   ####  #####  ###### 
  #   #  #    # #    #    #    # #      #    # # #      #      #    # #      #    # #    # #    # #      
 #     # #      #    #    #    #  ####  #      # #      #      #    #  ####  #      #    # #    # #####  
 ####### #      #  # #    #    #      # #      # #      #      #    #      # #      #    # #####  #      
 #     # #    # #   #     #    # #    # #    # # #      #      #    # #    # #    # #    # #      #      
 #     #  ####   ### #     ####   ####   ####  # ###### ######  ####   ####   ####   ####  #      ###### 
%}

% Clear MATLAB workspace of any previous instrument connections
instrreset;

% Provide the Resource name of the oscilloscope - Note you will have to
% change this to match your oscilloscope.

visaAddress = 'TCPIP0::10.196.31.122::inst0::INSTR';
filename = "pad";
num_wave = 5;
ch_1_enable = true;
ch_2_enable = false;

% Create a VISA object and set the |InputBufferSize| to allow for transfer
% of waveform from oscilloscope to MATLAB. Tek VISA needs to be installed.
myScope = visa('ni', visaAddress);
myScope.InputBufferSize = 1e8;

% Set the |ByteOrder| to match the requirement of the instrument
myFgen.ByteOrder = 'littleEndian';

% Open the connection to the oscilloscope
fopen(myScope);

% Turn headers off, this makes parsing easier
fprintf(myScope, 'HEADER OFF');
fprintf(myScope, 'HORizontal:RECOrdlength 10000000');

% Get record length value
recordLength = query(myScope, 'HOR:RECO?');
disp(recordLength);
% Ensure that the start and stop values for CURVE query match the full
% record length
fprintf(myScope, ['DATA:START 1;DATA:STOP' recordLength]);



if ch_1_enable
    % Read YMULT to calculate the vertical values
    fprintf(myScope, 'DATa:SOUrce CH1');
    verticalScale  = query(myScope,'WFMOUTPRE:YMULT?');
    % Read YOFFSET to calculate the vertical values
    yOffset = query(myScope, 'WFMO:YOFF?');
end

fprintf(myScope, 'DATa:SOUrce CH2');
verticalScale_2  = query(myScope,'WFMOUTPRE:YMULT?');
disp('vertical_scale');
disp(verticalScale);
% Read YOFFSET to calculate the vertical values
yOffset2 = query(myScope, 'WFMO:YOFF?');

%time scale
hor_scale = str2double(query(myScope,'HORizontal:SCAle?'));
sample_time = (hor_scale*10)/str2double(recordLength);

time = [];

for i=1:str2double(recordLength)
    time(i)=i*sample_time;
end

t1 = datetime('now');

qq = query(myScope,'WFMOutpre:XINcr?');
disp(qq);
% Request 8 bit binary data on the CURVE query
fprintf(myScope, 'DATA:ENCDG RIBINARY;WIDTH 1');
hold on
for i=1:num_wave
    
    if ch_1_enable
        fprintf(myScope, 'DATa:SOUrce CH1');
        fprintf(myScope, 'CURVE?');
        data = (str2double(verticalScale) * (binblockread(myScope,'int8')))' - str2double(yOffset)*str2double(verticalScale);
        plot(time,data); 
    end

    if ch_2_enable
        fprintf(myScope, 'DATa:SOUrce CH2');
        fprintf(myScope, 'CURVE?');
        data2 = (str2double(verticalScale_2) * (binblockread(myScope,'int8')))' - str2double(yOffset2)*str2double(verticalScale_2);
        plot(time,data2);
    end
 
    xlabel('Sample Index'); 
    ylabel('Volts');
    title('Waveform Acquired from Tektronix Oscilloscope');
    grid on;
    
    str_file = strcat('data\',filename,num2str(i),'.txt');
    fid = fopen(str_file, 'w');
    fprintf(fid,'time,ch1,ch2\n');
    for j=1:str2double(recordLength)
        help1=0;
        help2=0;
        if ch_1_enable
            help1 = data(j);
        end
        if ch_2_enable
            help2 = data(j);
        end
        fprintf(fid,'%e,%f,%f\n',sample_time*j,help1,help2);
    end
    fclose(fid);
    flushinput(myScope);
    % clrdevice(myScope);
end

t2 = datetime('now');

disp(between(t2,t1));

% Clean up Close the connection
fclose(myScope);
% Clear the variable
clear myScope;

