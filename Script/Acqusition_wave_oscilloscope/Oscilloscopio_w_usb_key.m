filename = 'E:/PIXEL_D_A1_25_45_CENTRAL_'
num_wave = 10

DPO3000.IP = '10.196.31.127' ; % to check and modify each time
DPO3000.P = tcpip(DPO3000.IP,4000); %create TCPIP object
fopen(DPO3000.P); %connect TCPIP object

for i=1:num_wave
    formatSpec = strcat('SAVE:WAVEFORM ALL,','"',filename,"_%d.csv",'"');
    str = sprintf(formatSpec,i);
    disp(str);
    fprintf(DPO3000.P,str);  
    pause(0.25);
end

