function APTrelease(control,Xmotor,Ymotor,APTfig)
fprintf('Releasing Control...\n')
% Releasing control of X-axis motor
Xmotor.StopCtrl;
Xmotor.delete;
% Releasing control of Y-axis motor
Ymotor.StopCtrl;
Ymotor.delete;
% Releasing main control
control.StopCtrl;
control.delete;
fprintf('APT interface correctly closed.\n');
close(APTfig);

end