python3 -c "
from caen_libs import caenhvwrapper
# ... (dopo aver aperto il device come fa il driver)
print(device.get_ch_param_info(slot, 0))
"
