@echo off
call venv\Scripts\activate
pyinstaller --onefile --windowed --clean --collect-all PyQt6 --collect-all pyqtgraph --collect-all pyvisa --collect-all pyvisa_py --collect-all usb --collect-all serial --icon=icona.ico app.py
echo.
echo Build complete. Executable in dist\app.exe
pause