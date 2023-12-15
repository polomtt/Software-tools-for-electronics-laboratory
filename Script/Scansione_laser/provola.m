
global h_Ctrl;
 h_Ctrl = actxcontrol('MG17SYSTEM.MG17SystemCtrl.1', [0 0 100 100], fig);
[temp, num_motor] = h_Ctrl.GetNumHWUnits(6, 0);
    %controllo numero motori
    if num_motor ~= 2  
        fprintf(['Check number of motors (Found' num2str(num_motor) ')!\n']);
        return
    end

    % Ottengo il numero seriale del primo (index 0) e del secondo dispositivo (index1)
    [temp, SN_motor{1}] = h_Ctrl.GetHWSerialNum(6, 0, 0); 
    [temp, SN_motor{2}] = h_Ctrl.GetHWSerialNum(6, 1, 0); 
    SN_motor

    
        Current_X = ud.h_motor_Left.GetPosition_Position(0)
        Current_Y = ud.h_motor_Right.GetPosition_Position(0)