class program():
    """
    
    """
    
    def __init__(self, name, program_set):
        
        # Remember the name
        self.name  = name
        
        # If not a custom program, grab all the details
        if name != 'Custom':
            
            # Get the program steps
            self.steps = program_set[name]
            
            # Load the first step
            self.loaded_step = self.steps[0]
            
            # Remeber step index
            self.loaded_step_index = 0
            
            # Remeber number of steps in the program
            self.size = len(self.steps)
            
            # Calculate the total program length (in seconds)
            self.length = 0
            for i in range(self.size):
                # Add the length of this step to the total program length
                self.length += self.steps[i][2]*3600
        else:
            self.steps = []

    def get_name(self):
        """
        Get the program name.
        """
        return self.name
    
    def get_step_operation(self):
        """
        Get the operation of the current step.

        """
        return self.loaded_step[0]
    
    def get_step_temperature(self):
        """
        Get the set temperature of the current step.
        """
        return self.loaded_step[1]
    
    def get_step_duration(self):
        """
        Get the duration of the current step.
        """
        return self.loaded_step[2]
    
    def get_size(self):
        """
        Get the program size (number of steps).
        """
        return self.size
        
    def get_step(self,i):
        """
        Get the ith step of the program.

        Parameters
        ----------
        i : int
            Step index.

        Returns None if no step of the requested index exists.

        """
        if i < self.size:
            return self.steps[i]
        else:
            return None
    
    def get_length(self):
        """
        Get the full program duration (duration of all combined steps)
        in seconds.
        """
        return self.length  
    
    def get_step_index(self):
        """
        Get the current step index.
        """
        return self.loaded_step_index
    
    def add_step(self, new_step):
        """
        Add a new step to the program.

        Parameters
        ----------
        new_step : list
            List containing step information in the order
            (operation, temperature, duration).
        """
        
        # Append the new step to the step list
        self.steps.append(new_step)
        
        # If this is the first added step
        if len(self.steps) == 1:
            
            # Load the first step
            self.loaded_step = self.steps[0]
            
            # Remeber step index
            self.loaded_step_index = 0
            
        # Update number of steps in the program
        self.size = len(self.steps)
            
        # Update the total program length (in seconds)
        self.length = 0
        for i in range(self.size):
            # Add the length of this step to the total program length
            self.length += self.steps[i][2]*3600
            
    def check_next(self):
        """
        Check if there is a next step 
        (following the current loaded step) to the program.

        Returns
        -------
        bool
            True if a next step exists, False otherwise.

        """
        if self.loaded_step_index < self.size - 1:
            return True
        else:
            return False
    
    def increment_step(self, current_setpoint):
        """
        Move to the next program step.

        """
        
        # Load in the nxt program step.
        self.loaded_step = self.steps[self.loaded_step_index+1]
        
        # Update the step index.
        self.loaded_step_index += 1
        
        # Calculate temperature ramping parameters
        if self.get_step_operation() == 'Ramp':
            self.dT        = self.get_step_temperature() - current_setpoint
            self.sgn       = 1 if self.dT > 0 else -1
            self.step_time = self.get_step_duration()*3600 / (abs(self.dT) * 10.0)
            self.t_next    = self.step_time
            
        else:
            self.step_time = 0
            self.t_next    =  self.get_step_duration()*3600 # In seconds 
            
        return self.step_time, self.t_next, current_setpoint, self.get_step_temperature()
            
        
        
    def run(self, current_temperature):
        """
        Run the program.
        """
        # Calculate temperature ramping parameters
        if self.get_step_operation() == 'Ramp':
            
            self.dT        = self.get_step_temperature() - current_temperature
            self.sgn       = 1 if self.dT > 0 else -1
            self.step_time = self.get_step_duration()*3600 / (abs(self.dT) * 10.0)
            self.t_next    = self.step_time
        
        else:
            self.step_time = 0
            self.t_next    =  self.get_step_duration()*3600 # In seconds 
            
        return self.step_time, self.t_next, current_temperature, self.get_step_temperature()
    
    def save_program(self):
        """
        Save the program to the PROGRAM_DIR directory.

        """
        
        # Create a spinmob databox to hold the program step data
        s = _s.data.databox()
        
        # Get the name of the new program via save dialog box.
        result = _s._qtw.QFileDialog.getSaveFileName(directory=_os.getcwd()+'/'+PROGRAM_DIR)
        self.name = result[0].split('/')[-1]
        
        # Add a name header to the databox
        s.h(name = self.name)

        # Add the program steps as headers to the databox
        for i in range(0,self.size):
            
            # Insert filled steps
            s.insert_header('op%d'%i, self.steps[i])
            
        for j in range(self.size,PROGRAM_STEPS):
            
            # Insert empty steps
            s.insert_header('op%d'%j, '')
            
        # Save the file.
        s.save_file(PROGRAM_DIR+'/'+result[0].split('/')[-1])

        return self.name