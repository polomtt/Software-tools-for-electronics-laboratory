# import visa
import pyvisa as visa
import time
import datetime
import matplotlib.pyplot as plt
import numpy as np

echo_commands = 0

def instrument_connect(resource_mgr, instrument_object, instrument_resource_string,
                       timeout, do_id_query, do_reset, do_clear):

    instrument_object = resource_mgr.open_resource(instrument_resource_string)

    instrument_object.timeout = timeout
    instrument_object.write_termination = "\n"
    instrument_object.read_termination = "\n"

    if do_id_query == 1:
        print(instrument_object.query("*IDN?"))

    if do_reset == 1:
        instrument_write(instrument_object, "*RST")

    if do_clear == 1:
        instrument_object.clear()

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


def acquisition(my_instr, f, voltage_vector, current_vector, voltage, time_start_programme):
    current_meas = float(instrument_query(my_instr, ':MEAS:CURR?'))
    time_to_plot = time.time() - time_start_programme

    f.write("{:.3f},{:.6f},{:.6e}\n".format(time_to_plot,voltage,current_meas))
    print("{:.3f},{:.6f},{:.6e}".format(time_to_plot,voltage,current_meas))
    f.flush()

    voltage_vector.append(voltage)
    current_vector.append(current_meas)

    return current_meas


def ramp(my_instr, v_start, v_end, step=0.5, delay=0.3):

    direction = 1 if v_end > v_start else -1
    step = abs(step) * direction

    v = v_start

    while (direction > 0 and v <= v_end) or (direction < 0 and v >= v_end):

        instrument_write(my_instr, f":SOUR:VOLT {v:.3f}")
        acquisition(my_instr, f,
            voltage_vector,
            current_vector,
            v,
            time_start_programme)
        time.sleep(delay)

        v += step

    instrument_write(my_instr, f":SOUR:VOLT {v_end:.3f}")
    time.sleep(delay)



#  ___                                _
#|  _ \ __ _ _ __ __ _ _ __ ___   ___| |_ ___ _ __ ___
#| |_) / _` | '__/ _` | '_ ` _ \ / _ \ __/ _ \ '__/ __|
#|  __/ (_| | | | (_| | | | | | |  __/ ||  __/ |  \__ \
#|_|   \__,_|_|  \__,_|_| |_| |_|\___|\__\___|_|  |___/

##in Volts
#step_voltage = 0.01
#V_set = 0.5
#sample_name = "GelMA-05PEDOT_2"

#double_polarity = True
## Bias sequence definition:
## - single polarity:False→ +Vset → 0
## - double_polarity:True =>  0 → +Vset → -Vset → 0
## (used for I-V characterization under forward/reverse bias)

#current_compliance = 100e-6 # in Ampere
#delay_new_step = 0 #in secondi

#For COBRA

step_voltage = 0.5
V_set = -80
sample_name = "Meas_Current_COBRA_IV_sensor_su_Kapton_Bias_BACK_sp3_AFTER_Ba133"

double_polarity = False
# Bias sequence definition:
# - single polarity:False→ +Vset → 0
# - double_polarity:True =>  0 → +Vset → -Vset → 0
# (used for I-V characterization under forward/reverse bias)

current_compliance = 600e-6 # in Ampere
delay_new_step = 1.0 #in secondi

#instrument_resource_string = "TCPIP::10.196.31.120::inst0::INSTR"
instrument_resource_string = "TCPIP::10.196.31.238::inst0::INSTR"


#================================================================================
#
#    MAIN CODE STARTS HERE
#
#================================================================================


time_set_filename = datetime.datetime.now()
filename_time = time_set_filename.strftime("%Y%m%d_%H%M%S")
folder = "Data/"

v_set_value_vector = []

voltage = 0
if double_polarity:
    v_set_value_vector = [V_set,V_set*-1.0]
else:
    v_set_value_vector = [V_set]

filename_out = folder + sample_name

f = open("{}_{}.txt".format(filename_out,filename_time), "w")
f.write("#time[s],voltage[V],current[A]\n")

time_start_programme = time.time()                    # Start the timer...
resource_manager = visa.ResourceManager()	# Opens the resource manager
my_instr = None 
resource_manager, my_instr = instrument_connect(resource_manager, my_instr, instrument_resource_string, 10000, 1, 0, 0)


instrument_write(my_instr, ":OUTP:STAT OFF")
instrument_write(my_instr, ":ABOR")

instrument_write(my_instr, ":SOUR:FUNC VOLT")
instrument_write(my_instr, ":SOUR:VOLT 0")
instrument_write(my_instr, ":SOURce:VOLT:ILIM {}".format(current_compliance))

instrument_write(my_instr, ":TRIG:BLOC:BUFF:CLE 1")
instrument_write(my_instr, ":TRIG:BLOC:MEAS 1")

instrument_write(my_instr, ":INIT")

instrument_write(my_instr, ":OUTP:STAT ON")

#exit()

voltage_vector = []
current_vector = []

for v_set in v_set_value_vector:
    v_start = float(instrument_query(my_instr, ":SOUR:VOLT?"))
    ramp(my_instr, v_start, v_set, step=step_voltage, delay=delay_new_step)
    ramp(my_instr, v_set, 0.0, step=step_voltage, delay=delay_new_step)

instrument_write(my_instr,":OUTP:STAT OFF")
instrument_write(my_instr,'*RST')
instrument_disconnect(my_instr)
resource_manager.close

print("done :)")

fontsize_to_use = 15

plt.figure()
plt.plot(voltage_vector,current_vector,label="Current")
plt.grid(True)
plt.xlabel("Voltage [V]",fontsize=fontsize_to_use)
plt.ylabel("Current [A]",fontsize=fontsize_to_use)
plt.ticklabel_format(style='sci', axis='y', scilimits=(0,0))
plt.tight_layout()
plt.title("{}_{}".format(filename_out,filename_time),fontsize=fontsize_to_use)
plt.savefig("{}_{}.png".format(filename_out,filename_time))
plt.show()

