# import visa
import pyvisa as visa
import time
import datetime
import matplotlib.pyplot as plt
import numpy as np

echo_commands = 0


def instrument_connect(resource_mgr, instrument_object, instrument_resource_string, timeout, do_id_query, do_reset, do_clear): 
    instrument_object = resource_mgr.open_resource(instrument_resource_string)
    if do_id_query == 1:
        print(instrument_query(instrument_object, "*IDN?"))
    if do_reset == 1:
        instrument_write(instrument_object, "*RST")
    if do_clear == 1:
        instrument_object.clear()
    instrument_object.timeout = timeout
    return resource_mgr, instrument_object

def instrument_write(instrument_object, my_command):
    if echo_commands == 1:
        print(my_command)
    instrument_object.write(my_command)
    return

def instrument_read(instrument_object):
    return instrument_object.read()

def instrument_query(instrument_object, my_command):
    if echo_commands == 1:
        print(my_command)
    return instrument_object.query(my_command)

def instrument_disconnect(instrument_object):
    instrument_object.close()
    return


#================================================================================
#
#    MAIN CODE STARTS HERE
#
#================================================================================

time_set_filename = datetime.datetime.now()
filename_time = time_set_filename.strftime("%Y%m%d_%H%M%S")

filename = "sample3_vbias_100_source_am241"
instrument_resource_string = "TCPIP0::10.196.31.127::inst0::INSTR"
quantity_to_measure = "AMPlitude"
acq_time = 600 #in seconds

f = open("Data/{}_{}.txt".format(filename,filename_time), "w")
f.write("id,value\n")

time_start_programme = time.time()                    # Start the timer...

resource_manager = visa.ResourceManager()	# Opens the resource manager
my_instr = None 
resource_manager, my_instr = instrument_connect(resource_manager, my_instr, instrument_resource_string,20000,1,0,0)

instrument_write(my_instr, "MEASUREMENT:IMMED:TYPE {}".format(quantity_to_measure))
count =0

try:
    while True and (time.time()-time_start_programme)<acq_time:
        voltage = float(instrument_query(my_instr,':MEASUrement:IMMed:VALue?'))
        if (count%100)==0:
            print("Num event save: {} -- Elapsed time: {:.2f}".format(count,time.time()-time_start_programme))
            
        f.write("{},{}\n".format(count,voltage))
        count=count+1
except KeyboardInterrupt:
    print("Finish :)")
    pass

f.close()
instrument_disconnect(my_instr)
resource_manager.close

