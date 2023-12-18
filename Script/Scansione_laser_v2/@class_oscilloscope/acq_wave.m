function acq_wave(obj)
    [w1, w2] = readWaveform(obj.myScope, 'acquisition', true);
    plot(w1);
    plot(w2);
end