%clear;
%clc;
% Create a VISA-TCPIP object.
interfaceObj = instrfind('Type', 'visa-tcpip', 'RsrcName', 'TCPIP0::10.196.30.225::inst0::INSTR', 'Tag', '');

% Create the VISA-TCPIP object if it does not exist
% otherwise use the object that was found.
if isempty(interfaceObj)
    interfaceObj = visa('NI', 'TCPIP010.196.30.225192.168.213.249::inst0::INSTR');
else
    fclose(interfaceObj);
    interfaceObj = interfaceObj(1);
end

% Create a device object. 
deviceObj = icdevice('tektronix_tds3052B.mdd', interfaceObj);

% Connect device object to hardware.
connect(deviceObj);

% Configure mode and probe value
set(deviceObj.Acquisition(1), 'Mode', 'sample');

set(deviceObj.Channel(1), 'Probe', 1.0);

% Set all the main properties for Ch1
set(deviceObj.Channel(1), 'BandwidthLimit', 'full');
set(deviceObj.Channel(1), 'Coupling', 'dc');
set(deviceObj.Channel(1), 'Position', -3.0);
set(deviceObj.Channel(1), 'Scale', 0.04);

% Set all the main properties for Ch2
set(deviceObj.Channel(2), 'BandwidthLimit', 'full');
set(deviceObj.Channel(2), 'Coupling', 'dc');
set(deviceObj.Channel(2), 'Position', 2.5);
set(deviceObj.Channel(2), 'Scale', 0.07);

% Set Timebase 
set(deviceObj.Acquisition(1), 'Timebase', 10.0E-9);

% Set trigger
set(deviceObj.Trigger(1), 'Coupling', 'dc');
set(deviceObj.Trigger(1), 'Level', 0.05);
set(deviceObj.Trigger(1), 'Mode', 'auto');
set(deviceObj.Trigger(1), 'Slope', 'rising');
set(deviceObj.Trigger(1), 'Source', 'channel1');

disconnect(deviceObj);