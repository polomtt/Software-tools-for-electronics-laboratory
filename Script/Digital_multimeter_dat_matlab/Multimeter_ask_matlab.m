
%{
  _____  __  __ __  __ 
 |  __ \|  \/  |  \/  |
 | |  | | \  / | \  / |
 | |  | | |\/| | |\/| |
 | |__| | |  | | |  | |
 |_____/|_|  |_|_|  |_|
                                                                                                                                                                                 
%}
close all
%Setting parameter

folder_name = 'Data';
sample = "_sp1";
time_acquisition = 300; % [s]
time_step = 1;        % [s]
xlab_name="Time [s]";
ylab_name="Current [A]";
Qty_to_meas= 'MEAS:RES?';
% Qty_to_meas=':MEAS:VOLT?';
%Qty_to_meas= ':MEAS:CURR?';

acquire_mode = true;   % if you need to check the code without instrument -> false

%Create stop button
breakLoopFigure = figure('color','w','Name','Plotter');
breakLoopFigure.Position = [612 200 640 480];
breakLoopFigure.Visible = "on";
breakLoopFigure.Units = "normalized";
ButtonHandle = uicontrol('Style', 'PushButton','String', 'Stop loop','Callback', 'delete(gcbf)');
ButtonHandle.Units = "normalized";
ButtonHandle.Position = [.85 .30 .10 .5];
drawnow

%Open file for data saving
[status, msg, msgID] = mkdir(folder_name);
disp(msg)
datetime.setDefaultFormats('default','yyyyMMdd_HHmmss');
time_str = string(datetime("now"));
filename = strcat(folder_name,"\",time_str,"_",sample,".txt");
fileID = fopen(filename,'w');
fprintf(fileID,'time[s],power[W]\n');
timer = 0;

title_fig = strcat(time_str,"_",sample);
title_fig = strrep(title_fig,"_"," ");


% SERVE PER CAPIRE l'indirizzo USB corretto, va commentato quadno si ha
% l'indirizzo, perchè altrimenti si incasina tutto, non so il perchè
% visaInfo = instrhwinfo('visa', 'ni');
% disp(visaInfo.ObjectConstructorName);


if acquire_mode
    % Crea l'oggetto VISA per lo strumento USB
    obj1 = visa('ni','USB0::0x0957::0x0A07::MY46000931::INSTR');
    % Apre la connessione
    fopen(obj1);
end

%Data acquisition loop
time_serie = [];
qty_series = [];

k=1;
while true && timer<time_acquisition
    if acquire_mode
        DMM_meas = query(obj1,Qty_to_meas,'%s','%s');
    else
        DMM_meas = string(rand);
    end
    fprintf(fileID,'%2.2f,%s\n',timer,DMM_meas);
    fprintf('%.2f,%s\n',timer,DMM_meas);
    timer=timer+time_step;

    time_serie(k,1) = timer;
    qty_series(k,1) = str2double(DMM_meas);
    k=k+1;
    pause(time_step);
    plot_graph(time_serie,qty_series,0.7,title_fig,xlab_name,ylab_name,0);

    if ~ishandle(ButtonHandle)
        disp('Loop stopped by user');
        break;
    end
end

fclose(fileID);

if acquire_mode
    fclose(obj1);
    delete(obj1);
end

[mean_qty,std_dev_qty] = calc_mean(qty_series);

fprintf('%.2e +- %.2e \n',mean_qty,std_dev_qty);

%Print and save the figure
fig = figure();
plot_graph(time_serie,qty_series,0.85,title_fig,xlab_name,ylab_name,mean_qty);
filename_fig = strcat(folder_name,"\",time_str,"_",sample,".png");
disp(filename_fig);
saveas(fig,filename_fig)

disp("__          __  _ _       _                  _ ")
disp("\ \        / / | | |     | |                | |")
disp(" \ \  /\  / /__| | |   __| | ___  _ __   ___| |")
disp("  \ \/  \/ / _ \ | |  / _` |/ _ \| '_ \ / _ \ |")
disp("   \  /\  /  __/ | | | (_| | (_) | | | |  __/_|")
disp("    \/  \/ \___|_|_|  \__,_|\___/|_| |_|\___(_)")
                                                
