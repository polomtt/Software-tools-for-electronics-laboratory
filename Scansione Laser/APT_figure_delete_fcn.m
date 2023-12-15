function APT_figure_delete_fcn(ud)
%% Identification
% David Krause
% Queen's University
% October 18, 2006
% Clean up that APT window

%% Get the UserData
%ud = get(gcbo, 'UserData');
%ud = ud_handle;
%% Clean up the objects
% Clean up the motors
try
    ud.h_motor_Left.StopCtrl;
    ud.h_motor_Left.delete;
    ud.h_motor_Right.StopCtrl;
    ud.h_motor_Right.delete;
catch
    fprintf('Tried to close and delete motor controls, problem!\n');
end



% Clean up the main control
try
    ud.h_Ctrl.StopCtrl;
    ud.h_Ctrl.delete
catch
    fprintf('Tried to close the main APT control, problem!\n');
end

fprintf('APT Interface Closed.\n');