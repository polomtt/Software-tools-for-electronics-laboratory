import pyvisa
import time



# Default address (set in config.py)

DEFAULT_AXES = {
    'x': 'ASRL4::INSTR',
    'y': 'ASRL5::INSTR',
    'z': 'ASRL3::INSTR',
}
SERIAL_BAUD      = 38400
SERIAL_TIMEOUT   = 2000 

class Motor:
    """
    Classe per il controllo di un singolo motore Opto Sigma SRC-101
    tramite PyVISA (comunicazione seriale RS-232/USB).

    Parametri
    ----------
    axis : str
        Etichetta dell'asse ('x', 'y' o 'z'). Usata solo nei log.
    address : str
        Indirizzo VISA della porta seriale (es. 'ASRL4::INSTR').
    resource_manager : pyvisa.ResourceManager, opzionale
        Se non fornito, ne viene creato uno interno con backend '@py'.

    Uso tipico
    ----------
        motor = Motor('x', 'ASRL4::INSTR')
        motor.connect()
        motor.move(pulses=1000, speed=5000)   # avanti
        motor.move(pulses=500,  speed=-3000)  # indietro
        motor.disconnect()
    """

    def __init__(self, axis: str, address: str,
                 resource_manager: pyvisa.ResourceManager = None):
        self.axis    = axis.upper()
        self.address = address
        self._rm_external = resource_manager is not None
        self._rm   = resource_manager or pyvisa.ResourceManager('')
        self._inst = None          # handle VISA, valido dopo connect()

    #  Connection / Disconnection 

    def connect(self):
       """Opens the serial port and configures SRC-101 parameters."""
       self._inst = self._rm.open_resource(
           self.address,
           baud_rate    = SERIAL_BAUD,
           data_bits    = 8,
           stop_bits    = pyvisa.constants.StopBits.one,
           parity       = pyvisa.constants.Parity.none,
           flow_control = pyvisa.constants.ControlFlow.none,
       )
   
       self._inst.timeout           = SERIAL_TIMEOUT
       self._inst.read_termination  = '\r\n'
       self._inst.write_termination = '\r\n'
   
       # clear() is not supported on serial resources with pyvisa-py backend,
       # so we flush manually by draining any stale bytes in the buffer.
       try:
           self._inst.flush(pyvisa.constants.VI_IO_IN_BUF_DISCARD)
       except Exception:
           pass  # not all backends support flush either – safe to ignore
   
       time.sleep(0.1)
       print(f"[Motor {self.axis}] Connected on {self.address}")
   
    def disconnect(self):
        """Chiude la connessione VISA."""
        if self._inst is not None:
            try:
                self._inst.close()
            except Exception:
                pass
            self._inst = None
            print(f"[Motore {self.axis}] Disconnesso.")

        # Close the ResourceManager only if the state was created 
        if not self._rm_external:
            try:
                self._rm.close()
            except Exception:
                pass

    # State property 

    @property
    def is_connected(self) -> bool:
        return self._inst is not None

    # Low level comand
    def _write(self, cmd: str):
        """Send command without waiting."""
        if not self.is_connected:
            raise RuntimeError(f"Engine {self.axis}: not connected.")
        self._inst.write(cmd)
        time.sleep(0.05)

    def _query(self, cmd: str) -> str:
        """Send a command and wait answer (stripped)."""
        if not self.is_connected:
            raise RuntimeError(f"Motor {self.axis}: not connected.")
        return self._inst.query(cmd).strip()

    # High level command
    def set_speed(self, speed: int):
        """
        Set the maximum speed in pulses per second (absolute value).
        The direction is NOT encoded here — it is passed via move().

        Parameters
        ----------
        speed : int
            Absolute value of the speed (pulses per second). It must be greater than 0.
        """
        if speed <= 0:
            raise ValueError("set_speed() need a positive value. "
                             "Exploit move() with negative speed for counter motion.")
        cmd = f"D:1S0F{speed}R0"
        self._write(cmd)
        time.sleep(0.1)

    def move(self, pulses: int, speed: int, wait: bool = True):
        """
        Execute a relative motion.

        Parametri
        ----------
        pulses : int
            Number of steps to be taken (absolute value).
        speed : int
            Speed in pulse/s with sign:
              > 0  -> Forward direction  (+)
              < 0  -> Backward direction (-)
        wait : bool
            If True (default), it waits for the motor to stop
            before returning control.

        Example
        -------
            motor.move(pulses=1000, speed=5000)   # forward  1000 pulses
            motor.move(pulses=500,  speed=-3000)  # backward 500 pulses
        """
        if pulses <= 0:
            raise ValueError("pulses must be a positive integer.")
        if speed == 0:
            raise ValueError("speed cannot be zero.")

        direction = '+' if speed > 0 else '-'
        abs_speed = abs(speed)

        #  Set speed
        self.set_speed(abs_speed)

        #  Load relative motion
        self._write(f"M:1{direction}P{pulses}")

        # Execute command
        self._write("G:")

        print(f"[Motor {self.axis}] Motion: {direction}{pulses} pulses "
              f"@ {abs_speed} pulse/s")

        # Wait for required motion
        if wait:
            self.wait_ready()

    def stop(self):
        """Immediate stop (decelerated stop)."""
        self._write("L:1")
        print(f"[Motor {self.axis}] Stop.")
    
    def home(self):
      """
      Sends the motor to the origin position (mechanical home search).
      Blocks until the motor reports Ready.
      """
      self._write("H:1")   # SRC-101 home command
      self._write("G:")    # execute
      print(f"[Motor {self.axis}] Homing ...")
      self.wait_ready()
      print(f"[Motor {self.axis}] Homing complete.")

    # Than 
    def get_status(self) -> dict:
       raw   = self._query("Q:")
       parts = raw.split(',')
   
       try:
           # Strip everything that isn't a digit or a sign
           clean    = ''.join(c for c in parts[0] if c.isdigit() or c in '+-')
           position = int(clean) if clean else 0
       except (ValueError, IndexError):
           position = 0
   
       ready = (len(parts) == 4 and parts[3].strip() == 'R')
       return {'position': position, 'ready': ready, 'raw': raw}

    def wait_ready(self, poll_interval: float = 0.1):
        """
        Hold until the engine displays 'Ready'.

        Parameters
        ----------
        poll_interval : float
            Polling interval in seconds (default 0.1 s).
        """
        while True:
            status = self.get_status()
            if status['ready']:
                break
            time.sleep(poll_interval)

    def get_position(self) -> int:
        """Returns the current position in pulses."""
        return self.get_status()['position']

    #  Context manager 

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.disconnect()
