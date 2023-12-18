classdef class_oscilloscope < handle
    %UNTITLED2 Summary of this class goes here
    %   Detailed explanation goes here

    properties
        trigger
        myScope
        waveformArray
    end

    methods
   
    acq_wave(obj);
    configure_oscilloscope(obj);
    close_connection_oscilloscope(obj);

    end
end