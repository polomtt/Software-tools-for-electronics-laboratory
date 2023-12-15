function [handle_oscilloscope] = initialize_oscilloscope_Rob
interfaceObj = instrfind('Type', 'visa-tcpip', 'RsrcName', 'TCPIP0::10.196.30.226::inst0::INSTR', 'Tag', '');

% controllo all'avvio dell'oggetto connesso all'oscilloscopio (codice commentabile)
% Create the VISA-TCPIP object if it does not exist
% otherwise use the object that was found.
if isempty(interfaceObj)
    interfaceObj = visa('NI', 'TCPIP0::10.196.30.225::inst0::INSTR');
else
    fclose(interfaceObj);
    interfaceObj = interfaceObj(1);
end
%

% Create a device object. 
deviceObj = icdevice('tkdpo4k.mdd', 'TCPIP0::10.196.30.226::inst0::INSTR');

% Connect device object to hardware.
connect(deviceObj);
%reset per evitare che vecchie impostazioni ci diano fastidio
devicereset(deviceObj); 


%configuriamo oscilloscopio nella get_wave, perchè acquisiamo in average
%mode e dopo acquisizione torniamo in sample mode

% Configure mode and probe value
% %Acquisition in sample mode --> 'samplemode'
%     groupObj = get(deviceObj, 'Configurationacquisition');
%     groupObj = groupObj(1);
%     invoke(groupObj, 'samplemode');

%Acquisition in average mode --> 
% groupObj = get(deviceObj, 'Configurationacquisition');
% groupObj = groupObj(1);
% invoke(groupObj, 'configureacquisitiontype', 4.0); %%set AVERAGE type of acquisition
% set(deviceObj.Acquisition(1), 'Number_Of_Averages', 128.0); %%set 128 number of averages


%inizio la configurazione dei canali dell'oscilloscopio
groupObj = get(deviceObj, 'Configurationchannel');
groupObj = groupObj(1);

%Vengono inizializzati i canali dell'oscilloscopio, indicando la scala
%delle ampiezze (con offset), il tipo di coupling, l'attenuazione della
%sonda. L'ultimo campo indica se il canale va attivato(1) oppure no.

% Set all the main properties for Ch1 (acquisizione dati)
invoke(groupObj, 'configurechannel', 'Ch1',1,0.25,0,1,1); %(20=2V )vertical range, vertical offset, coupling(0:ac 1:dc 2:gnd), probe attenuation, and channel enabled.

% Set all the main properties for Ch2 (trigger)
invoke(groupObj, 'configurechannel', 'Ch2',20,0,0,1,1); %(20=2V, allora 1=100mV )vertical range, vertical offset, coupling(0:ac 1:dc 2:gnd), probe attenuation, and channel enabled.

% Set all the main properties for Ch3 (reference laser)
invoke(groupObj, 'configurechannel', 'Ch3',0.1,0.02,0,1,1); %(20=2V )vertical range, vertical offset, coupling(0:ac 1:dc 2:gnd), probe attenuation, and channel enabled.

%set input impedance
%INVOKE(OBJ,'configurechancharacteristics',CHANNELNAME,INPUTIMPEDANCEOHMS,MAXIMUMINPUTFREQUENCYHERTZ)
invoke(groupObj,'configurechancharacteristics','Ch1',50,300e6 )
%invoke(groupObj,'configurechancharacteristics','Ch2',50,300e6 )
invoke(groupObj,'configurechancharacteristics','Ch3',50,300e6 )

% Set trigger
% Connect device object to hardware.
groupObj = get(deviceObj, 'Configurationtriggeredgetriggergroupedgetrigger');
groupObj = groupObj(1);
%viene configurato il trigger, indicando canale, livello(in V) e tipo (1 indica il fronte di salita)
invoke(groupObj, 'configureedgetriggersource', 'Ch2',2,1); %(canale livello tipo)


% groupObj = get(deviceObj, 'Configurationmathchannels');
% groupObj = groupObj(1);
% invoke(groupObj, 'enablemathchannel', 1);
% 
% % groupObj = get(deviceObj, 'Configurationmathchannels');
% % groupObj = groupObj(1);
% % invoke(groupObj, 'configuremathchanneladvanced', 10, 4,(1-4));
% 
% groupObj = get(deviceObj, 'Configurationmathchannels');
% groupObj = groupObj(1);
% invoke(groupObj, 'configuremathchanneladvanced', 0,0,'ch1-REF1');


% groupObj = get(deviceObj, 'Configurationreferencechannels');
% groupObj = groupObj(1);
% invoke(groupObj, 'enablereferencechannel', 'REF1',1);


handle_oscilloscope = deviceObj; %viene ritornato l'oggetto creato

disconnect(deviceObj); % disconnettiamo l'oggetto creato
