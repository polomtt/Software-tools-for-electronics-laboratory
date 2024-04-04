##Measure_Keytley2470_for_long_time

+Questo script è utile per comunicare con Keytley 24XX, usansdo l'interfaccia SPI.
+Permette di settare la tensione V<sub>i<\sub> per un tempo T<sub>i<\sub> (s) e misurare la corrente I (A).
+Per l'esecuzione usare lo 'script start_measure_example.sh'
La riga da modificare è indicata da una freccia
La struttura della riga è

'echo "*filename* T V<sub>1<\sub> V<sub>2<\sub> ... V<sub>N<\sub>" > voltage_set_file'

