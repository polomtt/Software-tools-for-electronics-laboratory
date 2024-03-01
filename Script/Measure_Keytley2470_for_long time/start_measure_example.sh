rm voltage_set_file
echo "sample3 900 5 10 15 20 25 30" > voltage_set_file
python3 set_voltage.py

rm voltage_set_file
echo "sample3 1800 5 10 15 20 25 30" > voltage_set_file
python3 set_voltage.py

rm voltage_set_file
echo "sample3 600 5 0 -5 0 10 0 -10" > voltage_set_file
python3 set_voltage.py
