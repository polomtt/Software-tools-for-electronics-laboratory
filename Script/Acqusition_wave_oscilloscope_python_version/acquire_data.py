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

def download_waveform(instrument_object, channel="CH1", n_points=2500):
    import struct

    # Imposta il canale e l’encoding binario
    instrument_write(instrument_object, f"DATA:SOURCE {channel}")
    instrument_write(instrument_object, "DATA:ENCODING RIBinary")  # o "BYTE" se il tuo oscillo lo richiede
    instrument_write(instrument_object, "DATA:WIDTH 1")  # 1 byte per punto
    instrument_write(instrument_object, f"DATA:START 1")
    instrument_write(instrument_object, f"DATA:STOP {n_points}")

    # Legge parametri di scala
    y_mult = float(instrument_query(instrument_object, "WFMPRE:YMULT?"))
    y_off = float(instrument_query(instrument_object, "WFMPRE:YOFF?"))
    y_zero = float(instrument_query(instrument_object, "WFMPRE:YZERO?"))

    # Legge la curva binaria
    instrument_object.write("CURVE?")
    raw = instrument_object.read_raw()

    # Parsing header binario: es. #85000[...] -> 8 cifre, 5000 byte
    if raw[0:1] != b"#":
        raise ValueError("Formato binario non valido.")
    
    header_len = int(raw[1:2])
    n_bytes = int(raw[2:2+header_len])
    data_start = 2 + header_len
    waveform_data = raw[data_start:data_start+n_bytes]

    # Converte da byte a array numpy
    data = np.frombuffer(waveform_data, dtype=np.int8)  # 1 byte = int8

    # Applica la scalatura reale
    voltage = (data - y_off) * y_mult + y_zero

    return voltage

#================================================================================
#    MAIN CODE STARTS HERE
#================================================================================

time_set_filename = datetime.datetime.now()
filename_time = time_set_filename.strftime("%Y%m%d_%H%M%S")

filename = "sample3_vbias_100_source_am241"
instrument_resource_string = "TCPIP0::10.196.31.122::inst0::INSTR"
acq_time = 10  # in seconds

f = open("Data/{}_{}.txt".format(filename, filename_time), "w")
f.write("id,value\n")

time_start_programme = time.time()

resource_manager = visa.ResourceManager()
my_instr = None 
resource_manager, my_instr = instrument_connect(resource_manager, my_instr, instrument_resource_string, 20000, 1, 0, 0)

# 1. Imposta modalità media su 4 campioni
instrument_write(my_instr, "ACQuire:MODE AVERage")
instrument_write(my_instr, "ACQuire:NUMAVg 4")
time.sleep(1)  # attesa per calcolo media

# 2. Imposta misura di ampiezza su CH1
instrument_write(my_instr, "MEASurement:IMMed:TYPE AMPLitude")
instrument_write(my_instr, "MEASurement:IMMed:SOURCE CH1")

count = 0

try:
    while True and (time.time() - time_start_programme) < acq_time:
        voltage = float(instrument_query(my_instr, ':MEASurement:IMMed:VALue?'))
        print(voltage)

        if (count % 10) == 0:
            print("Num event save: {} -- Elapsed time: {:.2f}".format(count, time.time() - time_start_programme))
        
        # wave = download_waveform(my_instr)
        # plt.plot(wave)
        
        
        # f.write("{},{}\n".format(count, voltage))
        count += 1

except KeyboardInterrupt:
    print("Misura interrotta manualmente.")

f.close()
plt.show()
instrument_disconnect(my_instr)
resource_manager.close()


