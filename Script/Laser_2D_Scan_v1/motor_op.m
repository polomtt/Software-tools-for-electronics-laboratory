% motor_op - provides basic control of a single Thorlabs motor stage.
%
% Matthew Hasselfield - Nov. 26, 2008
%
% Brief usage:
%   Initialization:
%       h = motor_op(0, 'init');
%
%   Motion:
%       motor_op(h, 'goto', 5.4);
%       motor_op(h, 'goto_wait', 5.4);  %Careful, this times out...
%       motor_op(h, 'stop');
%       current_pos = motor_op(h, 'pos');
%      
%   Velocity and acceleration control:
%       max_vel = motor_op(h, 'get_vel');
%       motor_op(h, 'set_vel', new_max_vel);
%       accel = motor_op(h, 'get_accel');
%       motor_op(h, 'set_accel', new_accel);
%
% Notes:
%   You must initialize the motor before using it.  The 'init'
%   function returns a 'handle' that you must pass as the first
%   argument in all subsequent commands.  The handle is actually a
%   structure that contains a few useful fields:
%      h.stage    the activeX object for the Thorlabs control top-level.
%      h.ctrl     the activeX object for the stage we're controlling.
%      h.figure   the handle of the hidden figure where our controls live.
%

function output = motor_op(handle, cmd, varargin)

    n_argin = size(varargin,2);
    if (~strcmp(cmd,'init'))
        c = handle.ctrl;
        h = handle.stage;
        f = handle.figure;
    end
    
    motor_id = 0;
    switch(cmd)
        case 'init'
            % Create controls on a hidden window
            clear handle;
            handle.figure = figure;
            f = handle.figure;
            set(f, 'Visible', 'off');
            set(f, 'NextPlot', 'new');

            % Start system
            c = actxcontrol('MG17SYSTEM.MG17SystemCtrl.1', [0 0 100 100]);
            handle.ctrl = c;
            c.StartCtrl;
            [a,n_motor] = c.GetNumHWUnits(6, 0); %%Get number of USB_STEPPER_DRIVEs (6 stays for the stepper motor controllers), 
%
%System Control Enumeration MG17_HW_TYPES 
%This enumeration contains constants that specify the type of hardware unit.
%Constant	Name	Purpose
%6	USB_STEPPER_DRIVE	Identifies a USB standalone stepper motor controller
%7	USB_PIEZO_DRIVE	Identifies a USB standalone piezo controller
%8	USB_NANOTRAK	Identifies a USB standalone NanoTrak controller
% 
if n_motor ~= 1
                disp('Wrong number of motors found...');
                close(f)
                output = -1;
            end
            [a, serial_number] = c.GetHWSerialNum(6, 0, 0); %% 6 - HW unit, 0,0 - are initial values of a and serial_number 

%GetHWSerialNum(lHWType, lIndex, plSerialNum)
%lHWType - the type of hardware unit
%lIndex - the index number specifying the hardware unit
%plSerialNum - the returned serial number of the hardware unit
            
            % Start motor
            handle.stage = actxcontrol('MGMOTOR.MGMotorCtrl.1',[0,0,300,300]);
            h = handle.stage;
            h.HWSerialNum = serial_number;
            h.StartCtrl;
            output = handle;
            
        case 'pos'
            output = h.GetPosition_Position(motor_id);
%Certain development environments, e.g. MatLab, can only support returns by value. 
%This method acts as a wrapper for the GetPosition method, and returns the
%position parameter value that is returned by reference in the GetPosition method
%
% GetPosition_Position(lChanID As Long) As Float          
%
        case 'goto_wait'
            h.SetAbsMovePos(motor_id, varargin{1});
            output = h.MoveAbsolute(motor_id, true);
            
        case 'goto'
            h.SetAbsMovePos(motor_id, varargin{1});
            output = h.MoveAbsolute(motor_id, false);
            
        case 'stop'
            % Please somebody fix this...
            motor_op(handle,'goto',motor_op(handle,'pos',0));
            
        case 'get_vel'
            [status, min_v, accel, max_v] = h.GetVelParams(motor_id, 0,0,0);
            output = max_v;
            
        case 'set_vel'
            [status, min_v, accel, max_v] = h.GetVelParams(motor_id, 0,0,0);
            if n_argin > 1
                min_v = varargin{2};
            end
            output = h.SetVelParams(motor_id, min_v, accel, varargin{1});

        case 'get_accel'
            [status, min_v, accel, max_v] = h.GetVelParams(motor_id, 0,0,0);
            output = accel;
            
        case 'set_accel'
            [status, min_v, accel, max_v] = h.GetVelParams(motor_id, 0,0,0);
            output = h.SetVelParams(motor_id, min_v, varargin{1}, max_v);

        case 'wait_free'
            while abs(motor_op(handle,'pos',0) - varargin{1}) < varargin{2}
                pause(0.1);
            end
            output = motor_op(handle,'pos',0);

        case 'cleanup'
            close(f);
            output = 0;
            
        otherwise
            disp([ 'unknown command ' cmd ]);
            output = -1;
            
    end

end
