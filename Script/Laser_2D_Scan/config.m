%  _____                             _____             __ _       
% |  __ \                           / ____|           / _(_)      
% | |__) |_ _ _ __ __ _ _ __ ___   | |     ___  _ __ | |_ _  __ _ 
% |  ___/ _` | '__/ _` | '_ ` _ \  | |    / _ \| '_ \|  _| |/ _` |
% | |  | (_| | | | (_| | | | | | | | |___| (_) | | | | | | | (_| |
% |_|   \__,_|_|  \__,_|_| |_| |_|  \_____\___/|_| |_|_| |_|\__, |
%                                                            __/ |
%                                                           |___/

% Flag -> true = plot raw data
% Flag -> false = don't plot data
PlotFlag = false;                                                           % If you want to plot the obtained waves choose true, otherwise, if you want only
                                                                            % the data, write false
OSCI_ID = 'TCPIP0::10.196.30.225::inst0::INSTR';                            % Oscilloscope IP address
ch1_enable = true;
ch2_enable = false;
%numero medie acquisione in AVG mode
num_wave_mean = 4;

%  _   _            _                _        _   _                  _   _     
% | | | | ___  _ __(_)_______  _ __ | |_ __ _| | | | ___ _ __   __ _| |_| |__  
% | |_| |/ _ \| '__| |_  / _ \| '_ \| __/ _` | | | |/ _ \ '_ \ / _` | __| '_ \ 
% |  _  | (_) | |  | |/ / (_) | | | | || (_| | | | |  __/ | | | (_| | |_| | | |
% |_| |_|\___/|_|  |_/___\___/|_| |_|\__\__,_|_| |_|\___|_| |_|\__, |\__|_| |_|
%                                                              |___/           

% Sample horizontal length to sweep [mm]
hor_length = 50*1e-3;  
% X-Motor step size [mm]
hor_Step_Size = 1*1e-2; 

% __     __        _   _           _   _                  _   _     
% \ \   / /__ _ __| |_(_) ___ __ _| | | | ___ _ __   __ _| |_| |__  
%  \ \ / / _ \ '__| __| |/ __/ _` | | | |/ _ \ '_ \ / _` | __| '_ \ 
%   \ V /  __/ |  | |_| | (_| (_| | | | |  __/ | | | (_| | |_| | | |
%    \_/ \___|_|   \__|_|\___\__,_|_| |_|\___|_| |_|\__, |\__|_| |_|
%                                                   |___/           

% Sample lateral lenght to sweep [mm]
lat_length = 30*1e-3; 
% Y-Motor step size [mm]                                                    
lat_Step_Size = 1*1e-2;                                                     

%  ____                  
% / ___|  __ ___   _____ 
% \___ \ / _` \ \ / / _ \
%  ___) | (_| |\ V /  __/
% |____/ \__,_| \_/ \___|
                       
folder_name = "3d_detector";

