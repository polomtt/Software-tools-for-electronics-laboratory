function configure_oscilloscope(obj)
    myScope = oscilloscope();
    %availableResources = resources(myScope);

    % Connect to oscilloscope
    myScope.Resource = 'TCPIP0::10.196.31.122::inst0::INSTR';
    connect(myScope);
    %autoSetup(myScope);
    
    time_division = 100e-6;

    % Set the acquisition time to 0.01 second. 
    myScope.AcquisitionTime = time_division*10;
    
    % Set the acquisition to collect 2000 data points. 
    myScope.WaveformLength = 10000;
    
    % Set the trigger mode to normal. 
    myScope.TriggerMode = 'normal';
    myScope.TriggerSource = 'CH1';
    
    % Set the trigger level to 0.1 volt. 
    myScope.TriggerLevel = 0.05;
    
    % Enable channel 1. 
    enableChannel(myScope,'CH1');
    enableChannel(myScope,'CH2');

    % Set the vertical coupling to AC. 
    configureChannel(myScope,'CH1','VerticalCoupling','DC');
    configureChannel(myScope,'CH2','VerticalCoupling','DC');
         
    % Set the vertical range to 5.0. 
    configureChannel(myScope,'CH1','VerticalRange',0.1);
    configureChannel(myScope,'CH2','VerticalRange',0.1);
    obj.myScope = myScope;

end