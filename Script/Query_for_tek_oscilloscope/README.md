# Query_fot_tek_oscilloscope

+ This script is useful for communicating with Tektronic Oscilloscope, using the SCPI command. See 3SeriesMDO-Programmer.pdf
+ With this script it is possbile to save in a csv file the measure made by the oscilloscope
+ To execute, you must change the following variable in the code:
	+ `filename`: name of the csv file
	+ `instrument_resource_string`: IP of the oscilloscope
	+ `quantity_to_measure`: SCPI command
	+ `acq_time`: in second



