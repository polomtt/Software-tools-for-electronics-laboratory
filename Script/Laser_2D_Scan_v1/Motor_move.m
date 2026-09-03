[ud_handle]=APT_interface;



for i = 1:20
ud_handle.h_motor_Left.SetRelMoveDist(0, 0.2)
output = ud_handle.h_motor_Left.MoveRelative(0, false)
pause(1);
end

