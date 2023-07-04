import mcphysics as _mp
import numpy as _n

_debug_enabled = False
_debug = _mp._debug

class auber_syl53x2p_api():
    """
    Commands-only object for interacting with an Auber Instruments SYL-53X2P
    temperature controller.
    Parameters
    ----------
    port='COM3' : str
        Name of the port to connect to.
    address=1 : int
        Address of the instrument. Can be 0-255, and must match the instrument
        setting.
    baudrate=9600 : int
        Baud rate of the connection. Must match the instrument setting.
    timeout=2000 : number
        How long to wait for responses before giving up (ms). Must be >300 for this instrument.
        
    temperature_limit=450 : float
        Upper limit on the temperature setpoint (C).
    """
    def __init__(self, port='COM3', address=1, baudrate=9600, timeout=2000, temperature_limit=500):

        self._temperature_limit = temperature_limit        

        # Check for installed libraries
        if not _mp._minimalmodbus or not _mp._serial:
            print('You need to install pyserial and minimalmodbus to use the Auber SYL-53X2P.')
            self.modbus = None
            self.simulation_mode = True

        # Assume everything will work for now
        else: self.simulation_mode = False

        # If the port is "Simulation"
        if port=='Simulation': self.simulation_mode = True
        
        self.simulation_setpoint = 24.5

        # If we have all the libraries, try connecting.
        if not self.simulation_mode:
            try:
                # Create the instrument and ensure the settings are correct.
                self.modbus = _mp._minimalmodbus.Instrument(port, address)

                # Other settings
                self.modbus.serial.baudrate = baudrate              # Baud rate
                self.modbus.serial.bytesize = 8                     # Typical size of a byte :)
                self.modbus.serial.parity = _mp._minimalmodbus.serial.PARITY_NONE # No parity check for this instrument.
                self.modbus.serial.stopbits = 1                     # Whatever this means. It needs to be 1 for this instrument.
                self.modbus.serial.timeout  = timeout*0.001         # Timeout in seconds. Must be >0.3 for this instrument.
                self.modbus.mode = _mp._minimalmodbus.MODE_RTU                    # RTU or ASCII mode. Must be RTU for this instrument.
                self.modbus.clear_buffers_before_each_transaction = True # Seems like a good idea. Works, too.

                # Simulation mode flag
                self.simulation_mode = False

                # Test the connection
                self.get_temperature()


            # Something went wrong. Go into simulation mode.
            except Exception as e:
                print('Could not open connection to "'+port+':'+str(address)+'" at baudrate '+str(baudrate)+'. Entering simulation mode.')
                print(e)
                self.modbus = None
                self.simulation_mode = True

    def disconnect(self):
        """
        Disconnects.
        """
        if not self.simulation_mode: self.modbus.serial.close()

    def get_alarm_status(self):
        """
        Returns the alarm code:
            0: Alarm 1 off, Alarm 2 off (yay!)
            1: Alarm 1 on,  Alarm 2 off
            2: Alarm 1 off, Alarm 2 on
            3: Alarm 1 on,  Alarm 2 on
        It was binary all along! All along!
        """
        if self.simulation_mode: return 0
        else:                    return self.modbus.read_register(0x1201, 0)

    def get_main_output_power(self):
        """
        Gets the current output power (percent).
        """
        if self.simulation_mode: return _n.random.randint(0,200)
        else:                    return self.modbus.read_register(0x1101, 0)

    def get_temperature(self):
        """
        Gets the current temperature in Celcius.
        """
        if self.simulation_mode: return _n.round(_n.random.rand()+24, 1)
        else:                    return self.modbus.read_register(0x1001, 1)

    def get_temperature_setpoint(self):
        """
        Gets the current temperature setpoint in Celcius.
        """
        if self.simulation_mode: return self.simulation_setpoint
        else:                    return self.modbus.read_register(0x1002, 1)

    def set_temperature_setpoint(self, T=20.0, temperature_limit=None):
        """
        Sets the temperature setpoint to the supplied value in Celcius.
        
        Parameters
        ----------
        T=20.0 : float
            Temperature setpoint (C).
            
        temperature_limit=None : None or float
            If None, uses self._temperature_limit. Otherwise uses the specified
            value to place an upper bound on the setpoint (C).
        """
        if temperature_limit is None: temperature_limit = self._temperature_limit
        
        if T > temperature_limit:
            print('Setpoint above the limit! Doing nothing.')
            return self.get_temperature_setpoint()
        
        if not self.simulation_mode:
            self.modbus.write_register(0x00, T, number_of_decimals=1, functioncode=6)
            return T
        self.simulation_setpoint = T
        return self.get_temperature_setpoint()