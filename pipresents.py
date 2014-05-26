#! /usr/bin/env python

"""
Part of Pi Presents
Pi Presents is a presentation package, running on the Raspberry Pi, for museum exhibits, galleries, and presentations.
Copyright 2012/2013, Ken Thompson

See manual.pdf for instructions.
"""
import os
import sys
import copy
import traceback
from subprocess import call
import time

from Tkinter import *
import Tkinter as tk
import tkMessageBox

from pp_options import command_options
from pp_showlist import ShowList
from pp_validate import Validator
from pp_showmanager import ShowManager
from pp_resourcereader import ResourceReader
from pp_screendriver import ScreenDriver
from pp_timeofday import TimeOfDay
from pp_kbddriver import KbdDriver
from pp_controlsmanager import ControlsManager
from pp_utils import Monitor
from pp_utils import StopWatch


class PiPresents(object):
    """
    Instantiated from the command line or from a script. Takes care of
    """

    def __init__(self, options):
        
        self.pipresents_issue = "1.2"
        self.nonfull_window_width = 0.6     # proportion of width
        self.nonfull_window_height = 0.6    # proportion of height
        self.nonfull_window_x = 0           # position of top left corner
        self.nonfull_window_y = 0           # position of top left corner
        
        StopWatch.global_enable = False

#****************************************
# Initialisation
# ***************************************
        # get command line options
        self.options = options

        # TODO: make this more flexible so that PPresents can be installed directly into python sources
        # get pi presents code directory
        pp_dir = sys.path(__file__)
        self.pp_dir = pp_dir
        
        if not os.path.exists(os.path.join(self.pp_dir, "pipresents.py")):
            tkMessageBox.showwarning("Pi Presents", "Bad Application Directory")
            exit()

        #Initialise logging
        Monitor.log_path = self.pp_dir
        self.mon = Monitor()
        self.mon.on()
        if self.options['debug']:
            Monitor.global_enable = True
        else:
            Monitor.global_enable = False
 
        self.mon.log(self, "Pi Presents is starting")
        self.mon.log(self, "OS and separator:" + os.name + '  ' + os.sep)
        self.mon.log(self, "sys.path[0] - location of code: " + sys.path[0])
        # self.mon.log(self,"os.getenv('HOME') -  user home directory (not used): " + os.getenv('HOME'))
        # self.mon.log(self,"os.path.expanduser('~') -  user home directory: " + os.path.expanduser('~'))

        # optional other classes used
        self.ppio = None
        self.tod = None
         
        #get profile path from -p option
        if self.options['profile']:
            self.pp_profile_path = os.path.join("pp_profiles", self.options['profile'])
        else:
            self.pp_profile_path = os.path.join("pp_profiles", "pp_profile")
        
       #get directory containing pp_home from the command,
        if not self.options['home']:
            home = os.path.join(os.path.expanduser('~'), "pp_home")
        else:
            home = os.path.join(self.options['home'], "pp_home")
        self.mon.log(self, "pp_home directory is: " + home)
        
        #check if pp_home exists.
        # try for 10 seconds to allow usb stick to automount
        # fall back to pipresents/pp_home
        self.pp_home = os.path.join(pp_dir, "pp_home")

        found = False
        for i in range(1, 10):
            self.mon.log(self, "Trying pp_home at: {0} ({1})".format(home, i))
            if os.path.exists(home):
                found = True
                self.pp_home = home
                break
            time.sleep(1)
        if found:
            self.mon.log(self, "Found Requested Home Directory, using pp_home at: " + home)
        else:    
            self.mon.log(self, "FAILED to find requested home directory, using default to display error message: " + self.pp_home)

        #check profile exists, if not default to error profile inside pipresents
        self.pp_profile = self.pp_home+self.pp_profile_path
        if os.path.exists(self.pp_profile):
            self.mon.log(self, "Found Requested profile - pp_profile directory is: " + self.pp_profile)
        else:
            self.pp_profile=pp_dir+"/pp_home/pp_profiles/pp_profile"   
            self.mon.log(self, "FAILED to find requested profile, using default to display error message: pp_profile")
        
        if self.options['verify']:
            val = Validator()
            if not val.validate_profile(None, pp_dir, self.pp_home, self.pp_profile, self.pipresents_issue, False):
                tkMessageBox.showwarning("Pi Presents", "Validation Failed")
                exit()
                
        # open the resources
        self.rr = ResourceReader()
        # read the file, done once for all the other classes to use.
        if not self.rr.read(pp_dir, self.pp_home, self.pp_profile):
            self.end('error', 'cannot find resources.cfg')

        #initialise and read the showlist in the profile
        self.showlist = ShowList()
        self.showlist_file = os.path.join(self.pp_profile, "pp_showlist.json")
        if os.path.exists(self.showlist_file):
            self.showlist.open_json(self.showlist_file)
        else:
            self.mon.err(self, "showlist not found at " + self.showlist_file)
            self.end('error', 'showlist not found')

        # check profile and Pi Presents issues are compatible
        if float(self.showlist.sissue()) != float(self.pipresents_issue):
            self.mon.err(self, "Version of profile {0} is not same as Pi Presents, must exit".format(self.showlist.sissue()))
            self.end('error', 'wrong version of profile')
 
        # get the 'start' show from the showlist
        index = self.showlist.index_of_show('start')
        if index >= 0:
            self.showlist.select(index)
            self.starter_show = self.showlist.selected_show()
        else:
            self.mon.err(self, "Show [start] not found in showlist")
            self.end('error', 'start show not found')

# ********************
# SET UP THE GUI
# ********************
        #turn off the screenblanking and saver
        if self.options['noblank']:
            call(["xset", "s", "off"])
            call(["xset", "s", "-dpms"])

        self.root = Tk()
       
        self.title = 'Pi Presents - '+ self.pp_profile
        self.icon_text = 'Pi Presents'
        self.root.title(self.title)
        self.root.iconname(self.icon_text)
        self.root.config(bg='black')
        
        # get size of the screen
        self.screen_width = self.root.winfo_screenwidth()
        self.screen_height = self.root.winfo_screenheight()

        # set window dimensions and decorations
        if self.options['fullscreen']:

            self.root.attributes('-fullscreen', True)
            os.system('unclutter &')
            self.window_width = self.screen_width
            self.window_height = self.screen_height
            self.window_x = 0
            self.window_y = 0
            self.root.geometry("%dx%d%+d%+d" % (self.window_width, self.window_height, self.window_x, self.window_y))
            self.root.attributes('-zoomed', '1')
        else:
            self.window_width = int(self.screen_width*self.nonfull_window_width)
            self.window_height = int(self.screen_height*self.nonfull_window_height)
            self.window_x = self.nonfull_window_x
            self.window_y = self.nonfull_window_y
            self.root.geometry("%dx%d%+d%+d" % (self.window_width, self.window_height, self.window_x, self.window_y))
            
        #canvas covers the whole window
        self.canvas_height = self.screen_height
        self.canvas_width = self.screen_width
        
        # make sure focus is set.
        self.root.focus_set()

        #define response to main window closing.
        self.root.protocol("WM_DELETE_WINDOW", self.exit_pressed)

        #setup a canvas onto which will be drawn the images or text
        self.canvas = Canvas(self.root, bg='black')

        self.canvas.config(height=self.canvas_height,
                           width=self.canvas_width,
                           highlightthickness=0)
        # self.canvas.pack()
        self.canvas.place(x=0, y=0)

        self.canvas.focus_set()

# ****************************************
# INITIALISE THE INPUT DRIVERS
# ****************************************

        # looks after bindings between symbolic names and internal operations
        controlsmanager = ControlsManager()
        if not controlsmanager.read(pp_dir,self.pp_home,self.pp_profile):
                self.end('error', 'cannot find or error in controls.cfg.cfg')
        else:
            controlsmanager.parse_defaults()

        # each driver takes a set of inputs, binds them to symboic names
        # and sets up a callback which returns the symbolic name when an input event occurs/

        # use keyboard driver to bind keys to symbolic names and to set up callback
        kbd = KbdDriver()
        if not kbd.read(pp_dir,self.pp_home,self.pp_profile):
                self.end('error','cannot find or error in keys.cfg')
        kbd.bind_keys(self.root,self.input_pressed)

        self.sr = ScreenDriver()
        # read the screen click area config file
        if not self.sr.read(pp_dir,self.pp_home,self.pp_profile):
            self.end('error', 'cannot find screen.cfg')

        # create click areas on the canvas, must be polygon as outline rectangles are not filled as far as find_closest goes
        reason, message = self.sr.make_click_areas(self.canvas,self.input_pressed)
        if reason == 'error':
            self.mon.err(self, message)
            self.end('error', message)

# ****************************************
# INITIALISE THE APPLICATION AND START
# ****************************************
        self.shutdown_required = False
        
        #kick off GPIO if enabled by command line option
        if self.options['gpio']:
            from pp_gpio import PPIO
            # initialise the GPIO
            self.ppio = PPIO()
            # PPIO.gpio_enabled=False
            if not self.ppio.init(pp_dir, self.pp_home, self.pp_profile, self.canvas, 50, self.gpio_pressed):
                self.end('error', 'gpio error')
                
            # and start polling gpio
            self.ppio.poll()

        #kick off the time of day scheduler
        self.tod = TimeOfDay()
        self.tod.init(pp_dir, self.pp_home, self.canvas, 500)
        self.tod.poll()

        # Create list of start shows initialise them and then run them
        self.run_start_shows()

        #start tkinter
        self.root.mainloop()

# *********************
#  RUN START SHOWS
# ********************   
    def run_start_shows(self):
        #start show manager
        show_id = -1  #start show
        self.show_manager = ShowManager(show_id, self.showlist, self.starter_show, self.root, self.canvas, self.pp_dir,
                                        self.pp_profile, self.pp_home)
        
        #first time through so empty show register and set callback to terminate Pi Presents if all shows have ended.
        self.show_manager.init(self.all_shows_ended_callback)

        #parse the start shows field and start the initial shows       
        start_shows_text = self.starter_show['start-show']
        self.show_manager.start_initial_shows(start_shows_text)

    #callback from ShowManager when all shows have ended
    def all_shows_ended_callback(self, reason, message, force_shutdown):
        self.mon.log(self, "All shows ended, so terminate Pi Presents")
        if force_shutdown:
            self.shutdown_required = True
            self.mon.log(self, "shutdown forced by profile")
            self.terminate('killed')
        else:
            self.end(reason, message)

# *********************
# User inputs
# ********************

    #gpio callback - symbol provided by gpio
    def gpio_pressed(self, index, symbol, edge):
        self.mon.log(self, "GPIO Pressed: " + symbol)
        self.input_pressed(symbol, edge, 'gpio')

    # all input events call this callback with a symbolic name.              
    def input_pressed(self, symbol, edge, source):
        self.mon.log(self, "input received: " + symbol)
        if symbol == 'pp-exit':
            self.exit_pressed()
        elif symbol == 'pp-shutdown':
            self.shutdown_pressed('delay')
        elif symbol == 'pp-shutdownnow':
            self.shutdown_pressed('now')
        else:
            for show in self.show_manager.shows:
                show_obj = show[ShowManager.SHOW_OBJ]
                if show_obj is not None:
                    show_obj.input_pressed(symbol, edge, source)

# **************************************
# respond to exit inputs by terminating
# **************************************

    def shutdown_pressed(self, when):
        if when == 'delay':
            self.root.after(5000, self.on_shutdown_delay)
        else:
            self.shutdown_required = True
            self.exit_pressed()           

    def on_shutdown_delay(self):
        if self.ppio.shutdown_pressed():
            self.shutdown_required = True
            self.exit_pressed()

    def exit_pressed(self):
        self.mon.log(self, "kill received from user")
        #terminate any running shows and players     
        self.mon.log(self, "kill sent to shows")
        self.terminate('killed')

     # kill or error
    def terminate(self, reason):
        needs_termination = False
        for show in self.show_manager.shows:
            if show[ShowManager.SHOW_OBJ] is not None:
                needs_termination = True
                self.mon.log(self, "Sent terminate to show " + show[ShowManager.SHOW_REF])
                show[ShowManager.SHOW_OBJ].terminate(reason)
        if not needs_termination:
            self.end(reason, 'terminate - no termination of lower levels required')

# ******************************
# Ending Pi Presents after all the showers and players are closed
# **************************

    def end(self, reason, message):

        self.mon.log(self, "Pi Presents ending with message: " + reason + ' ' + message)
        if reason == 'error':
            self.tidy_up()
            self.mon.log(self, "exiting because of error")
            #close logging files 
            self.mon.finish()
            exit()            
        else:
            self.tidy_up()
            self.mon.log(self,"no error - exiting normally")
            #close logging files 
            self.mon.finish()
            if self.shutdown_required:
                call(['sudo', 'shutdown', '-h', '-t 5','now'])
                exit()
            else:
                exit()

    def tidy_up(self):
        """
        tidy up all the peripheral bits of Pi Presents
        """
        #turn screen blanking back on
        if self.options['noblank']:
            call(["xset", "s", "on"])
            call(["xset", "s", "+dpms"])
            
        # tidy up gpio
        if self.options['gpio'] and self.ppio is not None:
            self.ppio.terminate()
            
        #tidy up time of day scheduler
        if self.tod is not None:
            self.tod.terminate()

# *****************************
# utilitities
# ****************************

    def resource(self, section, item):
        value = self.rr.get(section, item)
        if not value:
            self.mon.err(self, "resource: {0}: {1} not found".format(section, item))
            self.terminate("error")
        else:
            return value

          
if __name__ == '__main__':

    pp = PiPresents(command_options())
    #try:
        #pp = PiPresents()
    #except:
        # traceback.print_exc(file=open("/home/pi/pp_exceptions.log","w"))
        #pass


