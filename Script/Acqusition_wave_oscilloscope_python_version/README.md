# Acquisition wave oscilloscope

Matlab program to be used for acquire waveform with Tektronic oscilloscope:

## Oscilloscopio_w_usb_key.m
+ `filename`: is the name of the output file. The file will have the structure: disk name + useful name.
    The disk name must be check from the oscilloscope.
+ `DPO3000.IP`: is the IP address of the Keithley oscilloscope instrument, to be checked each time the instrument is powered on.
+ `num_wave`: number of wave to be saved.
