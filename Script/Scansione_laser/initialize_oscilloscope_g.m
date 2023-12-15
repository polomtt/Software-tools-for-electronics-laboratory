function [handle_oscilloscope] = initialize_oscilloscope_g

    interfaceObj = instrfind('Type', 'visa-tcpip', 'RsrcName', 'TCPIP0::10.196.31.122::inst0::INSTR', 'Tag', '');

    % controllo all'avvio dell'oggetto connesso all'oscilloscopio (codice commentabile)
    % Create the VISA-TCPIP object if it does not exist
    % otherwise use the object that was found.

    if isempty(interfaceObj)
        interfaceObj = visa('NI', 'TCPIP0::10.196.31.122::inst0::INSTR');
        else
        fclose(interfaceObj);
        interfaceObj = interfaceObj(1);
    end

    % crea l'oggetto relativo allo stumento colleato 
    deviceObj = icdevice('tkdpo4k.mdd', 'TCPIP0::10.196.31.54::inst0::INSTR');

    % connette l'oggetto allo strumento
    connect(deviceObj);
    
    %reset per evitare che vecchie impostazioni ci diano fastidio
    devicereset(deviceObj); 

    %inizio la configurazione dei canali dell'oscilloscopio
    groupObj = get(deviceObj, 'Configurationchannel');
    groupObj = groupObj(1);

    %Vengono inizializzati i canali dell'oscilloscopio, indicando la scala
    %delle ampiezze (con offset), il tipo di coupling, l'attenuazione della
    %sonda. L'ultimo campo indica se il canale va attivato(1) oppure no.

    % Set all the main properties for Ch1 (acquisizione dati)
    invoke(groupObj, 'configurechannel', 'Ch1',20,6,0,1,1); %(20=2V )vertical range, vertical offset, coupling(0:ac 1:dc 2:gnd), probe attenuation, and channel enabled.

    % Set all the main properties for Ch2 (trigger)
    invoke(groupObj, 'configurechannel', 'Ch2',20,0,0,1,1); %(20=2V, allora 1=100mV )vertical range, vertical offset, coupling(0:ac 1:dc 2:gnd), probe attenuation, and channel enabled.

    % Set all the main properties for Ch3 (reference laser)
    invoke(groupObj, 'configurechannel', 'Ch3',0.1,0.02,0,1,1); %(20=2V )vertical range, vertical offset, coupling(0:ac 1:dc 2:gnd), probe attenuation, and channel enabled.

    %set input impedance
    %INVOKE(OBJ,'configurechancharacteristics',CHANNELNAME,INPUTIMPEDANCEOHMS,MAXIMUMINPUTFREQUENCYHERTZ)
    invoke(groupObj,'configurechancharacteristics','Ch1',1000000,300e6 )
    invoke(groupObj,'configurechancharacteristics','Ch3',50,300e6 )

    % Set trigger
    % Connect device object to hardware.
    groupObj = get(deviceObj, 'Configurationtriggeredgetriggergroupedgetrigger');
    groupObj = groupObj(1);
    
    %viene configurato il trigger, indicando canale, livello(in V) e tipo (1 indica il fronte di salita)
    invoke(groupObj, 'configureedgetriggersource', 'Ch2',2,1); %(canale livello tipo)

    %viene ritornato l'oggetto creato
    handle_oscilloscope = deviceObj; 

disconnect(deviceObj); % disconnettiamo l'oggetto creato
