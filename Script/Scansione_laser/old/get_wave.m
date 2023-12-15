function [area_a, massimo,massimo2,waveformArray_new]= get_wave(deviceObj,filenamedafault, time_scale,wave)

recordLength = 100000; %Can be: 1k, 10k, 100k, 1000k, 1M, 5M
waveformArray = zeros(1, recordLength); %  Ch1
waveformArray2 = zeros(1, recordLength); % Ch3

% Connect device object to hardware.
connect(deviceObj);
%devicereset(deviceObj);


%configura acquisizione
groupObj = get(deviceObj, 'Configurationacquisition');
groupObj = groupObj(1);
invoke(groupObj, 'configureacquisitionrecord', time_scale ,100000,0); %scelgo 10k sample e una scala temporale di 2e-5 (1/Msampe/s)
%INVOKE(OBJ,'configureacquisitionrecord',TIMEPERRECORDSECONDS,MINIMUMRECORDLENGTH,ACQUISITIONSTARTTIMESECOND)


%time_scale=10e-3;  imposto scala temporale a time_scale/10 per tacca
set(deviceObj.Acquisition(1), 'Horizontal_Time_Per_Record', (time_scale)); 

%%pause(0.3);

%  in sample mode --> 'samplemode'
    groupObj = get(deviceObj, 'Configurationacquisition');
    groupObj = groupObj(1);
    invoke(groupObj, 'samplemode');
    
pause(0.5);
    
%Acquisition in average mode --> 
groupObj = get(deviceObj, 'Configurationacquisition');
groupObj = groupObj(1);
invoke(groupObj, 'configureacquisitiontype', 4.0); %% set AVERAGE type of acquisition
set(deviceObj.Acquisition(1), 'Number_Of_Averages', 256.0); %%set 128 number of averages
%pause(0.1);


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
invoke(groupObj, 'configurewfmbuffersize', recordLength);
% Pre-allocate buffer to store the data read from scope.
 

%configuro scala voltaggi
groupObj = get(deviceObj, 'Configurationmeasurement');
groupObj = groupObj(1);
invoke(groupObj, 'configurereflevels', 0,50,100);
% INVOKE(OBJ,'configurereflevels',LOWREFPERCENTAGE,MIDREFPERCENTAGE,HIGHREFPERCENTAGE)
 
 

ACTUALPOINTS=0;
INITIALX=0;
XINCREMENT=0;

ACTUALPOINTS2=0;
INITIALX2=0;
XINCREMENT2=0;



 %acquisisce tutto 
 groupObj = get(deviceObj, 'Waveformacquisitionlowlevelacquisition');
 groupObj = groupObj(1);
 %waveformArray= invoke(groupObj, 'fetchwaveform', 'Ch1',recordLength, waveformArray);
 [waveformArray,ACTUALPOINTS,INITIALX,XINCREMENT]=invoke(groupObj, 'fetchwaveform', 'Ch1',recordLength, waveformArray);
 %waveformArray= invoke(groupObj, 'fetchwaveform', 'Ch3',recordLength, waveformArray2);
 [waveformArray2,ACTUALPOINTS2,INITIALX2,XINCREMENT2]=invoke(groupObj, 'fetchwaveform', 'Ch3',recordLength, waveformArray2);
 
 
ACTUALPOINTS;
INITIALX;
XINCREMENT;

 
 % back in sample mode --> 'samplemode'
    groupObj = get(deviceObj, 'Configurationacquisition');
    groupObj = groupObj(1);
    invoke(groupObj, 'samplemode');


    
    xlin = linspace(INITIALX,(INITIALX+(ACTUALPOINTS*XINCREMENT)),ACTUALPOINTS); 

    
 
 xlin=xlin*XINCREMENT;
 
 
 
t=xlin;
numero_elementi=ACTUALPOINTS;


    waveformArray_new=waveformArray;
    waveformArray2_new=waveformArray2;

 
  waveformArray_new=waveformArray_new-wave;
 
%calcolo integrale forma d'onda
area_a= integrale_area(t,abs(waveformArray_new));
massimo = max(abs (waveformArray_new)) ;
massimo2 = max(abs (waveformArray2_new));
 %area_a=waveformArray;
%figure(1);
%plot(t,waveformArray_new)
%figure(3);
%plot(t,wave);
save2(t, waveformArray_new, filenamedafault,'n')

disconnect(deviceObj); % disconnettiamo l'oggetto passato, se no da errore 


