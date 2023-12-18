obj_osci = class_oscilloscope();
obj_osci.configure_oscilloscope();
disp(obj_osci.myScope)

hold on
for i = 1:10
    acq_wave(obj_osci);
    pause(0.1);
end
legend();
%xlabel('Samples');
%ylabel('Voltage');
obj_osci.close_connection_oscilloscope();
