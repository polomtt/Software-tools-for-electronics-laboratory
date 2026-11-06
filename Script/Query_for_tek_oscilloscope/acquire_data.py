import pyvisa as visa
import time
import datetime
import os

echo_commands = 0


def instrument_connect(resource_mgr, instrument_resource_string,
                       timeout, do_id_query, do_reset, do_clear):

    instrument_object = resource_mgr.open_resource(
        instrument_resource_string
    )

    instrument_object.timeout = timeout

    if do_id_query:
        print(instrument_query(instrument_object, "*IDN?"))

    if do_reset:
        instrument_write(instrument_object, "*RST")

    if do_clear:
        instrument_object.clear()

    return resource_mgr, instrument_object


def instrument_write(instrument_object, my_command):
    if echo_commands:
        print(my_command)

    instrument_object.write(my_command)


def instrument_query(instrument_object, my_command):
    if echo_commands:
        print(my_command)

    return instrument_object.query(my_command)


def instrument_disconnect(instrument_object):
    instrument_object.close()


# ============================================================
# MAIN CODE
# ============================================================

filename = "cobra"

instrument_resource_string = "TCPIP0::10.196.31.73::inst0::INSTR"

quantity_to_measure = "CURRent"

acq_time = 600000  # seconds

# Sampling interval (seconds)
sampling_interval = 10

# Create output directory
os.makedirs("Data", exist_ok=True)

# Generate filename
filename_time = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

filepath = "Data/{}_{}.txt".format(filename, filename_time)

# Start timer
time_start_programme = time.time()

resource_manager = visa.ResourceManager()
my_instr = None
count = 0

try:

    # Connect to instrument
    resource_manager, my_instr = instrument_connect(
        resource_manager,
        instrument_resource_string,
        20000,
        1,
        0,
        0
    )

    # Configure measurement
    instrument_write(
        my_instr,
        "MEASUREMENT:IMMED:TYPE {}".format(quantity_to_measure)
    )

    print("\nStarting current acquisition...\n")

    with open(filepath, "w") as f:

        f.write("id,time,value\n")

        while (time.time() - time_start_programme) < acq_time:

            # Measure current
            current_meas = float(
                instrument_query(my_instr, ":MEAS:CURR?")
            )

            elapsed_time = time.time() - time_start_programme

            # Save measurement
            f.write(
                "{},{:.6f},{:.12e}\n".format(
                    count,
                    elapsed_time,
                    current_meas
                )
            )
            f.flush()

            # Print measurement
            if count % 100 == 0:

                print(
                    "Event: {} | Time: {:.2f} s | Current: {:.8e} A".format(
                        count,
                        elapsed_time,
                        current_meas
                    )
                )

            count += 1
            
            time.sleep(sampling_interval)

    print("\nAcquisition completed!")

except KeyboardInterrupt:

    print("\nAcquisition interrupted by user.")

except Exception as e:

    print("\nERROR:", e)

finally:

    if my_instr is not None:
        instrument_disconnect(my_instr)

    resource_manager.close()

    print("Total measurements: {}".format(count))
    print("Data saved in: {}".format(filepath))

