"""
A graphical user interface for controlling the Auber SYL53X2P temperature controller,
encorporating creation of complex (up to 10 ramping/soaking steps) programs. 
 
Written by Brandon Ruffolo (2022).
See https://github.com/BrandonRuf/AuberController for updated versions of this software.
Email brandon.ruffolo@mcgill.ca with any software issues/bugs or suggestions.

"""

import spinmob.egg   as _egg
import spinmob       as _s
import time          as _time
import os            as _os
import serial        as _serial

_g = _egg.gui

from serial.tools.list_ports  import comports as _comports
from auber_controller_api     import auber_syl53x2p_api
from auber_controller_program import program

# GUI settings
_s.settings['dark_theme_qt'] = True

# 
PROGRAM_STEPS = 10
PROGRAM_DIR   = 'Programs'


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
            1, 1, int=True,
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
                             
            # Get all the available ports
            if _comports:
                for inx, p in enumerate(_comports()):
                    self._ports.append(p.device)
                    ports      .append(p.description)
    
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
            self.combo_ports.set_index(0)
    
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

            # Record the time
            self.t0 = _time.time()

            # Enable the grid
            self.grid_bot.enable()

            # Disable serial controls
            self.combo_baudrates.disable()
            self.combo_ports    .disable()
            self.number_timeout .disable()
            
            
            if self.api.simulation_mode:
                self.combo_ports.set_value(len(self._ports)-2)
                self.button_connect.set_text("Simulation").set_colors(background='pink')
            else:
                self.button_connect.set_text('Disconnect').set_colors(background = 'blue')

        # Otherwise, shut it down
        else:
            self.api.disconnect()
            self.button_connect.set_colors()
            self.grid_bot.disable()

            # Enable serial controls
            self.combo_baudrates.enable()
            self.combo_ports    .enable()
            self.number_timeout .enable()
            
            self.button_connect.set_text('Connect').set_colors(background = '')


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
        
        # Dictionary holding the full set of programs
        self.program_set = dict()
        
        # Load in all programs
        self.get_program_set()
        
        # Dictionary for holding program information
        self.program = dict()
        
        # Build the GUI
        self.setup_gui_components(name)
        
        # Set the loaded program to custom (user supplied by default)
        self.loaded_program = program("Custom", None)
        
        # Finally show it.
        self.window.show(block)
     
        
    def _combo_program_changed(self):
        """
        Called when the program selector tab is changed.
        """
        
        # Get the program name
        _program_name = self.combo_program.get_text()
        
        # Update the program name in the GUI
        self._update_program(_program_name)
        
        # Handle the "Custom" program selection individually
        if  _program_name == "Custom":
            
            # Enable in all program step tabs and fill them with dummy values
            for i in range(PROGRAM_STEPS):
                self.program[i]['operation']  .enable()
                self.program[i]['temperature'].enable()
                self.program[i]['time']       .enable()
                
                self.program[i]['operation']  .set_value(0)
                self.program[i]['temperature'].set_value(24)
                self.program[i]['time']       .set_value(200.5)
            
            # Make sure the run button is disabled so that a run cannot be 
            # started with invalid operations
            self.button_run.disable()
            
        else:    
            # Load in the selected program
            self.loaded_program = program(_program_name, self.program_set)
            
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
                
            # Save first step parameters
            self.step_duration  = self.loaded_program.get_step_duration ()*3600
            self.step_operation = self.loaded_program.get_step_operation()
            
            # Update the GUI data boxes with the current program info
            self._update_step(1)
            self._update_operation(self.step_operation)
            self._update_step_time(self.step_duration)
            
            
    def _check_program_validity(self):
        """
        Enables the run button if a valid program is present.
        The save button is additionally enabled if a valid custom
        program is present. 
        """
        
        # Check if the first operation has been set 
        if self.program[0]['operation'].get_text() != '--':
            
            # Enable the run button if a valid first program operation is present
            self.button_run .enable()
            
            # Enable the save button if the run is custom
            if self.textbox_program.get_text() == "Custom": self.button_save.enable()
            else:                                           self.button_save.disable()
        else:
            # Disable the run and save buttons if the first program operation is not set            
            self.button_run .disable()
            self.button_save.disable()
    
    
    def _button_run_toggled(self):
        """
        Called when the run button is toggled.
        """
        
        if self.button_run.is_checked():
            
            # Clear the temperature plot 
            self.plot.clear()
            
            # Reload non-custom programs
            if self.combo_program.get_text() != "Custom":
                self._combo_program_changed()
            
            # Turn the "Run" button green to show that the program is running
            self.button_run.set_colors(text = 'limegreen', background='white')
            
            # Disable the program selector
            self.combo_program.disable()
            
            # Disable setpoint numberbox
            self.number_setpoint.disable()
            
            # Time of program start
            self.time = _time.time()
            self.t0   = self.time
            
            # Define program run time - time the current program has been running
            self.t_program = 0
            
            # Define program step time - time the current program STEP has been running
            self.t_step    = 0 
            
            # Update status label
            self.label_program_status.set_text("(Running)").set_style('font-size: 17pt; font-weight: bold; color: '+('mediumspringgreen'))
            
            # If the program is new (custom), set it up
            if self.textbox_program.get_text() == "Custom":
                
                # Create new program
                self.loaded_program = program("Custom", None)
                
                # Upload all program steps
                for i in range(PROGRAM_STEPS):
                    operation = self.program[i]['operation'].get_value()
                    
                    if operation != 0:
                        new_step = []
                        
                        if   operation == 1: new_step.append("Ramp")
                        elif operation == 2: new_step.append("Soak")
                        
                        new_step.append(self.program[i]['temperature'].get_value())
                        new_step.append(self.program[i]['time'].get_value())
                        
                        self.loaded_program.add_step(new_step)
                    else: break
                
                # Save first step parameters
                self.step_duration  = self.loaded_program.get_step_duration ()*3600
                self.step_operation = self.loaded_program.get_step_operation()
                
                # Update the GUI data boxes with the current program info
                self._update_step(1)
                self._update_operation(self.step_operation)
                self._update_step_time(self.step_duration)
                self._update_progress()
                    
            # Run the loaded program
            self.step_time, self.t_next, self.T_start, self.T_stop = self.loaded_program.run(self.api.get_temperature())
            self.T_current = self.T_start
            
        else:
            # Reset the "Run" button colors
            self.button_run.set_colors(text = '', background = '')
            
            # Re-enable the program selector
            self.combo_program.enable()
            
            # Re-enable setpoint numberbox
            self.number_setpoint.enable()
            
            # Update status to show controller is Idle
            self.label_program_status.set_text("(Idle)").set_style('font-size: 17pt; font-weight: bold; color: '+('grey'))
    
    
    def _button_save_toggled(self):
        """
        Called when the save button is toggled.
        
        This will save an entered program outside of python, 
        so that it will be availible every time the controller is opened.
        """
        
        # Create a new program
        self.loaded_program = program("Custom", None)
        
        # Get the program steps
        for i in range(PROGRAM_STEPS):
            operation = self.program[i]['operation'].get_value()
            
            if operation != 0:
                new_step = []
                
                if   operation == 1: new_step.append("Ramp")
                elif operation == 2: new_step.append("Soak")
                
                new_step.append(self.program[i]['temperature'].get_value())
                new_step.append(self.program[i]['time'].get_value())
                
                self.loaded_program.add_step(new_step)
            else: break
        
        # Save the program
        name = self.loaded_program.save_program()
        
        # Load in the new program set (that includes the newly saved program)
        self.get_program_set()
        
        # Update the program selector tab
        self._update_combo_program()
        
        # Set the program selector to our new program
        self.combo_program.set_index(index = list(self.program_set.keys()).index(name)+1 )
        
        
    def _after_button_connect_toggled(self):
        """
        Called after the connection or disconnection routine.
        """
        if self.button_connect.is_checked():
            
            try:
                # Get the setpoint
                self.number_setpoint.set_value(self.api.get_temperature_setpoint(), block_signals=True)
                
                # Enable the setpoint NumberBox
                self.number_setpoint.enable()
                
                # Clear the plot (in case anything was previously there)
                self.plot.clear()
                
                # Start the timer
                self.timer.start()
                
                # Bring the hidden program tab into the GUI
                if 1 in self.tabs.popped_tabs: self.tabs.unpop_tab(1)
                
                # Update the program status
                self.label_program_status.set_text("(Idle)")
                
            # Failure to retrieve setpoint
            except:
                self.number_setpoint.set_value(0)
                
                # Disconnect
                self.button_connect.set_checked(False)
                
                # Update the program status
                self.label_program_status.set_text("(Error)").set_style('font-size: 17pt; font-weight: bold; color: '+('orangered'))
                #self.label_status.set_text('Could not get temperature.').set_colors('pink' if _s.settings['dark_theme_qt'] else 'red')
        
        # Disconnected
        else:
            self.label_program_status.set_text("(Disconnected)")
            
            if self.button_run.is_checked(): self.button_run.click()
            
            # Disable the setpoint NumberBox
            self.number_setpoint.disable()
            
            # Stop the timer
            self.timer.stop()
    
    
    def _number_setpoint_changed(self, *a):
        """
        Called when someone changes the temperature setpoint (when a program is not running).
        """
        # Set the temperature setpoint on the Auber
        self.api.set_temperature_setpoint(self.number_setpoint.get_value(), self._temperature_limit)


    def _update_progress(self, _val = None):
        """
        Updates the progress counter in the GUI.

        Parameters
        ----------
        _val : float, optional
            The default is None.

        """
        if _val == None:
            self._textbox_progress.set_value("%.2f %%"%(100*self.t_program/self.loaded_program.get_length()))
        else:
            self._textbox_progress.set_value("%.2f %%"%(100*_val/self.loaded_program.get_length()))


    def _update_step_time(self, t):
        """
        Updates the program step time in the GUI.

        Parameters
        ----------
        t : float
            Time remaining in the current program step.
        """
        
        # Get number of hours 
        hours, remainder = divmod(t,3600)
        
        # Get number of minutes and seconds
        minutes, seconds = divmod(remainder, 60)
        
        # Update the step time textbox 
        self.textbox_step_time.set_text("%dh %dmin %ds"%(hours, minutes, seconds))


    def _update_step(self, n):
        """
        Updates the step counter in the GUI.

        Parameters
        ----------
        n : int
            Current program step.
        """
        self.textbox_step.set_value("%d/%d"%(n,self.loaded_program.get_size()) )
    
    
    def _update_operation(self, _operation):
        """
        Updates the program operation in the GUI.

        Parameters
        ----------
        _operation : str
            Program operation (Ramp or Soak).
        """
        self.textbox_operation.set_value(_operation)
        
        
    def _update_program(self, name):
        """
        Updates the displayed program name in the GUI.

        Parameters
        ----------
        name : str
            Program name.
        """
        self.textbox_program.set_value(name)
    
    
    def _update_status(self):
        return
    
    
    def _update_combo_program(self):
        """
        Updates the list of availible programs in the program tab.
        """
        for i in range(1,len(self.combo_program.get_all_items())):
            self.combo_program.remove_item(1)
            
        for program in self.program_set:
            self.combo_program.add_item(program)
    
    
    def _timer_tick(self, *a):
        """
        Called whenever the timer ticks. 
        
        Updates the plot, saves the latest data,
        and advances the program (if one is running).
        """
        
        current_time = _time.time()
        
        # Get the time, temperature, and setpoint
        t = current_time - self.t0
        T = self.api.get_temperature()
        S = self.api.get_temperature_setpoint()
        P = self.api.get_main_output_power()    
        
        # Append this to the databox
        self.plot.append_row([t/3600, T, S, P], ckeys=['Time (h)', 'Temperature (C)', 'Setpoint (C)', 'Power (%)'])
        self.plot.plot()

        # Update the temperature data box
        self.number_temperature(T)
        
        # If a program is running
        if self.button_run.is_checked():
            
            ## Update time markers ##
            
            # Get the time change since last timer tick
            dt  = current_time - self.time
            
            # Increment the step time counter
            self.t_step += dt
            
            # Save the current time of this timer tick
            self.time = current_time
        
            # Increment the active program
            self.program_increment(T)
                
        # Update the GUI
        self.window.process_events()
    
    
    def setup_gui_components(self,name):
        """
        Populates the GUI.

        Parameters
        ----------
        name : str
            GUI window name.
            
        """
        
        # Upper middle of GUI - Basic numerical data readout (Temperature)
        self.grid_upper_mid = self.window.place_object(_g.GridLayout(margins=False), alignment=1,column_span=1)
        self.window.new_autorow()
        
        # Lower middle of GUI - Program parameter readout
        self.grid_lower_mid = self.window.place_object(_g.GridLayout(margins=False), alignment=1)
        self.window.new_autorow()
        
        # Bottom of GUI - Tabs
        self.grid_bot = self.window.place_object(_g.GridLayout(margins=False), alignment=0)
        
        # By default the bottom grid is disabled
        self.grid_bot.disable()
        
        # Add NumberBox and label for the current measured temperature from the Auber
        self.grid_upper_mid.add(_g.Label('Measured Temperature:'), alignment=1).set_style('font-size: 17pt; font-weight: bold; color: white')
        
        self.number_temperature = self.grid_upper_mid.add(_g.NumberBox(
            value=-273.16, suffix='°C', tip='Last recorded temperature value.'),
            alignment=1).set_width(175).disable().set_style('font-size: 17pt; font-weight: bold; color: white')
        
        #
        self.label_temperature_status = self.grid_upper_mid.add(_g.Label(name),
            column = 2, row_span=2).set_style('font-size: 17pt; font-weight: bold; color: '+('lightcoral'))
        
        # New row
        self.grid_upper_mid.new_autorow()

        # Add NumberBox and label of the Auber's current setpoint temperature 
        self.grid_upper_mid.add(_g.Label('Setpoint Temperature:'), alignment=1).set_style('font-size: 17pt; font-weight: bold; color: cyan')

        self.number_setpoint = self.grid_upper_mid.add(_g.NumberBox(
            -273.16, bounds=(-273.16, self._temperature_limit), suffix='°C',
            signal_changed=self._number_setpoint_changed, tip='Current temperature setpoint.')
            ).set_width(175).set_style('font-size: 17pt; font-weight: bold; color: cyan').disable()
        
        # Label and TextBox for displaying the current loaded program 
        self.grid_lower_mid.add(_g.Label('Program:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: lavender')
        self.textbox_program = self.grid_lower_mid.add(_g.TextBox('Custom', tip='Name of the currently selected program.'),alignment=0).set_width(150).set_style('font-size: 14pt; font-weight: bold; color: lavender').disable()
        
        # Label and TextBox for displaying the progression of the current program (in percent)
        self.grid_lower_mid.add(_g.Label('Progress:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: gold')
        self._textbox_progress = self.grid_lower_mid.add(_g.TextBox("0%", tip='Progress of completion of the currently selected program.'),alignment=1).set_width(100).set_style('font-size: 14pt; font-weight: bold; color: gold').disable()
        
        self.label_program_status = self.grid_lower_mid.add(_g.Label("(Disconnected)"),alignment=1,column_span=2).set_style('font-size: 17pt; font-weight: bold; color: '+('grey'))
        
        # New Row
        self.grid_lower_mid.new_autorow()
        
        # Label and TextBox for displaying the current program step 
        self.grid_lower_mid.add(_g.Label('Step:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: pink')
        self.textbox_step = self.grid_lower_mid.add(_g.TextBox("1/10", tip='What step you are on in the current program.'),alignment=0).set_width(70).set_style('font-size: 14pt; font-weight: bold; color: pink').disable()
        
        # Label and TextBox for displaying the current program operation 
        self.grid_lower_mid.add(_g.Label('Operation:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: paleturquoise')
        self.textbox_operation = self.grid_lower_mid.add(_g.TextBox("Hold", tip='Operation being preformed at the current program step (Ramp/Soak).'),alignment=0).set_width(100).set_style('font-size: 14pt; font-weight: bold; color: paleturquoise').disable()
        
        # Label and TextBox for displaying the remaining time in current program step 
        self.grid_lower_mid.add(_g.Label('Time:'),alignment=1).set_style('font-size: 14pt; font-weight: bold; color: coral')
        self.textbox_step_time = self.grid_lower_mid.add(_g.TextBox("0h 0min 0s", tip='Remaining time for the current program step.'),alignment=1).set_width(175).set_style('font-size: 14pt; font-weight: bold; color: coral').disable()
        
        # Add tabs to the bottom grid
        self.tabs = self.grid_bot.add(_g.TabArea(self.name+'.tabs'), alignment=0,column_span=10)
        
        # Create main tab
        self.tab_main  = self.tabs.add_tab('Main')

        # Add data plotting to main tab
        self.plot = self.tab_main.add(_g.DataboxPlot(
            file_type='*.csv',
            autosettings_path=name+'.plot',
            delimiter=',', show_logger=True), alignment=0, column_span=10)
        
        # Timer for collecting data
        self.timer = _g.Timer(interval_ms=250, single_shot=False)
        self.timer.signal_tick.connect(self._timer_tick)

        # Bottom log file controls
        self.tab_main.new_autorow()
        
        # Create a tab for program setpoint control
        self.tab_program = self.tabs.add_tab('Program')
        
        # Pop tab from the main GUI (This is done for aesthetic sizing reasons)
        poped_tab = self.tabs.pop_tab(1)
        poped_tab.hide()
        
        # Top grid of the "Program" tab
        self.tab_program_top = self.tab_program.place_object(_g.GridLayout(margins=False))
        
        # Add program selector label and ComboBox
        self.tab_program_top.add(_g.Label('Program:'),alignment=1).set_width(120).set_style('font-size: 12pt; font-weight: bold; color: lavender')
        
        self.combo_program = self.tab_program_top.add(_g.ComboBox(['Custom']+list(self.program_set.keys())),alignment=1).set_width(150).set_style('font-size: 12pt; font-weight: bold; color: lavender')
        self.combo_program.signal_changed.connect(self._combo_program_changed)
        
        # Add "Run" button for program activation
        self.button_run = self.tab_program_top.add(_g.Button('Run', checkable=True).set_style('font-size: 12pt').set_height(27)).disable()
        self.button_run.signal_toggled.connect(self._button_run_toggled)
        
        # Add "Save" button for saving new programs
        self.button_save = self.tab_program_top.add(_g.Button('Save').set_style('font-size: 12pt').set_height(27)).disable()
        self.button_save.signal_clicked.connect(self._button_save_toggled)
        
        # New row
        self.tab_program.new_autorow()
        
        # Bottom grid of the "Program" tab
        self.tab_program_bot = self.tab_program.place_object(_g.GridLayout(margins=False))
        
        # Create program step entries 
        for i in range(PROGRAM_STEPS):
            self.program[i] = dict()      
            
            self.tab_program_bot.add(_g.Label('Step %d:'%i),alignment=0).set_width(120).set_style('font-size: 12pt; font-weight: bold; color: pink')
            self.program[i]['operation']   = self.tab_program_bot.add(_g.ComboBox(["--","Ramp","Soak"],signal_changed=self._check_program_validity),alignment = 0).set_width(125).set_style('font-size: 12pt; font-weight: bold; color: paleturquoise')
            
            self.tab_program_bot.add(_g.Label('Temperature:'),alignment=0).set_style('font-size: 12pt; font-weight: bold; color: cyan')
            self.program[i]['temperature'] = self.tab_program_bot.add(_g.NumberBox(24.5, bounds=(-273.16, self._temperature_limit), suffix='°C'),alignment=0).set_width(100).set_style('font-size: 12pt; font-weight: bold; color: cyan')
            
            self.tab_program_bot.add(_g.Label('Duration:'),alignment=2).set_style('font-size: 12pt; font-weight: bold; color: gold')
            self.program[i]['time']        = self.tab_program_bot.add(_g.NumberBox(200.5, bounds=(0,1000.), suffix='h'),alignment=2).set_width(100).set_style('font-size: 12pt; font-weight: bold; color: gold')
            
            if i < (PROGRAM_STEPS-1): self.tab_program_bot.new_autorow()
    
    
    def program_increment(self, T):
        """

        Parameters
        ----------
        T : float
            Current temperature.

        """
        
        # Ramp operation
        if(self.step_operation == "Ramp"):
            
            # Up ramp
            if self.T_stop > self.T_start:
                
                # Check if we have reached the stop temperature
                if round(self.T_current,1) < self.T_stop:
                    
                    # Check if we are ready to increment the temperature
                    while self.t_step >= self.t_next: 
                        
                        # Update time since program has started
                        self.t_program +=  self.step_time
                        
                        # 
                        self.t_next += self.step_time
                        
                        # Increment temperature
                        self.T_current += 0.1
                        
                        # Set the new temperature
                        self.number_setpoint.set_value(self.T_current)
                        
                        if(round(self.T_current,1) >= self.T_stop): break
                                  
                    # Update step time on the GUI
                    self._update_step_time(self.step_duration - self.t_step if self.step_duration - self.t_step > 0 else 0)
                    
                    # Update the program progress counter on the GUI
                    self._update_progress()
                    
                    # Break
                    return 
       
                else:
                    # Goto next step in the program 
                    self.step_increment()
                    
                    # Break
                    return
                    
             # Down ramp        
            if self.T_stop < self.T_start:
                
                # Check if we have reached the stop temperature
                if round(self.T_current,1) > self.T_stop:
                    
                    while self.t_step >= self.t_next: 
                        
                        # Update time since program has started
                        self.t_program +=  self.step_time
                        
                        #
                        self.t_next += self.step_time
                        
                        # Decrement temperature
                        self.T_current -= 0.1
                        
                        # Set the new temperature
                        self.number_setpoint.set_value(self.T_current)
                        
                        # Break the loop if we reach stopping temperature
                        if(round(self.T_current,1) <= self.T_stop): break
                        

                    # Update step time on the GUI
                    self._update_step_time(self.step_duration - self.t_step if self.step_duration - self.t_step > 0 else 0)
                        
                    # Update the program progress counter on the GUI
                    self._update_progress()
                        
                    # Break
                    return
                
                else:
                    # Goto next step in the program
                    self.step_increment()
                    
                    # Break
                    return
        
            
        # Soak operation
        else:
            if self.t_step < self.t_next:
                
                # Keep the user in the game
                self._update_progress(self.t_program +  self.t_step)
                self._update_step_time(self.step_duration - self.t_step if self.step_duration - self.t_step > 0 else 0)
 
            else:
                # Update the program time variable with the total soak time
                self.t_program += self.loaded_program.get_step_duration()*3600
                
                # Goto next step in the program
                self.step_increment()
      
        
    def step_increment(self):
        
        # Load in the next step if it exists
        if self.loaded_program.check_next():
            
            # Move to the next program step
            self.step_time, self.t_next, self.T_start, self.T_stop = self.loaded_program.increment_step(
                                                            self.api.get_temperature_setpoint())
            # Zero the step time
            self.t_step = 0
        
            # Get step parameters 
            self.step_duration = self.loaded_program.get_step_duration()*3600
            self.step_operation     = self.loaded_program.get_step_operation()
            
            # Update the step number in the GUI
            self._update_step(self.loaded_program.get_step_index()+1)
            
            # Update the step time in the GUI
            self._update_step_time(self.step_duration)
            
            # Update operation type in the GUI
            self._update_operation(self.step_operation)
                
            # Update the program progress counter in the GUI
            self._update_progress()
            
        else:
            #
            self._update_step_time(0)
            
            # Unclick the run button
            self.button_run.click()
            
            # Show the user the program is complete
            self.label_program_status.set_text("(Completed)").set_style('font-size: 17pt; font-weight: bold; color: '+('mediumspringgreen'))
            
    def get_program_set(self):
        
        if PROGRAM_DIR in _os.listdir():
            
            for file in _os.listdir(PROGRAM_DIR):
                f = _s.data.databox().load_file(path = PROGRAM_DIR+'/'+file, quiet=True)
    
                self.program_set[f.h('name')] = []
                for i in range(10):
                    operation = f.h('op%d'%i)
                    
                    if operation != '':
                        self.program_set[f.h('name')].append(operation)
                    else: break
        else:
            try: _os.mkdir(PROGRAM_DIR)
            except: return
            
        
if __name__ == '__main__':
    _egg.clear_egg_settings()
    alpha = auber_syl53x2p(name = "Alpha",temperature_limit = 1100)
    bravo = auber_syl53x2p(name = "Bravo",temperature_limit = 1100)

