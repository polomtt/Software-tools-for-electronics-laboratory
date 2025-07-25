# Measure_Keytley2470_for_long_time

+ This script is useful for communicating with Keytley 24XX, using the SPI interface.
+ It allows setting the voltage V<sub>i</sub> for a time T<sub>i</sub> (s) and measuring the current I (A).
+ To execute, use the 'start_measure_example.sh' script
    + The line to modify is indicated by an arrow
    + The structure of the line is

        `echo "filename T V1 V2 ... VN" > voltage_set_file`

        + With this line, the data is saved in a `csv` file named `filename`
        + The program performs the following measurement:

            ```
            V1 for a time T (s)
            V2 for a time T (s)
            ...
            VN for a time T (s)
            ```


