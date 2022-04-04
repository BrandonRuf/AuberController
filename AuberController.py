import mcphysics as _mp
import numpy as _n
import spinmob.egg as _egg
import traceback as _traceback
_p = _traceback.print_last
_g = _egg.gui
import spinmob as _s
import time as _time

_debug_enabled = False
_debug = _mp._debug

try: import serial as _serial
except: _serial = None

try: from serial.tools.list_ports import comports as _comports
except: _comports = None

def get_com_ports():
    """
    Returns a dictionary of port names as keys and descriptive names as values.
    """
    if _comports:

        ports = dict()
        for p in _comports(): ports[p.device] = p.description
        return ports

    else:
        raise Exception('You need to install pyserial and have Windows to use get_com_ports().')

def list_com_ports():
    """
    Prints a "nice" list of available COM ports.
    """
    ports = get_com_ports()

    # Empty dictionary is skipped.
    if ports:
        keys = list(ports.keys())
        keys.sort()
        print('Available Ports:')
        for key in keys:
            print(' ', key, ':', ports[key])

    else: raise Exception('No ports available. :(')

class serial_gui_base(_g.BaseObject):
    """
    Base class for creating a serial connection gui. Handles common controls.
    Parameters
    ----------
    api_class=None : class
        Class to use when connecting. For example, api_class=auber_syl53x2p_api would
        work. Note this is not an instance, but the class itself. An instance is
        created when you connect and stored in self.api.
    name='serial_gui' : str
        Unique name to give this instance, so that its settings will not
        collide with other egg objects.
    show=True : bool
        Whether to show the window after creating.
    block=False : bool
        Whether to block the console when showing the window.
    window_size=[1,1] : list
        Dimensions of the window.
    hide_address=False: bool
        Whether to show the address control for things like the Auber.
    """
    def __init__(self, api_class=None, name='serial_gui', show=True, block=False, window_size=[1,1], hide_address=False):

        # Remebmer the name.
        self.name = name

        # Checks periodically for the last exception
        self.timer_exceptions = _g.TimerExceptions()
        self.timer_exceptions.signal_new_exception.connect(self._new_exception)

        # Where the actual api will live after we connect.
        self.api = None
        self._api_class = api_class

        # GUI stuff
        self.window   = _g.Window(
            self.name, size=window_size, autosettings_path=name+'.window',
            event_close = self._window_close)
        
        # Top of GUI (Serial Communications)
        self.grid_top = self.window.place_object(_g.GridLayout(margins=False), alignment=0)
        self.window.new_autorow()
        
        # Middle of GUI (Numerical data readout)
        self.grid_mid = self.window.place_object(_g.GridLayout(margins=False), alignment=1,column_span=1)
        self.window.new_autorow()
        
        # Middle of GUI (Numerical data readout)
        self.grid_mid2 = self.window.place_object(_g.GridLayout(margins=False), alignment=1)
        self.window.new_autorow()
        
        self.grid_mode = self.window.place_object(_g.GridLayout(margins=False), alignment=1)
        self.window.new_autorow()
        
        # Bottom of GUI (Graphical data plotting) 
        self.grid_bot = self.window.place_object(_g.GridLayout(margins=False), alignment=0)

        # Get all the available ports
        self._label_port = self.grid_top.add(_g.Label('Port:'))
        self._ports = [] # Actual port names for connecting
        ports       = [] # Pretty port names for combo box
        if _comports:
            for p in _comports():
                self._ports.append(p.device)
                ports      .append(p.description)

        ports      .append('Simulation')
        self._ports.append('Simulation')
        self.combo_ports = self.grid_top.add(_g.ComboBox(ports, autosettings_path=name+'.combo_ports'))

        self.grid_top.add(_g.Label('Address:')).show(hide_address)
        self.number_address = self.grid_top.add(_g.NumberBox(
            0, 1, int=True,
            autosettings_path=name+'.number_address',
            tip='Address (not used for every instrument)')).set_width(40).show(hide_address)

        self.grid_top.add(_g.Label('Baud:'))
        self.combo_baudrates = self.grid_top.add(_g.ComboBox(
            ['1200', '2400', '4800', '9600', '19200'],
            default_index=3,
            autosettings_path=name+'.combo_baudrates'))

        self.grid_top.add(_g.Label('Timeout:'))
        self.number_timeout = self.grid_top.add(_g.NumberBox(2000, dec=True, bounds=(1, None), suffix=' ms', tip='How long to wait for an answer before giving up (ms).', autosettings_path=name+'.number_timeout')).set_width(100)

        # Button to connect
        self.button_connect  = self.grid_top.add(_g.Button('Connect', checkable=True))

        # Stretch remaining space
        self.grid_top.set_column_stretch(self.grid_top._auto_column)

        # Connect signals
        self.button_connect.signal_toggled.connect(self._button_connect_toggled)

        # Status
        self.label_status = self.grid_top.add(_g.Label(''))

        # By default the bottom grid is disabled
        self.grid_bot.disable()

        # Expand the bottom grid
        self.window.set_row_stretch(1)
        
        
        # Error
        self.grid_top.new_autorow()
        self.label_message = self.grid_top.add(_g.Label(''), column_span=10).set_colors('pink' if _s.settings['dark_theme_qt'] else 'red')

        # Other data
        self.t0 = None

        # Run the base object stuff and autoload settings
        _g.BaseObject.__init__(self, autosettings_path=name)

        # Show the window.
        if show: self.window.show(block)

    def _button_connect_toggled(self, *a):
        """
        Connect by creating the API.
        """
        if self._api_class is None:
            raise Exception('You need to specify an api_class when creating a serial GUI object.')

        # If we checked it, open the connection and start the timer.
        if self.button_connect.is_checked():
            port = self.get_selected_port()
            self.api = self._api_class(
                    port=port,
                    address=self.number_address.get_value(),
                    baudrate=int(self.combo_baudrates.get_text()),
                    timeout=self.number_timeout.get_value())

            # If we're in simulation mode
            if self.api.simulation_mode:
                #self.label_status.set_text('*** Simulation Mode ***')
                #self.label_status.set_colors('pink' if _s.settings['dark_theme_qt'] else 'red')
                self.button_connect.set_colors(background='pink')
            else:
                self.label_status.set_text('Connected').set_colors('teal' if _s.settings['dark_theme_qt'] else 'blue')

            # Record the time if it's not already there.
            if self.t0 is None: self.t0 = _time.time()

            # Enable the grid
            self.grid_bot.enable()

            # Disable other controls
            self.combo_baudrates.disable()
            self.combo_ports.disable()
            self.number_timeout.disable()

        # Otherwise, shut it down
        else:
            self.api.disconnect()
            self.label_status.set_text('')
            self.button_connect.set_colors()
            self.grid_bot.disable()

            # Enable other controls
            self.combo_baudrates.enable()
            self.combo_ports.enable()
            self.number_timeout.enable()


        # User function
        self._after_button_connect_toggled()

    def _after_button_connect_toggled(self):
        """
        Dummy function called after connecting.
        """
        return

    def _new_exception(self, a):
        """
        Just updates the status with the exception.
        """
        self.label_message(str(a)).set_colors('red')

    def _window_close(self):
        """
        Disconnects. When you close the window.
        """
        print('Window closed but not destroyed. Use show() to bring it back.')
        if self.button_connect():
            print('  Disconnecting...')
            self.button_connect(False)

    def get_selected_port(self):
        """
        Returns the actual port string from the combo box.
        """
        return self._ports[self.combo_ports.get_index()]


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
            _s._warn('You need to install pyserial and minimalmodbus to use the Auber SYL-53X2P.')
            self.modbus = None
            self.simulation_mode = True

        # Assume everything will work for now
        else: self.simulation_mode = False

        # If the port is "Simulation"
        if port=='Simulation': self.simulation_mode = True

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
        if self.simulation_mode: return 24.5
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
        return self.get_temperature_setpoint()


class auber_syl53x2p(serial_gui_base):
    """
    Graphical interface for the Auber SYL-53X2P temperature controller.
    Parameters
    ----------
    name='auber_syl53x2p' : str
        Unique name to give this instance, so that its settings will not
        collide with other egg objects.
    temperature_limit=450 : float
        Upper limit on the temperature setpoint (C).
    
    show=True : bool
        Whether to show the window after creating.
    block=False : bool
        Whether to block the console when showing the window.
    window_size=[1,1] : list
        Dimensions of the window.
    """
    def __init__(self, name='auber_syl53x2p', temperature_limit=500, show=True, block=False, window_size=[1,300]):
        if not _mp._minimalmodbus or not _mp._serial: _s._warn('You need to install pyserial and minimalmodbus to use the Auber SYL-53X2P.')

        # Remember the limit
        self._temperature_limit = temperature_limit
        

        # Run the base class stuff, which shows the window at the end.
        serial_gui_base.__init__(self, api_class=auber_syl53x2p_api, name=name, show=False, window_size=window_size)
        
        self.window.set_size([0,0])

        style_big_blue = 'font-size: 14pt; font-weight: bold; color: '+('mediumspringgreen' if _s.settings['dark_theme_qt'] else 'blue')
        style_big_red  = 'font-size: 17pt; font-weight: bold; color: '+('white' if _s.settings['dark_theme_qt'] else 'red')
        style_big      = 'font-size: 17pt; font-weight: bold; color: '+('cyan' if _s.settings['dark_theme_qt'] else 'purple')

        self.grid_mid.add(_g.Label('Measured Temperature:'), alignment=1).set_style(style_big_red)
        
        self.number_temperature = self.grid_mid.add(_g.NumberBox(
            value=-273.16, suffix='°C', tip='Last recorded temperature value.'
            ),alignment=1).set_width(175).disable().set_style(style_big_red)
        
        self.grid_mid.new_autorow()

        # Add GUI stuff to the bottom grid
        self.grid_mid.add(_g.Label('Setpoint Temperature:'), alignment=1).set_style(style_big)

        self.number_setpoint = self.grid_mid.add(_g.NumberBox(
            -273.16, bounds=(-273.16, temperature_limit), suffix='°C',
            signal_changed=self._number_setpoint_changed
            )).set_width(175).set_style(style_big).disable()
        
        self.label_temperature_status = self.grid_mid.add(_g.Label(
            ''), column = 2, row_span=2).set_style(style_big)
        
        ## Add mode buttons to GUI (open and closed loop control modes)
        self.grid_mode.add(_g.Label('Mode:')).set_style('color: azure')
        
        # Open loop (manual) control mode activation button
        self.button_single  = self.grid_mode.add(_g.Button('Single Setpoint' ,checkable=True, tip='Enable manual temperature control.')).disable()
        self.button_single.signal_toggled.connect(self._button_single_setpoint_toggled)
        
        # Closed loop control mode activation button
        self.button_multi = self.grid_mode.add(_g.Button('Multi Setpoint',checkable=True, tip='Enable PID temperature control.')).disable()
        self.button_multi.signal_toggled.connect(self._button_multi_toggled)
        
        self.tabs = self.grid_bot.add(_g.TabArea(self.name+'.tabs'), alignment=0,column_span=10)
        
        self.tab_main  = self.tabs.add_tab('Main')


        self.plot = self.tab_main.add(_g.DataboxPlot(
            file_type='*.csv',
            autosettings_path=name+'.plot',
            delimiter=',', show_logger=True), alignment=0, column_span=10)
        
                # Timer for collecting data
        self.timer = _g.Timer(interval_ms=1000, single_shot=False)
        self.timer.signal_tick.connect(self._timer_tick)

        # Bottom log file controls
        self.tab_main.new_autorow()

        # Finally show it.
        self.window.show(block)
        
        #self.tabs1 = self.grid_bot.add(_g.TabArea(self.name+'.tabs'), alignment=0,column_span=10,column = 0, row=2)
        self.tab_program = self.tabs.add_tab('Program')
        self.tab_program.disable()
        a = self.tabs.pop_tab(1)
        a.hide()
        
        self.program = dict()
        
        self.tab_program.add(_g.Label('Program:'),alignment=1).set_width(120).set_style('font-size: 12pt; font-weight: bold; color: lavender')
        
        self.combo_program = self.tab_program.add(_g.ComboBox(['Custom']+list(programss.keys())),alignment=1).set_width(150).set_style('font-size: 12pt; font-weight: bold; color: lavender')
        self.combo_program.signal_changed.connect(self._program_changed)
        
        
        self.button_run = self.tab_program.add(_g.Button('Run', checkable=True).set_height(27))
        self.button_run.signal_toggled.connect(self._button_run_toggled)
        
        self.tab_program.new_autorow()
        
        for i in range(10):
            self.program[i] = dict()      
            self.tab_program.add(_g.Label('Step %d:'%i),alignment=1).set_width(120).set_style('font-size: 12pt; font-weight: bold; color: pink')
            #self.tab_program.add(_g.Label('Operation:'),alignment=1).set_width(100).set_style('font-size: 12pt; font-weight: bold; color: gold')
            self.program[i]['operation']   = self.tab_program.add(_g.ComboBox(["--","Ramp","Soak"]),alignment=1).set_width(125).set_style('font-size: 12pt; font-weight: bold; color: paleturquoise')
            self.tab_program.add(_g.Label('Temperature:'),alignment=1).set_style('font-size: 12pt; font-weight: bold; color: cyan')
            self.program[i]['temperature'] = self.tab_program.add(_g.NumberBox(24.5, bounds=(-273.16, temperature_limit), suffix='°C'),alignment=1).set_width(125).set_style('font-size: 12pt; font-weight: bold; color: cyan')
            self.tab_program.add(_g.Label('Duration:'),alignment=1).set_style('font-size: 12pt; font-weight: bold; color: gold')
            self.program[i]['time']        = self.tab_program.add(_g.NumberBox(2.50, bounds=(0,1000.), suffix='h'),alignment=1).set_width(75).set_style('font-size: 12pt; font-weight: bold; color: gold')
            self.tab_program.new_autorow()
            self.tab_program.set_row_stretch(row=i+1,stretch=0)
            
            self.tab_program.set_column_stretch(column=1,stretch=0)

            self.program_mode = False        
    
    def _program_changed(self):
        
        if self.combo_program.get_text() == "Custom":
            for i in range(10):
                self.program[i]['operation']  .enable()
                self.program[i]['temperature'].enable()
                self.program[i]['time']       .enable()
                
                self.program[i]['operation']  .set_value(0)
                self.program[i]['temperature'].set_value(25.4)
                self.program[i]['time']       .set_value(2.5)
        else:    
            _program_name = self.combo_program.get_text()
            _program =  programss[_program_name]
            
            for i in range(len(list(_program))):
                s = _program[i]
                if s[0] == "--":
                    self.program[i]['operation']  .set_value(0)
                elif s[0] == "Ramp":
                    self.program[i]['operation']  .set_value(1)            
                elif s[0] == "Soak":
                    self.program[i]['operation']  .set_value(2)
                
                self.program[i]['temperature'].set_value(s[1])
                self.program[i]['time']       .set_value(s[2])
                
                self.program[i]['operation']  .disable()
                self.program[i]['temperature'].disable()
                self.program[i]['time']       .disable()
            
            for i in range(len(list(_program)),10):
                self.program[i]['operation']  .set_value(0)
                self.program[i]['temperature'].set_value(25.4)
                self.program[i]['time']       .set_value(2.5)
                
                self.program[i]['operation']  .disable()
                self.program[i]['temperature'].disable()
                self.program[i]['time']       .disable()
                
            s = _program[0]
            self.program_running.set_value(_program_name)
            self.operation.set_value(s[0])
            self.step_duration.set_value(s[2]*3600)
            self.program_time.set_value(s[2]*3600)
            
    
    def _button_run_toggled(self):
        if self.button_run.is_checked():
            self.button_run.set_colors(text = 'white', background="mediumspringgreen")
        else:
            self.button_run.set_colors(text = "",background="")

    def _button_multi_toggled(self):
        
        if self.button_single.is_checked(): self.button_single.click()
        
        if self.button_multi.is_checked():
        
            if(self.program_mode == False):
                #self.grid_mid2.new_autorow()
                
                style_big_blue = 'font-size: 14pt; font-weight: bold; color: '+('mediumspringgreen' if _s.settings['dark_theme_qt'] else 'blue')
                style_big_red  = 'font-size: 17pt; font-weight: bold; color: '+('white' if _s.settings['dark_theme_qt'] else 'red')
                style_big      = 'font-size: 17pt; font-weight: bold; color: '+('cyan' if _s.settings['dark_theme_qt'] else 'purple')
                
                #self.grid_mid2.add(_g.Label('Program:'),alignment=1).set_style(style_big_blue)
                #self.program = self.grid_mid2.add(_g.NumberBox(1),alignment=1).set_width(100).set_style(style_big_blue).disable()
                
                self.grid_mid2.add(_g.Label('Program:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: lavender')
                self.program_running = self.grid_mid2.add(_g.TextBox(self.combo_program.get_text()),alignment=0).set_width(150).set_style('font-size: 14pt; font-weight: bold; color: lavender').disable()
                

                self.grid_mid2.add(_g.Label('Duration:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: gold')
                self.step_duration = self.grid_mid2.add(_g.NumberBox(3600, suffix = 's'),alignment=1).set_width(100).set_style('font-size: 14pt; font-weight: bold; color: gold').disable()
                
                self.grid_mid2.new_autorow()
                
                self.grid_mid2.add(_g.Label('Step:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: pink')
                self.step_number = self.grid_mid2.add(_g.TextBox("1/10"),alignment=0).set_width(80).set_style('font-size: 14pt; font-weight: bold; color: pink').disable()
                
                
                self.grid_mid2.add(_g.Label('Operation:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: paleturquoise')
                self.operation = self.grid_mid2.add(_g.TextBox("Hold"),alignment=0).set_width(80).set_style('font-size: 14pt; font-weight: bold; color: paleturquoise').disable()
                
                #self.grid_mid2.new_autorow()
                
                self.grid_mid2.add(_g.Label('Time:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: coral')
                self.program_time = self.grid_mid2.add(_g.NumberBox(1102, suffix = 's'),alignment=1).set_width(100).set_style('font-size: 14pt; font-weight: bold; color: coral').disable()
                
                self.program_mode = True
                
                # Bring the hidden program tab into the GUI
                self.tabs.unpop_tab(1)
                
            self.tab_program.enable()
            self.button_multi.set_colors(text = 'white',background='limegreen')
        
        else:
            self.button_multi.set_colors(text = "",background="")
            self.tab_program.disable()  

    def _button_single_setpoint_toggled(self):
        if self.button_multi.is_checked(): self.button_multi.click()
        
        if self.button_single.is_checked():
            self.number_setpoint.enable()
            self.button_single.set_colors(text = 'white',background='red')
        else:
            self.number_setpoint.disable()
            self.button_single.set_colors(text = "",background="")
    
    def _number_setpoint_changed(self, *a):
        """
        Called when someone changes the number.
        """
        # Set the temperature setpoint
        self.api.set_temperature_setpoint(self.number_setpoint.get_value(), self._temperature_limit)

    def _timer_tick(self, *a):
        """
        Called whenever the timer ticks. Let's update the plot and save the latest data.
        """
        # Get the time, temperature, and setpoint
        t = _time.time()-self.t0
        T = self.api.get_temperature()
        S = self.api.get_temperature_setpoint()
        P = self.api.get_main_output_power()
        self.number_setpoint.set_value(S, block_signals=True)

        # Append this to the databox
        self.plot.append_row([t, T, S, P], ckeys=['Time (s)', 'Temperature (C)', 'Setpoint (C)', 'Power (%)'])
        self.plot.plot()

        if self.button_run.is_checked():
            self.program_time.set_value(self.program_time.get_value()-1)
        # Update the big red text.
        self.number_temperature(T)
        self.label_temperature_status.set_text('')
        self.window.process_events()

    def _after_button_connect_toggled(self):
        """
        Called after the connection or disconnection routine.
        """
        if self.button_connect.is_checked():

            # Get the setpoint
            try:
                self.number_setpoint.set_value(self.api.get_temperature_setpoint(), block_signals=True)
                self.timer.start()
                
                # Enable mode buttons
                self.button_single.enable()
                self.button_multi.enable()
            except:
                self.number_setpoint.set_value(0)
                self.button_connect.set_checked(False)
                self.label_status.set_text('Could not get temperature.').set_colors('pink' if _s.settings['dark_theme_qt'] else 'red')
        
        # Disconnected
        else:
            self.label_temperature_status('(disconnected)')
            self.timer.stop()
            
            # Disable mode buttons
            self.button_single.disable()
            self.button_multi.disable()
        
        
programss = dict()        
        
def program(name, operation):
    if name in programss.keys():
        myprogram = programss[name]
        numbers = list(myprogram)
        myprogram[numbers[-1]+1] = operation
    else:
        programss[name] = dict()
        programss[name][0] = operation


program("YBa2Cu3O7-x",['Ramp',950, 0.1])
program("YBa2Cu3O7-x",['Soak',950, 2])
program("YBa2Cu3O7-x",['Ramp',800, 2])
program("YBa2Cu3O7-x",['Ramp',300, 10])
program("YBa2Cu3O7-x",['Ramp',25, 4])

program("GaAs",['Ramp', 550, 1.02])
program("GaAs",["Soak", 550, .3])
program("GaAs",["Ramp", 250, 2.1])
program("GaAs",["Ramp", 25, 5])

program("(δ-phase) Pu-Ga",['Ramp', 639.4, 1])
program("(δ-phase) Pu-Ga",["Soak", 639.4, .3])
program("(δ-phase) Pu-Ga",["Ramp", 25, 1])
                 

if __name__ == '__main__':
    _egg.clear_egg_settings()
    self = auber_syl53x2p(name = "Oven Controller #1",temperature_limit = 1500)

