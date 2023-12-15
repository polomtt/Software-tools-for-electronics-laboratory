function [waveformArray_new]= get_wave_ref(deviceObj, time_scale)

recordLength = 100000; %Can be: 1k, 10k, 100k, 1000k, 1M, 5M
waveformArray = zeros(1, recordLength);

% Connect device object to hardware.
connect(deviceObj);
%devicereset(deviceObj);


%configura acquisizione
groupObj = get(deviceObj, 'Configurationacquisition');
groupObj = groupObj(1);
invoke(groupObj, 'configureacquisitionrecord', time_scale ,100000,0); %scelgo 10k sample e una scala temporale di 2e-5 (1/Msampe/s)
%INVOKE(OBJ,'configureacquisitionrecord',TIMEPERRECORDSECONDS,MINIMUMRECORDLENGTH,ACQUISITIONSTARTTIMESECOND)


set(deviceObj.Acquisition(1), 'Horizontal_Time_Per_Record', (time_scale)); 


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
 
 
 %acquisisce tutto 
 groupObj = get(deviceObj, 'Waveformacquisitionlowlevelacquisition');
 groupObj = groupObj(1);
 [waveformArray,ACTUALPOINTS,INITIALX,XINCREMENT]= invoke(groupObj, 'fetchwaveform', 'REF1',recordLength, waveformArray);
 
 
 
 index_first_elemento=abs(round(INITIALX/XINCREMENT));
index_last_elemento=index_first_elemento+abs(round((time_scale*5)/XINCREMENT));
numero_elementi=index_last_elemento-index_first_elemento;

index_first_elemento=round(abs(INITIALX/XINCREMENT)-0.05*numero_elementi);
numero_elementi=index_last_elemento-index_first_elemento;
% waveformArray=waveformArray-wave;


    %creazione scala temporale
    t=zeros(1,numero_elementi);
    for i=1:numero_elementi
         t(1,i)=i*XINCREMENT;
    end
    
waveformArray_new = zeros(1,numero_elementi);
 for i=1:numero_elementi
         waveformArray_new(1,i)=waveformArray(1,i+index_first_elemento);
 end


 
 
 
 
 
 
 plot (t,waveformArray_new);
 

disconnect(deviceObj); % disconnettiamo l'oggetto passato, se no da errore 


