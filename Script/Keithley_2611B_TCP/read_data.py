import pyvisa as visa
import time
import datetime
import matplotlib.pyplot as plt
import numpy as np
import os

echo_commands = 0


# ============================================================
# INSTRUMENT CONNECTION
# ============================================================

def instrument_connect(resource_mgr, instrument_resource_string,
                       timeout, do_id_query, do_reset):

    instrument_object = resource_mgr.open_resource(
        instrument_resource_string
    )

    instrument_object.timeout = timeout
    instrument_object.write_termination = "\n"
    instrument_object.read_termination = "\n"

    if do_id_query == 1:
        print("Connected to Keithley:", 
              instrument_query(instrument_object, "localnode.model"))

    if do_reset == 1:
        instrument_write(instrument_object, "reset()")

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

    # TSP queries require print()
    return instrument_object.query("print(" + my_command + ")")


def instrument_disconnect(instrument_object):

    instrument_object.close()

    return


# ============================================================
# ACQUISITION
# ============================================================

def acquisition(my_instr, f, voltage_vector, current_vector,
                voltage, time_start_programme):

    current_meas = float(
        instrument_query(my_instr, "smua.measure.i()")
    )

    time_to_plot = time.time() - time_start_programme

    f.write("{:.3f},{:.6f},{:.6e}\n".format(
        time_to_plot, voltage, current_meas
    ))

    print("{:.3f},{:.6f},{:.6e}".format(
        time_to_plot, voltage, current_meas
    ))

    f.flush()

    voltage_vector.append(voltage)
    current_vector.append(current_meas)

    return current_meas


# ============================================================
# VOLTAGE RAMP
# ============================================================

def ramp(my_instr, f, voltage_vector, current_vector,
         v_start, v_end, time_start_programme,
         step=0.5, delay=0.3):

    direction = 1 if v_end > v_start else -1

    step = abs(step) * direction

    v = v_start

    while ((direction > 0 and v <= v_end) or
           (direction < 0 and v >= v_end)):

        instrument_write(
            my_instr,
            "smua.source.levelv = {:.6f}".format(v)
        )

        acquisition(
            my_instr,
            f,
            voltage_vector,
            current_vector,
            v,
            time_start_programme
        )

        time.sleep(delay)

        v += step

    # Ensure exact final voltage
    instrument_write(
        my_instr,
        "smua.source.levelv = {:.6f}".format(v_end)
    )

    time.sleep(delay)


# ============================================================
# EXPERIMENT PARAMETERS
# ============================================================

# Voltage parameters [V]

step_voltage = 0.01
V_set = 0.1

double_polarity = True

# Bias sequence:
#
# single polarity:
# 0 -> +Vset -> 0
#
# double polarity:
# 0 -> +Vset -> 0 -> -Vset -> 0

current_compliance = 1e-4  # Ampere

delay_new_step = 0.1  # seconds

sample_name = "Alginate_OVA_11kPa_D4_CARA_A_SIN100G_CONPORTAMUESTRAS(2)"


# ============================================================
# INSTRUMENT CONFIGURATION
# ============================================================

instrument_resource_string = "TCPIP0::10.196.31.8::5025::SOCKET"


# ============================================================
# MAIN CODE
# ============================================================

time_set_filename = datetime.datetime.now()

filename_time = time_set_filename.strftime("%Y%m%d_%H%M%S")

folder = "Data/"

os.makedirs(folder, exist_ok=True)

filename_out = folder + sample_name


# Voltage sequence

if double_polarity:

    v_set_value_vector = [
        V_set,
        V_set * -1.0
    ]

else:

    v_set_value_vector = [
        V_set
    ]


# Output file

f = open(
    "{}_{}.txt".format(filename_out, filename_time),
    "w"
)

f.write("#time[s],voltage[V],current[A]\n")


# Start timer

time_start_programme = time.time()


# ============================================================
# CONNECT TO KEITHLEY
# ============================================================

resource_manager = visa.ResourceManager()

my_instr = None

resource_manager, my_instr = instrument_connect(
    resource_manager,
    instrument_resource_string,
    10000,
    1,
    0
)


# ============================================================
# INITIALIZATION - TSP
# ============================================================

# Switch output OFF

instrument_write(
    my_instr,
    "smua.source.output = smua.OUTPUT_OFF"
)

# Abort previous operations

instrument_write(
    my_instr,
    "smua.abort()"
)

# Configure voltage source

instrument_write(
    my_instr,
    "smua.source.func = smua.OUTPUT_DCVOLTS"
)

# Initial voltage

instrument_write(
    my_instr,
    "smua.source.levelv = 0"
)

# Current compliance

instrument_write(
    my_instr,
    "smua.source.limiti = {}".format(current_compliance)
)

# Current measurement range

instrument_write(
    my_instr,
    "smua.measure.rangei = 10e-3"
)

# Enable output

instrument_write(
    my_instr,
    "smua.source.output = smua.OUTPUT_ON"
)


# ============================================================
# VOLTAGE SWEEP
# ============================================================

voltage_vector = []
current_vector = []

for v_set in v_set_value_vector:

    # Read actual source voltage

    v_start = float(
        instrument_query(
            my_instr,
            "smua.source.levelv"
        )
    )

    # Ramp from initial voltage to target voltage

    ramp(
        my_instr,
        f,
        voltage_vector,
        current_vector,
        v_start,
        v_set,
        time_start_programme,
        step=step_voltage,
        delay=delay_new_step
    )

    # Ramp back to zero

    ramp(
        my_instr,
        f,
        voltage_vector,
        current_vector,
        v_set,
        0.0,
        time_start_programme,
        step=step_voltage,
        delay=delay_new_step
    )


# ============================================================
# SHUTDOWN
# ============================================================

# Output OFF

instrument_write(
    my_instr,
    "smua.source.output = smua.OUTPUT_OFF"
)

# Reset instrument

instrument_write(
    my_instr,
    "reset()"
)

# Disconnect

instrument_disconnect(my_instr)

resource_manager.close()

f.close()

print("done :)")


# ============================================================
# PLOT RESULTS
# ============================================================

fontsize_to_use = 15

plt.figure()

plt.plot(
    voltage_vector,
    current_vector,
    label="Current"
)

plt.grid(True)

plt.xlabel(
    "Voltage [V]",
    fontsize=fontsize_to_use
)

plt.ylabel(
    "Current [A]",
    fontsize=fontsize_to_use
)

plt.ticklabel_format(
    style="sci",
    axis="y",
    scilimits=(0, 0)
)

plt.title(
    "{}_{}".format(filename_out, filename_time),
    fontsize=fontsize_to_use
)

plt.tight_layout()

plt.savefig(
    "{}_{}.png".format(filename_out, filename_time)
)

plt.show()
