function aspettaLoStop = wait_stop(h)
timeout=10;
t1 = clock; 
while(etime(clock,t1)<timeout) 
% wait while the motor is active; timeout to avoid dead loop
    s = h.GetStatusBits_Bits(0);
    if (IsMoving(s) == 0)
      break;
    end
end