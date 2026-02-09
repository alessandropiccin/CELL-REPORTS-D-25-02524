# -*- coding: ISO-8859-1 -*-
import os
from pathlib import Path
import pandas as pd
import time
import json
import numpy as np
import pylab as graph
from random import random
import tkinter as tk
from tkinter import ttk

"""
Photometry analysis.
Read all files from a sub-folder of wherever program is run from.
Photometry files and behavior files should have the same name and different extensions,
defined in parameters_photometry.py and parameters_behavior.py.
Events are aligned using a blind procedure exploring all possible offsets between Min_offset and Max_offset.
Times are matched within an approximation range.
Create two corresponding databases of tagged trials and analyzed photometry data
"""
print("\nPhautom - 12/03/2025 - Alain R. Marchand\n")

Session_info=None #(18, 20)
Use_columns, Photom_columns, Iso, Sig=dict(), dict(), dict(), dict()
Behav_database_name, Photom_database_name=dict(), dict()

Param_file='phautom_parameters.json'          # some parameters will be read from Param_file

""" Example Param_file content
{
    "Regions": 2,
    "Behav_time": 100,
    "Minus_window": -5000,
    "Plus_window": 8000,
    "Min_offset": -4000,
    "Max_offset": 1000,
    "Photom_interval": 50,
    "Approximation": 50,
    "Ignore_first_seconds": 5,
    "Photom_marker": "*0",
    "TTL_on": "t_appui",
    "Align_on": "t_appui",
    "Synchro_codes": "{'P1': [0], 'P2': [0, 600], 'P3': [0, 600, 1200], 'D1': [1800], 'A1': [1800]}",
    "Add_reward": "True",
    "Globalize_z_score": "False",
    "Linear_regression": "True",
    "Divide_by_mean": "False",
    "Keep_DC_level": "False",
    "Detrend": "True",
    "Visualize": "False"
}
"""
# json check
not_bool=["Photom_marker", "TTL_on", "Align_on", "Synchro_codes"] # string parameters

# synchronization parameters (adjust for best alignment)
Refine=8                                                      # accuracy in ms for intermediate alignment
Reliability_threshold=0.8                             # triggers warning message if matches less than                  
ask_offset=False

# photometry file parameters
Input_subdir="Data"                                   # sub directory containing input data
Photom_ext=".csv"                                     # extension for photometry files
Photom_skip_header=1                               # header lines to ignore before column titles
Use_columns[1]=(0,1,2,3)                           # read time, control and signal
Use_columns[2]=(0,1,4,5)                           # read time, control and signal if 2 regions
Photom_columns[1]=(0,2,3)                        # time, control and signal
Photom_columns[2]=(0,4,5)                        # time, control and signal if 2 regions
Photom_marker_column=1                         # marker column
Iso[1], Iso[2]="CH1-410", "CH2-410"          # column titles
Sig[1], Sig[2]="CH1-470", "CH2-470"          # column titles
Timestamp="TimeStamp"                            # column titles
Photom_time_base=1                                   # time base in milliseconds
Photom_out_unit=1000                               # convert milliseconds to seconds

# behavior file parameters
Behav_ext=".xlsx"                                        # extension for processed behavioral files .xlsx
Behav_ext_WhandA=".xls"                           # extension for processed behavioral files from Whanda .xls
Sheet_name="essais"                                  # Excel data sheet containing input data
Time_column="temps"
Event_column="event"
Reward_column="reward"
Behav_header_size=0                                  # header lines to ignore
##Behav_time=100                                 # time base in milliseconds
Behav_time_Whanda=1000                # time base in milliseconds
Behav_time_unit=1000                                # unit for analysed data in milliseconds

# TTL parameters
Event_code_size=-2                                      # keep only the last characters

# Output parameters
Output_subdir="Database"                       # sub directory containing output data
Logs_subdir="Database\\Logs"                       # sub directory containing log data
Behav_database_name[2]="Behav_data2.xls"
Photom_database_name[2]="Photom_data2.xls"
# see below for names #1
Log_summary_name="Log_summary.txt"
Log_ext=".txt"

File_error="\n*** Error: cannot access file:"
Time_base_error="\n*** Error: time base does not match in file:"
Pause_time=2

#==================================================
def load_parameters_from_json(filename):
    """
    Load parameters from a JSON file.

    Parameters:
    - filename (str): The name of the JSON file.

    Returns:
    - parameters (dict): A dictionary containing parameters.
    """
    try:
        with open(filename, 'r') as file:
            parameters = json.load(file)
        return parameters
    except FileNotFoundError:
        print(f"File '{filename}' not found.")
        exit_on_keypress()
    except json.JSONDecodeError:
        print(f"Error decoding JSON from file '{filename}'.")
        exit_on_keypress()
        
#==================================================
def save_parameters_to_json(filename, parameters):
    """
    Save a group of parameters to a JSON file.

    Parameters:
    - filename (str): The name of the JSON file.
    - parameters (dict): A dictionary containing parameters of various types.
    """

    with open(filename, 'w') as file:
        json.dump(parameters, file, indent=4)
        
#==================================================
class ParameterEditor:
    def __init__(self, master, parameters, filename):
        self.width=60
        self.filename=filename
        self.master = master
        self.master.title("Parameter Editor")
        self.parameters = parameters

        self.create_widgets()

    def create_widgets(self):
        # Create labels and entry widgets for each parameter, in two columns
        row, col = 0, 0                                   # column variable to alternate between columns
        for i, (key, value) in enumerate(self.parameters.items()):
            label = ttk.Label(self.master, text=key)
            label.grid(row=row, column=col*2, padx=5, pady=5, sticky=tk.E)

            entry = ttk.Entry(self.master, width=self.width)
            entry.insert(0, str(value))
            entry.grid(row=row, column=col*2+1, padx=5, pady=5, sticky=tk.W)

            # Alternate between two columns
            col, row = 1-col, row+col             # Move to the next row after filling two columns

        # Create a button to save the modified parameters
        save_button = ttk.Button(self.master, text="Save", command=self.save_parameters)
        save_button.grid(row=row+1, columnspan=4, pady=10)  # Span across two columns

    def save_parameters(self):
        # Update the parameters with the values from the entry widgets       
        for i, widget in enumerate(self.master.winfo_children()):
            if isinstance(widget, ttk.Label):
                parameter_name=widget.cget("text")
            if isinstance(widget, ttk.Entry):
                new_value = widget.get()
                self.parameters[parameter_name] = self.convert_to_correct_type(new_value)

        # Save the modified parameters to the JSON file
        save_parameters_to_json(self.filename, self.parameters)
        print("Parameters saved")

        # Optionally, you can close the GUI after saving
        self.master.destroy()

    def convert_to_correct_type(self, value):
        try:
            # Attempt to convert the value to int, float, or keep it as a string
            return int(value)
        except ValueError:
            try:
                return float(value)
            except ValueError:
                return value

#==================================================
def set_parameters(parameter_file):
    """
    get and display parameters for modification
    new parameters will be saved for next time
    parameter_file: string
    """
    parameters = load_parameters_from_json(parameter_file)

    if parameters:
        root = tk.Tk()
        editor = ParameterEditor(root, parameters, parameter_file)
        root.mainloop()

    return parameters

#==================================================
def make_subdir(dirname):
    """
    try creating directory, ignore if directory exists
    """
    try:
        os.mkdir(dirname)
    except FileExistsError: pass
        
#==================================================
def find_files(directory_in, Behav_ext, stop=True):
    behav_list=[]
    try:
        filelist = [os.path.normcase(name) for name in os.listdir(directory_in)]
        behav_list = [os.path.join(directory_in, name)                   # select behavior files
                    for name in filelist if os.path.splitext(name)[1] == Behav_ext]

        if not behav_list:
            behav_list = get_shortcut_file_list(directory_in,  Behav_ext, stop=stop)
        
        if not behav_list and stop:
            print("\n*** No files found. Please verify file type ***")
            exit_on_keypress()
            
    except IOError:
        print(File_error, directory_in,"***\n") 
        exit_on_keypress()
        
    return behav_list        
#=====================================================
def get_file_list(directory_in,  Behav_ext, Behav_ext_WhandA, Behav_time, Behav_time_Whanda):
    behav_list = find_files(directory_in, Behav_ext, stop=False)
    
    if not behav_list:
        Behav_ext=Behav_ext_WhandA
        Behav_time=Behav_time_Whanda
        behav_list = find_files(directory_in, Behav_ext, stop=False)
        
    return behav_list, Behav_time

#=============================================================
def get_shortcut_file_list(directory_in,  Datafile_extension, stop=True):                                                   
        """
        get list of files from shortcuts in data directory 
        """
        dirlist=os.listdir(directory_in)
        shortcutlist=[os.path.join(directory_in, name)
                      for name in dirlist if os.path.splitext(name)[1] == ".lnk"]                           
        if not shortcutlist and stop:
            print("*** No shortcut to data found ***")
            raise ReferenceError

        datalist=[get_target(name) for name in shortcutlist]
        datalist=[name  for name in datalist if os.path.splitext(name)[1] == Datafile_extension]
            
        return datalist
    
#================================================================
def get_target(shortcut):                              
        """
        return path to target of a shortcut
        """
        special_chars=[('\\xe9', 'é'), ('\\xe0', 'à'), ('\\xe7', 'ç'), ('\\xe8', 'è'), ('\\xf9', 'ù'), ('\\xea', 'ê')]
##        print(special_chars)                 

##        print('\nshortcut', shortcut)        
        if not shortcut.endswith(".lnk"):
            return None
        with open(shortcut,'rb') as f:
            destination=f.read()
            if b':\\' in destination:
                here=destination.find(b':\\')-1
                if b'\x00' in destination:
                    there=destination.find(b'\x00', here)
                    text=str(destination[here:there])[2:-1]
                    
                    text=text.replace('\\\\', '\\')
                    for k, c in special_chars:
                        text=text.replace(k, c)
##                    print('target', text)
                    return text

#==================================================
def check_sampling_interval(photom_file, Photom_interval, Photom_time_base):
    """
    read the first lines of photometry file to verify sampling interval
    """
    try:
        with open(photom_name, "r") as photom_file:

            for i in range(Photom_skip_header+1):              # ignore header and titles
                photom_line=photom_file.readline() 

            if photom_line:
                first_line=photom_file.readline() .split(",")                  # read one line 
                second_line=photom_file.readline().split(",")              # read one line
                interval=(float(second_line[0])-float(first_line[0]))*Photom_time_base
                if abs(interval-Photom_interval)>0.5: raise IOError
            
    except IOError:
        print(Time_base_error, photom_name, "-->", interval, "ms instead of",Photom_interval, "ms ***\n")
        exit_on_keypress()                                               # fatal error

 
#==================================================
def get_photom_times(photom_name, Photom_time_base, Photom_interval, Photom_skip_header):
    """
    read photometry file line-by-line to detect TTL markers 
    build a list of TTL onsets
    Parameters
    -----------
       photom_name: full name of file
       Photom_time_base: in milliseconds
       Photom_header_size
    Returns
    -------
        photom_times: a list of times in milliseconds
    """
    photom_times=[]
    
    try:
        with open(photom_name, "r") as photom_file:
            check_sampling_interval(photom_file, Photom_interval, Photom_time_base)
            
            for i in range(Photom_skip_header+1):              # ignore header and titles
                photom_line=photom_file.readline() 
            valid_line=photom_line                                     # look for end of file
            
            while valid_line:
                valid_line=photom_file.readline()                   # read one line 
                photom_line=valid_line.split(",")                    # split line
                if len(photom_line)>Photom_marker_column:
                    if photom_line[Photom_marker_column].endswith(Photom_marker):
                        time=float(photom_line[0])*Photom_time_base
                        photom_times+=[time]                             # extract TTL marker

    except IOError:
        print(File_error, photom_name,"***\n") 

    return photom_times

#==================================================
def get_photom_data(region, photom_name, Photom_time_base, Photom_skip_header):
    """
    read photometry file 
    Parameters
    -----------
       region: 1 or 2 
       photom_name: full name of file
       Photom_time_base: in milliseconds
       Photom_skip_header: lines to skip before column titles
    Returns
    -------
        df: a pandas dataframe
    """
    try:
        if region==1:
            my_data = pd.read_csv(photom_name, usecols=Use_columns[1], skiprows=Photom_skip_header)
        elif region==2:
            my_data = pd.read_csv(photom_name, usecols=Use_columns[2], skiprows=Photom_skip_header)
        df = pd.DataFrame(my_data)
        # convert all times to milliseconds
        if Photom_time_base!=1: df[Timestamp]=df[Timestamp]*Photom_time_base
        
    except IOError:
        print(File_error, photom_name,"***\n")

    return df

#==================================================        
def read_behav_file(behav_name, Behav_header_size):
    """
    read behavioral data from .xlsx file (processed data)
    results include event identity and timestamp
    convert times to milliseconds
    Parameters
    -----------
       behav_name: full name of file
    Returns
    -------
        behav_lines: a Pandas dataframe with timestamps and event_name columns
    """
    try:
            if Behav_ext==Behav_ext_WhandA:                              # WhandA analyzed file
                behav_lines = pd.read_csv(behav_name, sep="\t", header=None, skiprows=1)
                with open(behav_name, "r") as behav_file:
                    titles=behav_file.readline()
                    behav_lines.columns = titles.split('\t')
            else:            
                xls = pd.ExcelFile(behav_name)
                behav_lines = pd.read_excel(xls, Sheet_name)             # pandas data frame

            # convert times to milliseconds
            behav_lines[Time_column]=behav_lines[Time_column]*Behav_time
            
    except IOError:
        print(File_error, behav_name,"***\n")
        exit_on_keypress()                                                                      # fatal error

    return behav_lines

#==================================================
def get_behav_times(behav_lines, Behav_time_unit):
    """
    compute a list of event times from behav file
    Parameters
    -----------
       behav_lines: a Pandas dataframe with timstamps and event_codes columns
       Behav_time_unit: in milliseconds
    Returns
    -------
        time_list: in milliseconds
    """
    time_list=[]
    if TTL_on and not TTL_on in behav_lines.columns:
        print("\n*** Missing column:", TTL_on,"***")
        exit_on_keypress()
    if Align_on and not Align_on in behav_lines.columns:
        print("\n*** Missing column:", Align_on,"***")
        exit_on_keypress()

    for index, line in behav_lines.iterrows():
        time, event = line[Time_column], line[Event_column]
        if not isinstance(event, str):
            print("\nAnomaly line", index+1,": event is not a string")
            print("Please check content of behavioral event file (.xlsx)")
            exit_on_keypress()
        event_code=event[Event_code_size:]
        if TTL_on:
            time+=line[TTL_on]*Behav_time_unit

        # convert time to milliseconds and add TTL coding
        if event_code in Synchro_codes:                                                                                  # lever_press
            for TTL in Synchro_codes[event_code]:
                time_list+=[time+TTL]

        if Add_reward and Reward_column in behav_lines.columns and line[Reward_column]==1:                 # add reward
            event_code="D1"
            for TTL in Synchro_codes[event_code]:
                time_list+=[time+TTL]
                        
    return time_list 

#==================================================
def near_matches(targets, times, span):
    """
    search for near matches between two sorted time lists.
    explore all values from both lists in parallel
    a match occurs when abs(times[j]-targets[i])<= span
    abs(times[j]-targets[i]) is fitting error of match
    Parameters
    -----------
        targets: list of times, in milliseconds
        times: list of times, in milliseconds
        span: allowed error for matching, in milliseconds
    Returns
    -------
        matches: number of matches within span
        fit: sum of absolute fitting errors for matches only
        bias: sum of relative fitting errors for matches only
    """
    matches, fit, bias = 0, 0, 0
    if not targets: return matches, fit, bias

    i, j = 0, 0
    # tests borders
    if 0<times[j]-targets[i]<span:                                      # first time is just above target
        matches+=1
        fit+=times[0]-targets[0]
        bias+=times[0]-targets[0]
        i+=1                                                                      # next target

    # find two times bracketing target
    while i<len(targets) and j+1<len(times):                      # check index range
        
        if times[j]>targets[i]:                                               # time too high
            i+=1                                                                  # next target
            continue
        if times[j]==targets[i]:                                             # perfect match
            matches+=1
            i+=1                                                                  # next target
            continue   
        if times[j+1]<=targets[i]:                                           # time too low 
            j+=1                                                                  # next time
            continue
        
        # now target is between times[j] and times[j+1]
        lower_interval=targets[i]-times[j]
        upper_interval=times[j+1]-targets[i]

        # look for the shorter of two intervals
        if upper_interval<lower_interval:                            # upper is shorter
            if upper_interval<=span:
                matches+=1                                                 # upper is within span
                fit+=upper_interval
                bias+=upper_interval

        else:
            if lower_interval<=span:                                     # lower is shorter
                matches+=1                                                     # lower is within span
                fit+=lower_interval
                bias+=-lower_interval
            
        i+=1                                                                      # next target
        continue                                                           

        j+=1                                                                     # next time

    if 0<targets[-1]-times[-1]<span:                                 # last time is just below target
        matches+=1
        fit+=targets[-1]-times[-1]
        bias+=times[-1]-targets[-1]
    
    return matches, fit, bias
    
#==================================================
def store_best(dt, matches, fit, bias, best):
    """
    first compare number of matches, then bias to current best fit
    Parameters
    -----------
        dt: offset photom_times - behav_times
        matches: number of matches within span
        fit: sum of absolute fitting errors for matches only
        bias: sum of relative fitting errors for matches only
    Returns
    -------
        best: a tuple dt, matches, fit, bias
    """    
    if matches>best[1]: return dt, matches, fit, bias         
    elif matches==best[1] and abs(bias)<abs(best[3]): return dt, matches, fit, bias
    return best

#==================================================
def align(li1, li2, span, start, end):
    """
    blind alignment between two time series behav_times and photom_times
    search for matches with an accuracy of 'span' 
    Parameters
    -----------
        li1, li2: lists of behav_times and photom_times, in milliseconds
        span: allowed error for matching, in milliseconds
    Returns
    -------
        dt: offset photom_times - behav_times
        matches: number of matches within span
        fit: sum of absolute fitting errors for matches only
        bias: sum of relative fitting errors for matches only
        fit, bias, matches, size
    """    
    # calculate sizes and time ranges
    size1, size2 = len(li1), len(li2)
    size=min(size1, size2)
    min_t, max_t= li2[0]-span, li2[-1]+span

    # look for best offset (step = 1.9 span)
    best=0, 0, 0, 0
    for dt in range(start, int(end+1), int(1.9*span)):
        times=[t1+dt for t1 in li1 if min_t<= t1+dt <=max_t]
        matches, fit, bias = near_matches(times, li2, span)   # test all
        best=store_best(dt, matches, fit, bias, best)

    if not ask_offset:
        # refine by trying some values near best offset (step = Refine)
        dt=best[0]-span
        for i in range(2*int(span/Refine)):
            dt+=Refine
            times=[t1+dt for t1 in li1 if min_t< t1+dt <max_t]
            matches, fit, bias = near_matches(times, li2, span)      # test all
            best=store_best(dt, matches, fit, bias, best)
       
        # refine again by trying all values near best offset (step = 1 ms)
        dt=best[0]-Refine
        for i in range(2*Refine):
            dt+=1
            times=[t1+dt for t1 in li1 if min_t< t1+dt <max_t]
            matches, fit, bias = near_matches(times, li2, span)      # test all
            best=store_best(dt, matches, fit, bias, best)

    if best[1]==0: return None, 0, None, None, None
    return *best, size

#===================================================== 
def make_log(summary_name, log_filename, behav_times, photom_times, offset, fitstring):
    """
    create a file with all matched event times
    append fit info to global log file
    Parameters
    -----------
        summary_name: string name of summary .txt log file to create
        log_filename: string name of .txt log file to create
        behav_times: list of event times (ms) and pulse codes read from behav file
        photom_times: list of pulse codes read from photom file
        offset: in ms to be added to behav_times
        fitstring: text info about goodness of fit
    Returns
    -------
        creates a .csv file (delimiter ; ) with 6 columns
        pulse number, behav_time, aligned time, bracketing photom times, alignment error (ms)\n
    """
    try:
        # log summary file (append)
        with open(summary_name, "a") as log_file:
            line=log_filename+"\noffset: "+'{o: .3f}'.format(o=offset/1000)+"\n"+fitstring+"\n"
            log_file.write(line)

        # detailed log file            
        with open(log_filename, "w") as log_file:
            # title line
            line=log_filename+"\noffset: "+'{o: .3f}'.format(o=offset/1000)+"\n"+fitstring+"\n"
            log_file.write(line)
            log_file.write("event\tbehav_t\talign_t\tlow_phot_t\thigh_phot_t\tmatch (ms)\n")
            i=0
            lo_time=photom_times[i]
            hi_time=photom_times[i]
            for n, b_time in enumerate(behav_times):
                if np.isnan(b_time):
                    print('Error: missing time after', int((b2p_time-offset)/Behav_time))
                    exit_on_keypress()
                # convert behavioral time to photometry time
                b2p_time=b_time+offset
                # find lower (pt) and higher (npt) surrounding photometry times
                while photom_times[i]<b2p_time and i<len(photom_times)-1:
                    lo_time=photom_times[i]
                    i+=1
                    hi_time=photom_times[i]
                err=int(b2p_time-lo_time) if int(b2p_time-lo_time) < int(hi_time-b2p_time) else int(b2p_time-hi_time)
                
                line='{l: 0}\t{bt: .1f}\t{bpt: .3f}\t{lpt: .3f}\t{hpt:.3f}\t{x: 0}'.format(
                            l=n+1, bt=b_time/1000, bpt=b2p_time/1000, lpt=lo_time/1000, hpt=hi_time/1000, \
                            x=err)
                if hi_time<b2p_time: line+="; no match"
                log_file.write(line+"\n")
            
    except IOError:
        print(File_error, log_filename," file may be open ***\n")
        exit_on_keypress()

#==================================================
def export_behav(photom_name, Behav_database_name, behav_lines, Behav_time, offset, min_t, max_t):
    """
    use offset to convert trials from behavioral file to photometry times
    only trials within photometry time range are stored
    append to Behav_database file
    Parameters
    -----------
        photom_name: string, photometry filename (short)
        Behav_database_name: string, global
        behav_lines: list of lines or data frame read from behavior file
        Behav_time: float, global
        offset: float (ms) from behavior to photometry
        min_t, max_t: time limits of photometry
    Returns
    -------
        append trial info to Behav_database file
        trial_times: a list of tuples (time, check_code) in photometry time frame
    """
    trial_times=[]
    try:
        with open(Behav_database_name, 'a') as behav_file:
            # compute session from name
            if Session_info:
                session=os.path.split(photom_name)[-1][Session_info[0]:Session_info[1]]
            
            # write title line
            if os.path.getsize(Behav_database_name) == 0:                 # if file is empty
                if Session_info and not "seance" in behav_lines.columns:
                    behav_file.write('\t'.join(list(behav_lines.columns))+"\tseance\tcheck\n")
                else:
                    behav_file.write('\t'.join(list(behav_lines.columns))+"\tcheck\n")

            # write trial lines        
            for index, line in behav_lines.iterrows():
                if Session_info:
                     line["seance"]=session
                time = offset + line[Time_column]                                   # convert time
                if Align_on:
                    time+= line[Align_on]*Behav_time_unit               # alignment on an event
                check_code = str(int(random()*100_000))               # to verify match of Photom_database with Behav_database
                if time > min_t - Minus_window and time < max_t - Plus_window:
                    trial_times.append((time, check_code))                # memorize trial times
                    line_string='\t'.join([str(x) for x in line])
                    behav_file.write(line_string+'\t'+check_code+'\n')

    except IOError:
        print(File_error, log_filename," file may be open ***\n")
        exit_on_keypress()
    return trial_times

#==================================================
def plot(title, x, y, z=None, yname='', zname=''):
    global Visualize
    if Visualize:
        graph.plot(x, y, label=yname)
        if z is not None:
            graph.plot(x, z, label=zname)
        fig = graph.gcf()
        fig.canvas.manager.set_window_title(title)
        if yname or zname: graph.legend()
        graph.show()
        try: 
            print("\n*** Press Ctrl-C during pause to quit ***\n     Database will not be modified !")
            time.sleep(Pause_time)
        except:
            os._exit(1)
    
#==================================================
def detrend(signal):
    """
    compute global linear trend and remove it without changing DC level
    Parameters
    -----------
        signal: a pandas dataframe column
    Returns
    -------
        signal
    """
    x = np.arange(len(signal))
    y = signal.values
    coeffs = np.polyfit(x, y, deg=1)
    coeffs[1]=0.0
    trend = np.polyval(coeffs, x)
    return signal-trend

#==================================================
def compute_delta_f(signal, control):
    """
    compute deltaF/F over whole session
    Divide_by_mean is the same as not dividing, except for scale
    Parameters
    -----------
        signal: a pandas dataframe column
        control: a pandas dataframe column
    Returns
    -------
        delta_f
        delta_f_f
    """
    # DC option
    control_mean=np.array(control).mean()                                   # mean over whole part
    centered_control=control-control_mean
    
    # compute deltaF
    if Keep_DC_level:
        delta_f = signal - centered_control
    else:
        delta_f = signal - control

    # compute deltaF/F with F mean or F instantaneous
    if Divide_by_mean:
        delta_f_f = delta_f *100 / control_mean
    else:
        delta_f_f = delta_f  *100 / control

    # Detrending
    if Detrend:
        delta_f_f =detrend(delta_f_f )                                                # remove global linear trend
    
    return delta_f, delta_f_f

#==================================================
def export_photom(region, Photom_database_name, photom_data, tim, raw_sig, raw_iso, trial_times):
    """
    process and filter data
    compute deltaF/F, mean and stdev around trials
    from press + Minus_window to press + Plus_window
    append to Photom_database file
    Parameters
    -----------
        region: 1 or 2
        Photom_database_name: string, global
        tim, raw_sig, raw_iso: columns in a pandas dataframe
        trial_times: a list of tuples (time, check_code) in photometry time frame
        linear_fit: coefficients to fit isosbectic to signal
    Returns
    -------
        append photometry info to Photom_database file
    """
    global Visualize
    
    signal, iso = raw_sig, raw_iso
    plot("Signal/Iso Channel "+str(region), tim, signal, iso, 'signal', 'iso')      # plot raw data if Visualize    
##    plot("Signal/Glitch Channel "+str(region), tim, raw_sig, signal, 'raw', 'signal')      # plot raw data if Visualize    
##    plot("Control/Glitch Channel "+str(region), tim, raw_iso, iso, 'raw', 'iso')        # plot raw data if Visualize

    # linear fit of control to signal
    linear_fit=(1,0)                                                                                # no fit
    control=iso
    if  Linear_regression:
        linear_fit=np.polyfit(iso, signal, 1)
        control=linear_fit[0]*iso+linear_fit[1]
        plot("Fitted control Channel "+str(region), tim, signal, control, 'signal', 'fitted iso')  # plot data if Visualize
   
    # globalized deltaf/F
    delta_f, delta_f_f = compute_delta_f(signal, control)
    ref=control
    if Divide_by_mean: ref=np.array(control).mean()
    plot("deltaF Channel "+str(region), tim, delta_f, delta_f_f, 'deltaF', 'DeltaF/F')  # plot data if Visualize       

    # compute global z parameters mean and stdev
    mean, stdev = 0, 1
    if Globalize_z_score:       
        mean = delta_f_f.mean()
        stdev = delta_f_f.std()
        
    if not Visualize:
        try:
             with open(Photom_database_name, 'a') as photom_file:
                # write title line
                if os.path.getsize(Photom_database_name) == 0:                 # if file is empty
                    titles=[str(i) for i in range(Minus_window, Plus_window+Photom_interval, Photom_interval)]
                    photom_file.write("time\tcheck\tmean\tstdev\tgain\tshift\t"+'\t'.join(titles)+"\n")

                # browse trials
                nb_colons=0
                for time, check_code in trial_times:
                    start_time = time + Minus_window                                        # range around event
                    end_time = time + Plus_window + Photom_interval

                    # channel slices
                    period = tim[(tim>=start_time) & (tim<end_time)]           
                    sig=signal[(tim>=start_time) & (tim<end_time)]
                    cont=control[(tim>=start_time) & (tim<end_time)]          # fitted if Linear_regression
                    delff=delta_f_f[(tim>=start_time) & (tim<end_time)]

                    # compute z parameters mean and stdev
                    if not Globalize_z_score:       
                        mean = delff.mean()
                        stdev = delff.std()

                    # write trial data
                    if not nb_colons: nb_colons=len(delff)                             # OK except if first line is too long
                    line_string='\t'.join([str(time), str(check_code), str(mean), str(stdev), str(linear_fit[0]), str(linear_fit[1])])+'\t'
                    if nb_colons<len(delff):                                                       # delete extra colons
                        delff=delff.iloc[:-1]
                        print("deleting 1 value at time", time)
                    line_string+='\t'.join([str(x) for x in delff])
                    photom_file.write(line_string+'\n')

        except IOError:
            print(File_error, Photom_database_name," file may be open ***\n")
            exit_on_keypress()
            
#===================================================== 
def dialog(prompt):
    """
    prompt user for a response
    return response as text
    """
    print(prompt+"> ", end="")                    
    try: txt=input()
    except ValueError: txt=""
    return txt
        
#===================================================== 
def test_align():
    """
    test alignment procedure in debugging phase
    exit before running full program
    """
    list1=[10, 15, 17, 23, 30]
    list2=[11, 14.8, 17, 24, 29.5]
    
    print("*** ALIGNMENT TEST ***\n")                    
    offset, matches, fit, bias, size=align(list1, list2, 2, start=0, end=10)              # span=2
    if offset is not None:
        print("Offset: {time:.3f} s".format(time=offset))
    else:
        print("\n*** No data to align ! ***")
    exit_on_keypress()
        
#=====================================================
def exit_on_keypress():
    print("\nPress a key to exit")
    try: input()                                                     
    except ValueError: pass
    os._exit(1)

#=====================================================
def create_parameters(parameters):
# create and initialize variables from parameters
    faux=["f", "n", "no", "non", "false"]
    booleans=["v", "o", "y", "yes", "oui", "true"]+faux
    for k, v  in parameters.items():
        if isinstance(v, str) and not k in not_bool:   # make sure booleans are recognized
            if v.lower().strip(' ') in booleans:
                v=not(v.lower().strip(' ') in faux)
                parameters[k]=v
            else:
                print("\nIncorrect parameter", k, ":", v)
                print("Allowed values are :", booleans)
                exit_on_keypress()
        globals()[k]=v

#================================================== MAIN PROGRAM
# test alignment procedure
##test_align()                                                                    # only in debugging phase

# set and assign parameters
parameters=set_parameters(Param_file)            # get last parameters used, adjust if necessary
create_parameters(parameters)
print(parameters)

Synchro_codes=eval(Synchro_codes)   # convert string to dict
Behav_database_name[1]="Behav_data1.xls" if Regions==2 else "Behav_data.xls" 
Photom_database_name[1]="Photom_data1.xls" if Regions==2 else "Photom_data.xls" 

# current directory
directory= os.getcwd()                                                        # current program and data directory
directory_in= os.path.join(directory, Input_subdir)
directory_out= os.path.join(directory, Output_subdir)
directory_logs=os.path.join(directory, Logs_subdir)
if not Visualize:
    make_subdir(directory_out)                                           # create dir if necessary
    make_subdir(directory_logs)                                          # create dir if necessary

print("Working on", directory)

# files in current directory (remove caps)
behav_list, Behav_time = get_file_list(directory_in,  Behav_ext, Behav_ext_WhandA, Behav_time, Behav_time_Whanda)

# loop on all files
for behav_name in behav_list:

    offset=None
    for region in range(1,Regions+1):

        if offset is None:
            # read behavior file in totality
            photom_name=os.path.join(os.path.splitext(behav_name)[0])+Photom_ext        
            print("\nOpening", behav_name.split("\\")[-1])
            behav_lines=[]
            behav_lines = read_behav_file(behav_name, Behav_header_size)

            # read events and TTL inputs
            behav_times=get_behav_times(behav_lines, Behav_time_unit)
            photom_times=get_photom_times(photom_name, Photom_time_base, Photom_interval, Photom_skip_header)
            if not photom_times:
                print("\n*** No TTL inputs found ***")
                break
            Max_time=photom_times[-1]

            # synchronize        
            print("Behavior:", len(behav_times),"events, Photometry:", len(photom_times),"inputs")
            if ask_offset:
                offset=dialog("\nPlease select offset in ms. ")
                try: offset=int(offset)
                except ValueError:
                    exit_on_keypress()
                offset, matches, fit, bias, size = align(behav_times, photom_times, span=Approximation, start=offset, end=offset)
            else:
                offset, matches, fit, bias, size  = align(behav_times, photom_times, span=Approximation, start=Min_offset, end=Max_offset)
            if offset is None:
                print("\n*** No data to align ! ***")
                continue                                                                     # do not create event timestamps
            print("Offset: {time:.3f} s".format(time=offset/Photom_out_unit))

            # log aligned events
            if not Visualize:
                fitstring="Fit: {time:.1f} ms  ".format(time=fit/matches)
                fitstring+="Bias: {time:.1f} ms  ".format(time=bias/matches)
                fitstring+="Matches: "+str(matches)+ " / "+str(size)
                print(fitstring, end="   ")
                if matches/size<Reliability_threshold:
                    print("*** Warning: unreliable alignment ***", end="   ")
                print()
                log_filename=os.path.splitext(photom_name.split("\\")[-1])[0]+Log_ext
                log_global_name=os.path.join(directory_out, Log_summary_name)
                log_filename=os.path.join(directory_logs, "_log_"+log_filename)
                make_log(log_global_name, log_filename, behav_times, photom_times, offset, fitstring)      

        # read photom data for region            
        photom_data=get_photom_data(region, photom_name, Photom_time_base, Photom_skip_header)
        ignore=int(Ignore_first_seconds*1000/(Photom_interval*Photom_time_base))
        iso=photom_data[Iso[region]][ignore:]
        sig=photom_data[Sig[region]][ignore:]
        tim=photom_data['TimeStamp'][ignore:]

        # add to behavior database
        trial_times=[]
        if not Visualize:
            behav_filename=os.path.join(directory_out, Behav_database_name[region])
            min_t, max_t = photom_data[Timestamp][ignore], list(photom_data[Timestamp])[-1]
            trial_times=export_behav(photom_name, behav_filename, behav_lines, Behav_time, offset, min_t, max_t)
        
        # add to photometry database
        photom_filename=os.path.join(directory_out, Photom_database_name[region])
        export_photom(region, photom_filename, photom_data, tim, sig, iso, trial_times)

exit_on_keypress()

