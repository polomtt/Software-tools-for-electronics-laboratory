function [waveformArray_new,t]= get_wave2_g(deviceObj,filenamedafault, time_scale)

    recordLength = 100000; %Can be: 1k, 10k, 100k, 1000k, 1M, 5M
    waveformArray = zeros(1, recordLength);

    % Connect device object to hardware.
    connect(deviceObj);

    %configura acquisizione
    groupObj = get(deviceObj, 'Configurationacquisition');
    groupObj = groupObj(1);
    %INVOKE(OBJ,'configureacquisitionrecord',TIMEPERRECORDSECONDS,MINIMUMRECORDLENGTH,ACQUISITIONSTARTTIMESECOND)
    invoke(groupObj, 'configureacquisitionrecord', time_scale ,100000,0); %scelgo 10k sample e una scala temporale di 2e-5 (1/Msampe/s)

    %time_scale=10e-3;  imposto scala temporale a time_scale/10 per tacca
    set(deviceObj.Acquisition(1), 'Horizontal_Time_Per_Record', (time_scale)); 

    pause(1);

    %in sample mode --> 'samplemode'
    groupObj = get(deviceObj, 'Configurationacquisition');
    groupObj = groupObj(1);
    invoke(groupObj, 'samplemode');

    pause(1);

    %Acquisition in average mode --> 
    groupObj = get(deviceObj, 'Configurationacquisition');
    groupObj = groupObj(1);
    invoke(groupObj, 'configureacquisitiontype', 4.0); %%set AVERAGE type of acquisition
    set(deviceObj.Acquisition(1), 'Number_Of_Averages', 256.0); %%set 128 number of averages
    
    pause(1);

    %inizializza acquisizione
    groupObj = get(deviceObj, 'Waveformacquisitionlowlevelacquisition');
    groupObj = groupObj(1);
    invoke(groupObj, 'initiateacquisition')

    %fino a quando non arriva nulla stai buono 
    a=0;
    
    while (a==0)
        groupObj = get(deviceObj, 'Waveformacquisitionlowlevelacquisition');
        groupObj = groupObj(1);
        [a] = invoke(groupObj, 'acquisitionstatus');
    end

    % Execute device object function(s).
    groupObj = get(deviceObj, 'Waveformacquisition');
    groupObj = groupObj(1);
    % Pre-allocate buffer to store the data read from scope.
    invoke(groupObj, 'configurewfmbuffersize', recordLength);

    %configuro scala voltaggi
    groupObj = get(deviceObj, 'Configurationmeasurement');
    groupObj = groupObj(1);
    %INVOKE(OBJ,'configurereflevels',LOWREFPERCENTAGE,MIDREFPERCENTAGE,HIGHREFPERCENTAGE)
    invoke(groupObj, 'configurereflevels', 0,50,100);

    ACTUALPOINTS=0;
    INITIALX=0;
    XINCREMENT=0;

    %acquisisce tutto 
    groupObj = get(deviceObj, 'Waveformacquisitionlowlevelacquisition');
    groupObj = groupObj(1);
    %waveformArray= invoke(groupObj, 'fetchwaveform', 'Ch1',recordLength, waveformArray);
    [waveformArray,ACTUALPOINTS,INITIALX,XINCREMENT]=invoke(groupObj, 'fetchwaveform', 'Ch1',recordLength, waveformArray); 

    %back in sample mode --> 'samplemode'
    groupObj = get(deviceObj, 'Configurationacquisition');
    groupObj = groupObj(1);
    invoke(groupObj, 'samplemode');

    xlin = linspace(INITIALX,(INITIALX+(ACTUALPOINTS*XINCREMENT)),ACTUALPOINTS); 
    xlin= xlin*XINCREMENT;

    t=xlin;
    numero_elementi=ACTUALPOINTS;

    waveformArray_new=waveformArray;

    %calcolo integrale forma d'onda
    figure(1);
    plot(t,waveformArray_new);
    save2(t, waveformArray_new, filenamedafault,'n')

disconnect(deviceObj); % disconnettiamo l'oggetto passato, se no da errore 

