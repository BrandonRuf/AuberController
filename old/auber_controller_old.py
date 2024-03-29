import spinmob.egg as _egg
import traceback as _traceback
_p = _traceback.print_last
_g = _egg.gui
import spinmob as _s
import time as _time
import json

import serial as _serial
from serial.tools.list_ports import comports as _comports
from auber_controller_api import auber_syl53x2p_api

# Dark theme
_s.settings['dark_theme_qt'] = True

style_1 = 'font-size: 14pt; font-weight: bold; color: '+('mediumspringgreen' if _s.settings['dark_theme_qt'] else 'blue')
style_2 = 'font-size: 17pt; font-weight: bold; color: '+('white'             if _s.settings['dark_theme_qt'] else 'red')
style_3 = 'font-size: 17pt; font-weight: bold; color: '+('cyan'              if _s.settings['dark_theme_qt'] else 'purple')



try: 
    with open('program_list.json') as f:
        program_set = json.load(f) 
except:
    print("No existing program list.")
    program_set = dict() 

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
        
        # Middle of GUI (Basic numerical data readout)
        self.grid_mid = self.window.place_object(_g.GridLayout(margins=False), alignment=1,column_span=1)
        self.window.new_autorow()
        
        #
        self.grid_program = self.window.place_object(_g.GridLayout(margins=False), alignment=1)
        self.window.new_autorow()
        
        #
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
        
        # Append simulation port
        ports      .append('Simulation')
        self._ports.append('Simulation')
        
        # Append refresh port
        ports      .append('Refresh - Update Ports List')
        self._ports.append('Refresh - Update Ports List')
        
        self.combo_ports = self.grid_top.add(_g.ComboBox(ports, autosettings_path=name+'.combo_ports'))
        self.combo_ports.signal_changed.connect(self._ports_changed)

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
    
    def _ports_changed(self):
        """
        Refreshes the list of availible serial ports in the GUI.

        """
        if self.get_selected_port() == 'Refresh - Update Ports List':
            
            len_ports = len(self.combo_ports.get_all_items())
            
            # Clear existing ports
            if(len_ports > 1): # Stop recursion!
                for n in range(len_ports):
                    self.combo_ports.remove_item(0)
            else:
                return
                self.combo_ports.remove_item(0)
                 
            self._ports = [] # Actual port names for connecting
            ports       = [] # Pretty port names for combo box
                
            default_port = 0
             
            # Get all the available ports
            if _comports:
                for inx, p in enumerate(_comports()):
                    self._ports.append(p.device)
                    ports      .append(p.description)
                    
                    if 'Arduino' in p.description:
                        default_port = inx
                        
            # Append simulation port
            ports      .append('Simulation')
            self._ports.append('Simulation')
            
            # Append refresh port
            ports      .append('Refresh - Update Ports List')
            self._ports.append('Refresh - Update Ports List')
             
            # Add the new list of ports
            for item in ports:
                self.combo_ports.add_item(item)
             
            # Set the new default port
            self.combo_ports.set_index(default_port)
    
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

            # Disable serial controls
            self.combo_baudrates.disable()
            self.combo_ports    .disable()
            self.number_timeout .disable()

        # Otherwise, shut it down
        else:
            self.api.disconnect()
            self.label_status.set_text('')
            self.button_connect.set_colors()
            self.grid_bot.disable()

            # Enable serial controls
            self.combo_baudrates.enable()
            self.combo_ports    .enable()
            self.number_timeout .enable()


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

        # Remember the limit
        self._temperature_limit = temperature_limit

        # Run the base class stuff, which shows the window at the end.
        serial_gui_base.__init__(self, api_class=auber_syl53x2p_api, name=name, show=False, window_size=window_size)
        
        self.window.set_size([0,0])
        
        # Add NumberBox for the current measured temperature from the Auber
        self.grid_mid.add(_g.Label('Measured Temperature:'), alignment=1).set_style(style_2)
        
        self.number_temperature = self.grid_mid.add(_g.NumberBox(
            value=-273.16, suffix='°C', tip='Last recorded temperature value.'),
            alignment=1).set_width(175).disable().set_style(style_2)
        
        # New row
        self.grid_mid.new_autorow()

        # Add NumberBox of the Auber's current setpoint temperature 
        self.grid_mid.add(_g.Label('Setpoint Temperature:'), alignment=1).set_style('font-size: 17pt; font-weight: bold; color: cyan')

        self.number_setpoint = self.grid_mid.add(_g.NumberBox(
            -273.16, bounds=(-273.16, temperature_limit), suffix='°C',
            signal_changed=self._number_setpoint_changed)
            ).set_width(175).set_style('font-size: 17pt; font-weight: bold; color: cyan').disable()
        
        self.label_temperature_status = self.grid_mid.add(_g.Label(
            ''), column = 2, row_span=2).set_style(style_3)  
        
        # Add a tabs section in the bottom grid
        self.tabs = self.grid_bot.add(_g.TabArea(self.name+'.tabs'), alignment=0,column_span=10)
        
        # Create main tab
        self.tab_main  = self.tabs.add_tab('Main')

        # Add data plotting to main tab
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
        
        # Create a new tab to hold program setpoint control
        self.tab_program = self.tabs.add_tab('Program')
        
        # Pop tab from the main GUI
        poped_tab = self.tabs.pop_tab(1)
        poped_tab.hide()
        
        # Top grid of the "Program" tab
        self.tab_program_top = self.tab_program.place_object(_g.GridLayout(margins=False))
        
        # Add program selector
        self.tab_program_top.add(_g.Label('Program:'),alignment=1).set_width(120).set_style('font-size: 12pt; font-weight: bold; color: lavender')
        
        self.combo_program = self.tab_program_top.add(_g.ComboBox(['Custom']+list(program_set.keys())),alignment=1).set_width(150).set_style('font-size: 12pt; font-weight: bold; color: lavender')
        self.combo_program.signal_changed.connect(self._combo_program_changed)
        
        # Add "Run" button for program activation
        self.button_run = self.tab_program_top.add(_g.Button('Run', checkable=True).set_height(27))
        self.button_run.signal_toggled.connect(self._button_run_toggled)
        
        
        # New row
        self.tab_program.new_autorow()
        
        # Bottom grid of the "Program" tab
        self.tab_program_bot = self.tab_program.place_object(_g.GridLayout(margins=False))
        
        # Dictionary for holding program information
        self.program = dict()
        
        # Create 10 program steps 
        for i in range(10):
            self.program[i] = dict()      
            
            self.tab_program_bot.add(_g.Label('Step %d:'%i),alignment=0).set_width(120).set_style('font-size: 12pt; font-weight: bold; color: pink')
            self.program[i]['operation']   = self.tab_program_bot.add(_g.ComboBox(["--","Ramp","Soak"]),alignment = 0).set_width(125).set_style('font-size: 12pt; font-weight: bold; color: paleturquoise')
            
            self.tab_program_bot.add(_g.Label('Temperature:'),alignment=0).set_style('font-size: 12pt; font-weight: bold; color: cyan')
            self.program[i]['temperature'] = self.tab_program_bot.add(_g.NumberBox(24.5, bounds=(-273.16, temperature_limit), suffix='°C'),alignment=0).set_width(100).set_style('font-size: 12pt; font-weight: bold; color: cyan')
            
            self.tab_program_bot.add(_g.Label('Duration:'),alignment=2).set_style('font-size: 12pt; font-weight: bold; color: gold')
            self.program[i]['time']        = self.tab_program_bot.add(_g.NumberBox(200.5, bounds=(0,1000.), suffix='h'),alignment=2).set_width(100).set_style('font-size: 12pt; font-weight: bold; color: gold')
            
            if i < 9: self.tab_program_bot.new_autorow()

        
        self.grid_program.add(_g.Label('Program:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: lavender')
        self.program_running = self.grid_program.add(_g.TextBox(self.combo_program.get_text()),alignment=0).set_width(150).set_style('font-size: 14pt; font-weight: bold; color: lavender').disable()
        
        
        self.grid_program.add(_g.Label('Progress:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: gold')
        self.program_progress = self.grid_program.add(_g.TextBox("0%"),alignment=1).set_width(100).set_style('font-size: 14pt; font-weight: bold; color: gold').disable()
        
        self.grid_program.new_autorow()
        
        self.grid_program.add(_g.Label('Step:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: pink')
        self.step_number = self.grid_program.add(_g.TextBox("1/10"),alignment=0).set_width(70).set_style('font-size: 14pt; font-weight: bold; color: pink').disable()
        
        self.grid_program.add(_g.Label('Operation:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: paleturquoise')
        self.operation = self.grid_program.add(_g.TextBox("Hold"),alignment=0).set_width(100).set_style('font-size: 14pt; font-weight: bold; color: paleturquoise').disable()
        
        self.grid_program.add(_g.Label('Time:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: coral')
        self.program_time = self.grid_program.add(_g.NumberBox(1102,decimals = 4, suffix = 's',),alignment=1).set_width(130).set_style('font-size: 14pt; font-weight: bold; color: coral').disable()
        
    def _combo_program_changed(self):
        "Called when the program selector tab is changed"
                
        self.step_time  = 0
        
        _program_name = self.combo_program.get_text()
        
        if  _program_name == "Custom":
            for i in range(10):
                self.program[i]['operation']  .enable()
                self.program[i]['temperature'].enable()
                self.program[i]['time']       .enable()
                
                self.program[i]['operation']  .set_value(0)
                self.program[i]['temperature'].set_value(24)
                self.program[i]['time']       .set_value(200.5)
            
            # Enable the program text box
            self.program_running.enable()
        else:    
            # Load in the selected program
            self.loaded_program = program(_program_name)
            
            # Setup all the program steps being used
            for i in range(self.loaded_program.get_size()):
                
                # Get next program step
                step = self.loaded_program.get_step(i)
                
                if   step[0] == "--"   : self.program[i]['operation']  .set_value(0)
                elif step[0] == "Ramp" : self.program[i]['operation']  .set_value(1)            
                elif step[0] == "Soak" : self.program[i]['operation']  .set_value(2)
                
                self.program[i]['temperature'].set_value(step[1])
                self.program[i]['time']       .set_value(step[2])
                
            # Blank all the program steps not being used
            for i in range(self.loaded_program.get_size(),10):
                self.program[i]['operation']  .set_value(0)
                self.program[i]['temperature'].set_value(25.4)
                self.program[i]['time']       .set_value(2.5)
            
            # Disable all user input for the program steps
            for i in range(10):
                self.program[i]['operation']  .disable()
                self.program[i]['temperature'].disable()
                self.program[i]['time']       .disable()
            
            # 
            if self.loaded_program.get_operation() == 'Ramp': 
                self.dT        = self.loaded_program.get_temperature() - self.api.get_temperature()
                self.step_time = self.loaded_program.get_duration()*3600 / ((self.dT) * 10.0)
            
            # Update the GUI data boxes with the current program info
            self.step_number    .set_value("1/%d"%self.loaded_program.get_size())
            self.operation      .set_value(self.loaded_program.get_operation())
            self.program_time   .set_value(self.loaded_program.get_duration()*3600)
            
            # Disable the program text box
            self.program_running.disable()
        
        # Set the program name in the GUI
        self.program_running.set_value(_program_name)
               
    def _button_run_toggled(self):
        if self.button_run.is_checked():
            
            # Turn the "Run" button green to show that the program is running
            self.button_run.set_colors(text = 'white', background="mediumspringgreen")
            
            # Disable the program selector
            self.combo_program.disable()
            
            # Time of program start
            self.t1 = _time.time()
            
            #
            self.t_next = self.step_time
            
        else:
            # Reset the "Run" button colors
            self.button_run.set_colors(text = '', background = '')
            
            # Re-enable the program selector
            self.combo_program.enable()
    
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
        
        # Append this to the databox
        self.plot.append_row([t, T, S, P], ckeys=['Time (s)', 'Temperature (C)', 'Setpoint (C)', 'Power (%)'])
        self.plot.plot()

        #
        self._program_increment(T,S)
                
                
        # Update the temperature data box
        self.number_temperature(T)
        
        # 
        self.label_temperature_status.set_text('')
        
        # Update the GUI
        self.window.process_events()
    
    def _program_increment(self, T, S):
        
        if self.button_run.is_checked():
            
            # Calculate time since program step has started
            t2 = _time.time() - self.t1
            
            
            if self.program_time.get_value()- t2 > 0:
                
                self.program_time.set_value(self.loaded_program.get_duration()*3600-t2)
                self._increment_temperature(T, S, t2)
                
                # Update the program progress counter in the GUI
                self.program_progress.set_value("%.2f %%"%(100*t2/self.loaded_program.get_length()))
                   
            elif self.loaded_program.check_next():
                
                # Move to the next program step
                self.loaded_program.increment_step()
                
                # Get a new time reference for the start of the step
                self.t1 = _time.time()
                
                # Update the step number in the GUI
                self.step_number.set_value( "%d/%d"%(self.loaded_program.get_step_index(),self.loaded_program.get_size()) )
                
                # Update the step time in the GUI
                self.program_time.set_value(self.loaded_program.get_duration()*3600)
                
                if self.loaded_program.get_operation() == "Ramp":
                    self.operation.set_value("Ramp")
                    
                    self.dT = self.loaded_program.get_temperature() - T
                    self.step_time =  self.loaded_program.get_duration()*3600 / (self.dT * 10.0)
            
                else:
                    self.operation.set_value("Soak")
                    
                # Update the program progress counter in the GUI
                self.program_progress.set_value("%.2f %%"%(100*t2/self.loaded_program_length))
                
    def _increment_temperature(self, T, S, t2):
        
        if self.loaded_program.get_operation()== "Ramp":
            
            if(t2 > self.t_next):
                self.number_setpoint.set_value(S+.1)
                self.t_next = self.t_next + self.step_time
        else:
            self.number_setpoint.set_value(self.loaded_program.get_temperature())
         
    def _after_button_connect_toggled(self):
        """
        Called after the connection or disconnection routine.
        """
        if self.button_connect.is_checked():

            # Get the setpoint
            try:
                self.number_setpoint.set_value(self.api.get_temperature_setpoint(), block_signals=True)
                self.program_running.enable()
                self.timer.start()
                
                # Bring the hidden program tab into the GUI
                if 1 in self.tabs.popped_tabs: self.tabs.unpop_tab(1)
                
            except:
                self.number_setpoint.set_value(0)
                self.button_connect.set_checked(False)
                self.label_status.set_text('Could not get temperature.').set_colors('pink' if _s.settings['dark_theme_qt'] else 'red')
        
        # Disconnected
        else:
            self.label_temperature_status('(disconnected)')
            self.timer.stop()
        
class program():
    def __init__(self, name):
        self.name  = name
        self.steps = program_set[name]
        
        self.loaded_step = self.steps[0]
        self.loaded_step_index = 0
        self.size = len(self.steps)
        self.length = 0
        
        for i in range(self.size):
                            
            # Add the length of this step to the total program length
            self.length += self.steps[i][2]*3600
    
    def get_operation(self):
        return self.loaded_step[0]
    
    def get_temperature(self):
        return self.loaded_step[1]
    
    def get_duration(self):
        return self.loaded_step[2]
    
    def get_size(self):
        return self.size
    
    def increment_step(self):
        self.loaded_step = self.steps[self.loaded_step_index+1]
        self.loaded_step_index += 1
        
    def get_step(self,i):
        return self.steps[i]
    
    def get_length(self):
        return self.length  
    
    def get_step_index(self):
        return self.loaded_step_index
    
    def check_next(self):
        if self.loaded_step_index < self.size - 1:
            return True
        else:
            return False

if __name__ == '__main__':
    _egg.clear_egg_settings()
    self = auber_syl53x2p(name = "Domenic's Oven Controller #1",temperature_limit = 1500)

