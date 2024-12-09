%{
  _____                                        _            
 |  __ \                                      | |           
 | |__) |____      _____ _ __   _ __ ___   ___| |_ ___ _ __ 
 |  ___/ _ \ \ /\ / / _ \ '__| | '_ ` _ \ / _ \ __/ _ \ '__|
 | |  | (_) \ V  V /  __/ |    | | | | | |  __/ ||  __/ |   
 |_|   \___/ \_/\_/ \___|_|    |_| |_| |_|\___|\__\___|_|   
                                                                                                                                                                     
%}

%Setting parameter

folder_name = 'Data';
sample = "_sp1";
time_acquisition = 100; % [s]
time_step = 1;        % [s]
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

% Connect to instrument object
if acquire_mode
    obj1 = gpib('ni', 0, 5);
    fopen(obj1);
end

%Data acquisition loop

time_serie = [];
power_serie = [];

k=1;
while true && timer<time_acquisition
    if acquire_mode
        power_meter_meas = query(obj1,'R_A?','%s','%s');
    else
        power_meter_meas = "0";
    end
    fprintf(fileID,'%2.2f,%s\n',timer,power_meter_meas);
    fprintf('%.2f,%s\n',timer,power_meter_meas);
    timer=timer+time_step;

    time_serie(k,1) = timer;
    power_serie(k,1) = str2double(power_meter_meas);
    k=k+1;
    pause(time_step);
    plot_graph(time_serie,power_serie,0.7,title_fig);

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

%Print and save the figure
fig = figure();
plot_graph(time_serie,power_serie,0.85,title_fig)
filename_fig = strcat(folder_name,"\",time_str,"_",sample,".png");
disp(filename_fig);
saveas(fig,filename_fig)

disp("__          __  _ _       _                  _ ")
disp("\ \        / / | | |     | |                | |")
disp(" \ \  /\  / /__| | |   __| | ___  _ __   ___| |")
disp("  \ \/  \/ / _ \ | |  / _` |/ _ \| '_ \ / _ \ |")
disp("   \  /\  /  __/ | | | (_| | (_) | | | |  __/_|")
disp("    \/  \/ \___|_|_|  \__,_|\___/|_| |_|\___(_)")
                                                
