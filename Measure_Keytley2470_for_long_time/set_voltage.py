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

def acquisition(my_instr,f,voltage_vector,current_vector,voltage,time_start_programme):
    current_meas = float(instrument_query(my_instr,':MEAS:CURR?'))
    time_to_plot = time.time()-time_start_programme
    text_to_plot = "{:.2f},{:.2f},{}\n".format(time_to_plot,voltage,current_meas)
    f.write(text_to_plot)
    voltage_vector.append(voltage)
    current_vector.append(current_meas)

    return current_meas

#================================================================================
#
#    MAIN CODE STARTS HERE
#
#================================================================================

step_voltage = 1
current_compliance = 100e-6
voltage = 0
time_set_filename = datetime.datetime.now()
filename_time = time_set_filename.strftime("%Y%m%d_%H%M%S")

file1 = open('voltage_set_file', 'r')
Lines = file1.readlines()
Lines = Lines[0].replace("\n","")
x = Lines.split(" ")

if len(x)<3:
    print("Error!")
    print("The configuration file must be in the form: Filename-Time_acq-Ni_voltage_to_Set")
    exit()

f = open("{}_{}.txt".format(x[0],filename_time), "w")
f.write("time[s],voltage[V],current[A]\n")

time_acq_for_step = float(x[1])
v_set_value_vector = []
for v in range(2,len(x)):
    v_set_value_vector.append(float(x[v]))


time_start_programme = time.time()                    # Start the timer...
instrument_resource_string = "TCPIP0::10.196.31.142::inst0::INSTR"
resource_manager = visa.ResourceManager()	# Opens the resource manager
my_instr = None 
resource_manager, my_instr = instrument_connect(resource_manager, my_instr, instrument_resource_string, 20000, 1, 1, 1)

instrument_write(my_instr,'*RST')
instrument_write(my_instr,':SOUR:VOLT 0')
instrument_write(my_instr,':OUTP:STAT OFF')
instrument_write(my_instr,':ABOR');
instrument_write(my_instr,':TRIG:BLOC:BUFF:CLE 1')
instrument_write(my_instr,':TRIG:BLOC:MEAS 1')
instrument_write(my_instr,':INIT')
instrument_write(my_instr,'*WAI')
instrument_write(my_instr,':SOUR:FUNC VOLT')
instrument_write(my_instr,":OUTP:STAT ON")
instrument_write(my_instr,":SOUR:CURR:RANG 100e-6")

voltage_vector = []
current_vector = []

for v_set in v_set_value_vector:

    voltage = float(instrument_query(my_instr,':MEAS:VOLT?'))

    if v_set>0:
        step_voltage=1
    else:
        step_voltage=-1

    step_number = round(abs(v_set-voltage)+1)

    for step in range(0,step_number):
        instrument_write(my_instr,':SOUR:VOLT {}'.format(voltage))
        c = acquisition(my_instr,f,voltage_vector,current_vector,voltage,time_start_programme)
        voltage = voltage+step_voltage
        time.sleep(1)
        if step_voltage>0:
            print("STATUS -> RUMP UP")
        if step_voltage<0:
            print("STATUS -> RUMP DOWN")

    f.flush()

    time_set = time.time()
    time_set_output_log = time_set + 2
    time_acq = time_set + time_acq_for_step

    voltage = float(instrument_query(my_instr,':MEAS:VOLT?'))

    while (time_set<time_acq):
        c = acquisition(my_instr,f,voltage_vector,current_vector,voltage,time_start_programme)
        time.sleep(0.05)
        time_set = time.time()
        t_remain = time_acq - time_set

        if time_set>time_set_output_log:
            print("STATUS -> ON -- {}V -- Time remain: {:.2f}s".format(voltage,t_remain))
            time_set_output_log = time_set_output_log+5

    f.flush()

    #abbasso la tensione

voltage = float(instrument_query(my_instr,':MEAS:VOLT?'))

for step in range(0,abs(int(voltage))+1):

    if voltage>0:
        step_voltage=1
    else:
        step_voltage=-1

    instrument_write(my_instr,':SOUR:VOLT {}'.format(voltage))
    c = acquisition(my_instr,f,voltage_vector,current_vector,voltage,time_start_programme)
    voltage = voltage-step_voltage
    time.sleep(1)
    print("STATUS -> RUMP DOWN")

f.flush()

time_set = time.time()
time_stop = time_set + 10

while (time_set<time_stop):
    voltage = float(instrument_query(my_instr,':MEAS:VOLT?'))
    c = acquisition(my_instr,f,voltage_vector,current_vector,voltage,time_start_programme)
    time.sleep(1)
    time_set = time.time()
    print("STATUS -> MEASURE AT 0V")

f.close()

instrument_write(my_instr,":OUTP:STAT OFF")
instrument_write(my_instr,'*RST')
instrument_disconnect(my_instr)
resource_manager.close

print("done")
#
# fig, axs = plt.subplots(2)
# axs[0].plot(current_vector,label="Current")
# axs[1].plot(voltage_vector,label="Voltage")
# plt.show()

