# IV Curve with Keithley 2470

Matlab program to be used for conducting IV curve measurements with the Keithley 2470. To make the program work, 
you need to set the following parameters located in the initial part of the code:

+ `current_compliance` [A] is the maximum current that can be supplied by the instrument.
+ `max_voltage` [V] is the maximum voltage to be applied to the sample under examination, which can be positive or negative.
+ `voltage_step` [V] sets the voltage step in the first measurement phase from 0V to V<sub>set</sub>, to be specified in absolute value.
+ `voltage_step_back` [V] sets the voltage step in the second measurement phase from V<sub>set</sub> to 0V, to be specified in absolute value.
+ `filename` is the name of the output file. The file will have the structure: filename + datetime + ext.
+ `filename_format` is the extension of the output file.
+ `Keithley2470.IP` is the IP address of the Keithley 2470 instrument, to be checked each time the instrument is powered on.
