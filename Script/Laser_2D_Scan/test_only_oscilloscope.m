%% Initialization
clc;
clearvars;
close all;

% Flag -> true = plot raw data
% Flag -> false = don't plot data
PlotFlag = false;                                                           % If you want to plot the obtained waves choose true, otherwise, if you want only
                                                                            % the data, write false

OSCI_ID = 'TCPIP0::10.196.30.225::inst0::INSTR';                            % Oscilloscope IP address
ch1_enable = true;
ch2_enable = true;


noise = OscilloAcquisition(OSCI_ID, ch1_enable, ch2_enable, 5);

PlotWaves(noise(:,1),noise(:,2),'Acquired Waves CH1');
PlotWaves(noise(:,1),noise(:,3),'Acquired Waves CH2');

