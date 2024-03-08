%% Initialization
clc;
clearvars;
close all;

global h;
global h_motor_Left;
global h_motor_Right;

PlotFlag = false;                                                           % If you want to plot the obtained waves choose true, otherwise, if you want only
                                                                            % the data, write false

OSCI_ID = 'TCPIP0::10.196.30.225::inst0::INSTR';                            % Oscilloscope IP address
ch1_enable = true;
ch2_enable = false;

% Setting sample dimensions and motor step size
hor_length = 50*1e-3;                                                       % Sample horizontal length to sweep [mm]
lat_length = 30*1e-3;                                                       % Sample lateral lenght to sweep [mm]
Step_Size = 1e-2;                                                           % Motor step size [mm]
% Safety Check for incorrect step size or sample lengths values
if hor_length / Step_Size < 1
    fprintf('Warning! Incorrect step size selected.\n');
    return;
elseif lat_length / Step_Size < 1
    fprintf('Warning! Incorrect step size selected.\n');
    return;
end

ParamSet = 'CONF_Z812B_slow';                                               % Motor speed settings
% 'CONF_Z812B' -> normal speed
% 'CONF_Z812B_slow' -> reduced speed

%% APT configuration
% Configuring a simple APT interface for the motor control
% Create a dialog question box 
button = questdlg('About to launch the APT window - do not run if another APT window is open.  Do you want to open the APT window?', ...
                  'Launch APT window', 'Yes', 'No', 'No');
% Stop program if dialog box closed or if close has been pressed 
if isempty(button)
    fprintf('Task Aborted.\n')
    return
elseif length(button) == 2
    fprintf('Task Aborted.\n')
    return
end
fprintf('ActiveX APT launched.\n')

% APT graphic figure generation
fig = figure('Position', [0 0 600 200], 'HandleVisibility', 'on', 'IntegerHandle', 'off', ...
                'Name', 'APT Interface', 'NumberTitle', 'off');
set(fig, 'Name', ['APT Interface, Handle Number ' num2str(fig.Number, '%2.20f')]);

% Generating ActiveX control
h = actxcontrol('MG17SYSTEM.MG17SystemCtrl.1', [0 0 100 100], fig);

% Start Control
h.StartCtrl;
%% Motor configuration
% Checking if both motors has been connected
fprintf('Checking number of connected motors...\n');
[~, num_motor] = h.GetNumHWUnits(6, 0);
if num_motor ~= 2  
    fprintf(['Warning! Found ' num2str(num_motor) ' motors connected instead of 2!\n']);
    fprintf('Programm stopped.\n');
    close all;
    return
else
    fprintf('Both motors connected.\n');
end

% Get motors serial numbers (index 0 -> left motor, index 1 -> right motor)
[~, SN_motor(1)] = h.GetHWSerialNum(6, 0, 0); 
[~, SN_motor(2)] = h.GetHWSerialNum(6, 1, 0); 

% Create Motors ActiveX interface
h_motor_Left = actxcontrol('MGMOTOR.MGMotorCtrl.1', [0 0 300 200], fig);
h_motor_Right = actxcontrol('MGMOTOR.MGMotorCtrl.1', [300 0 300 200], fig);

% Configure Motors serial numbers and parameters
SetMotor(h_motor_Left, SN_motor(1), ParamSet);
SetMotor(h_motor_Right, SN_motor(2), ParamSet);

%% Noise Acquisition
% Extracting noise of the oscilloscope by performing a measurement without
% the laser on
button = questdlg('About to extract oscilloscope noise, please make sure that the Laser is turned off during the operation. Proceeding?', ...
                  'Oscilloscope Noise Extraction', 'Yes', 'No', 'No');
% Stop program if dialog box closed or if close has been pressed 
if isempty(button)
    fprintf('Task Aborted.\n')
    APTrelease(h,h_motor_Left,h_motor_Right,fig);
    return
elseif length(button) == 2
    fprintf('Task Aborted.\n')
    APTrelease(h,h_motor_Left,h_motor_Right,fig);
    return
end
fprintf('Extracting Noise Vector...\n');

noise = OscilloAcquisition(OSCI_ID, ch1_enable, ch2_enable, 5, 'noise_pad');

% Plotting the noise waveform
figure('Name','Noise Plot')
plot(noise(:,1),noise(:,2))
xlabel('Sample Index');
ylabel('Volts');
title('Noise Waveform Acquired from Tektronix Oscilloscope');
grid on;


pause(2);
fprintf('Noise vector extracted.\n')

%% Sweep function
% Sweep of the sample function, laser must be now turned on to perform the
% measurements.
button = questdlg('About to perform the Sweep, please make sure that the Laser is turned on during the operation. Proceeding?', ...
                  'Sweep Procedure', 'Yes', 'No', 'No');
% Stop program if dialog box closed or if close has been pressed 
if isempty(button)
    fprintf('Task Aborted.\n')
    APTrelease(h,h_motor_Left,h_motor_Right,fig);
    return
elseif length(button) == 2
    fprintf('Task Aborted.\n')
    APTrelease(h,h_motor_Left,h_motor_Right,fig);
    return
end

% Setting current Laser position as the starting point of the sweep
Start_X = h_motor_Left.GetPosition_Position(0);
Start_Y = h_motor_Right.GetPosition_Position(0);

% Obtaining the number of steps
Hor_value = ceil(hor_length/Step_Size);
Lat_value = ceil(lat_length/Step_Size);

% Sweep cycle 
fprintf(['Initial Position: X: '  num2str(Start_X) ' Y: '  num2str(Start_Y) ' -> (0,0) \n']);
pause(2);
fprintf('Performing sweep... \n')

% Initialising empty temp save vectors
ch1_tmp = zeros(Hor_value+1,length(noise))';
ch2_tmp = zeros(Hor_value+1,length(noise))';
ch1_waves = zeros(Hor_value+1,length(noise))';
ch2_waves = zeros(Hor_value+1,length(noise))';

for i = 1:Lat_value+1
    pos_Y = h_motor_Right.GetPosition_Position(0) - Start_Y;
    for j = 1:Hor_value+1
        % Make sure that both motors are still before acquiring waveform
        % (Safety check)
        wait_stop(h_motor_Left);
        wait_stop(h_motor_Right);
        pos_X = h_motor_Left.GetPosition_Position(0) - Start_X;
        fprintf(['X: ' num2str(pos_X) '  Y: ' num2str(pos_Y) '\n']);
        
        % Acquiring the signal wave
        tmp_wave = OscilloAcquisition_notxt(OSCI_ID, ch1_enable, ch2_enable, 5);
        % Processing the signal in order to obtain the mean signal later
        ch1_tmp(:,j) = tmp_wave(:,2)*(1/(Lat_value+1)) ;
        ch2_tmp(:,j) = tmp_wave(:,3)*(1/(Lat_value+1)) ;
        pause(0.1);
        
        % Moving the laser
        h_motor_Left.SetRelMoveDist(0, Step_Size);                          % Setting relative movement of motor along X-axis of one step
        h_motor_Left.MoveRelative(0, true);                                 % Performing set movement along X-axis
        pause(0.1);                                                         % Pausing to avoid jerk motion
        
    end
    
    % Generating the mean signal
    ch1_waves =  ch1_waves + ch1_tmp;                                       % Channel 1 mean wave signal, every column represent the aquired data of 1 step
    ch2_waves =  ch2_waves + ch2_tmp;                                       % Channel 2 mean wave signal, every column represent the aquired data of 1 step
    pause(0.1);
    % Make sure that both motors are still before acquiring waveform
    wait_stop(h_motor_Left);
    wait_stop(h_motor_Right);
    % Laterally move the motor by one step
    h_motor_Right.SetAbsMovePos(0, Start_Y+i*Step_Size);                    % Setting relative movement of motor along Y-axis of one step
    h_motor_Right.MoveAbsolute(0, true);                                    % Performing set movement along Y-axis
    % Waiting for Y-axis motor to be still
    wait_stop(h_motor_Right);
    % Resetting position of X-axis motor to its stargin point
    h_motor_Left.SetAbsMovePos(0, Start_X);                                 % Setting absolute X position back to its starting point
    h_motor_Left.MoveAbsolute(0, true);                                     % Performing set movement along X-axis
    % Waiting for Y-axis motor to be still
    wait_stop(h_motor_Right);
    pause(1);                                                               % Pausing to avoid jerk motion
end
fprintf('Sweep completed.\n')
% Saving on a txt the mean wave signal
for i = 1:Hor_value+1
    datetime.setDefaultFormats('default','yyyyMMdd_hhmm')
    t = datetime('now');
    filename_txt = strcat('mean_wave_pad_',num2str(i),'_',char(t));
    SaveWave(tmp_wave(:,1),ch1_waves(:,i),ch2_waves(:,i),filename_txt);
end

%% Returning to Initial Position
fprintf('Returning to initial position...\n')
% Wait for both motors to be still
wait_stop(h_motor_Left);
wait_stop(h_motor_Right);
pause(1);                                                                   % 1 second pause time for safety

% Returning motors to starting point
h_motor_Left.SetAbsMovePos(0, Start_X);                                     % Setting absolute X position back to its starting point
h_motor_Left.MoveAbsolute(0, true);
wait_stop(h_motor_Left);
h_motor_Right.SetAbsMovePos(0, Start_Y);                                    % Setting absolute Y position back to its starting point
h_motor_Right.MoveAbsolute(0, true);
wait_stop(h_motor_Right);

% Checking if we returned to the starting position correctly
pos_Y = h_motor_Right.GetPosition_Position(0) - Start_Y;
pos_X = h_motor_Left.GetPosition_Position(0) - Start_X;
if abs(pos_Y) >= 1e-4 || abs(pos_X) >= 1e-4
    fprintf('Warning! Motors not perfectly back to starting position \n')
end

%% (Optional) Plotting the acquired data
% Plotting the mean waves for each longitudinal step
if PlotFlag
    if ch1_enable
        PlotWaves(tmp_wave(:,1),ch1_waves,'Acquired Waves');
    elseif ch2_enable
        PlotWaves(tmp_wave(:,1),ch2_waves,'Acquired Waves');
    end
end

%% Maximum value extraction
button = questdlg('Do you want to extract the maximum value of each acquired waves?', ...
                  'Maximum Procedure', 'Yes', 'No', 'No');
% Stop program if dialog box closed or if close has been pressed 
if isempty(button)
    fprintf('Task Aborted.\n')
    APTrelease(h,h_motor_Left,h_motor_Right,fig);
    return
elseif length(button) == 2
    fprintf('Task Aborted.\n')
    APTrelease(h,h_motor_Left,h_motor_Right,fig);
    return
end
% Initialising empty max values vector
maximums = zeros(1,Hor_value+1)';

% Extracting values
if ch1_enable
    for i = 1:Hor_value+1
        maximums(i,1) = max(abs(ch1_waves(:,i)));
    end
elseif ch2_enable
    for i = 1:Hor_value+1
        maximums(i,1) = max(abs(ch2_waves(:,i)));
    end
end

% Plotting the maximum w.r.t position
pos = 0:Step_Size:hor_length;
figure('Name','Maximum Plot')
hold on;
grid on;
plot(pos(:),maximums(:,1),'r*');
xlabel('Relative position on sample [mm]');
ylabel('Volts');
title('Maximum data values for each step');

% Saving maximum w.r.t position on a txt file
fprintf('Saving maximum values...\n');
datetime.setDefaultFormats('default','yyyyMMdd_hhmm')
t = datetime('now');
str_file = strcat('data\','Max_pad_',char(t),'.txt');
fid = fopen(str_file, 'w');
fprintf(fid,'x,max\n');
for i=1:length(pos)
    fprintf(fid,'%e,%f\n',pos(i),maximums(i,1));
end
fclose(fid);

%% Clean up APT interface
APTrelease(h,h_motor_Left,h_motor_Right,fig);

