function PlotWaves(time_vec,waves_vec,PlotName)

[~,n] = size(waves_vec);

figure('Name',PlotName)
hold on;
grid on;
for i=1:n
    plot(time_vec(:),waves_vec(:,i))
end
xlabel('Sample Index');
ylabel('Volts');
title('Waveforms Acquired from Tektronix Oscilloscope');
end