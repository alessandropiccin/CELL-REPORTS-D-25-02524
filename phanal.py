# -*- coding: ISO-8859-1 -*-
import os
from pathlib import Path
import pandas as pd
import numpy as np
from random import random

"""
Photometry analysis.
Read behavior and photometry database files from a sub-folder of wherever program is run from.
Create a single text file of selected trials and binned photometry data
"""
print("\nPhanal - February 2026 - Alain R. Marchand\n")

Regions=1                                                   # 1 region (Iso+Sig), 2 regions (2 Iso+2 Sig)
Behav_database_name, Photom_database_name=dict(), dict()
Region_marker=dict()

# Input parameters__________________________________________________________________

Behav_database_name[0]="Behav_data.xls"            # *** CHOOSE DATABASES HERE ***      
Behav_database_name[1]="Behav_data1.xls"                  
Behav_database_name[2]="Behav_data2.xls"                
Photom_database_name[0]="Photom_data.xls"
Photom_database_name[1]="Photom_data1.xls"
Photom_database_name[2]="Photom_data2.xls"
Region_marker[0]=""
Region_marker[1]="_1"
Region_marker[2]="_2"
First_column=6
#_____________________________________________________________________________________

Input_subdir="Database"                             # sub directory containing input data
##Photom_interval=100                                   # sampling in milliseconds (default)
Param_ext=".txt"

# Output parameters
Output_subdir="Events"                             # sub directory containing output data
Event_ext=".xls"
bins, zscore, maxi, mini, tmax, tmin, area, equal = 'bins', "z-score", "max", "min", "tmax", "tmin", "area", "="
ignore_cols=6                                            # time	check	mean	stdev	gain	shift

File_error="\n*** Error: cannot access file ***"
Parameter_error="\n*** Error: invalid parameter ***"

#==================================================        
def get_parameters_from_file(parameter_file):
    """
    read parameter text file; empty lines and text after # are ignored
    specifies whether to convert data to z-scores
        format is 'z-score'
    specifies a list of analysis bins
        format is 'bin=start, end, width' or 'bin=start, end'
        single bin if end=start+width
        multiple bins may be specified on different lines
    specifies conditions for events using column names
        format is name=value or name=value1:value2 (for a range)
        multiple conditions are allowed ('or' if same name, 'and' if different)
    Parameters
    -----------
       parameter_file: full name of file
    Returns
    -------
        params: a dict {parameter_name: value}
    """
    behav_lines.columns= behav_lines.columns.str.lower()      # rename columns
    colnames=list(behav_lines.columns)                                  # all lower case
##    print(colnames)
    params={}

    try:
        with open(parameter_file, "r") as param_file:
            for valid_line in param_file.readlines():
                if not valid_line.strip(): continue                              # ignore empty lines
                valid_line=valid_line.lower()                                    # all lower case
                valid_line=valid_line.split("#")[0]                             # remove comments 
                valid_line=valid_line.replace(" ","")                         # remove spaces
                valid_line=valid_line.replace("\t","")                        # remove tabs

                found=False
                # max, min, tmax, tmin, area
                for name in zscore, maxi, mini, tmax, tmin, area:
                    if valid_line.startswith(name):
                        found=True
                        if valid_line.startswith(name+"=false"):
                            params[name]= False
                        else:
                            params[name]= True
                        break

                # bins
                if not found:
                    if valid_line.startswith(bins):
                        valid_line=valid_line.replace(bins+"=","")
                        param_line=valid_line.split(",")                           # split line
                        if len(param_line)<3: raise ValueError
                        if not param_line[2]: param_line[2]=str(Photom_interval)  # fill in step     
                        param_line=tuple([int(x) for x in param_line[:3]]) # convert to numbers
                        params[bins]=params.get(bins, [])+[(param_line)] # add bins to list
                            
                    # conditions on trials
                    elif equal in valid_line:
                        name, value = valid_line.split(equal)
                        if not name in colnames: raise ValueError
                        value=value.strip('\n')
                        params[name]=params.get(name,[])+[value]     # add value to list

                    else: raise ValueError

    except IOError:
        print(File_error)
        print(parameter_file,"\n")
        ask_and_stop()
        
    except ValueError:
        print(Parameter_error)
        print(valid_line)
        ask_and_stop()
        
    return params   

#==================================================        
def analyze_value(value):
    """
    try converting value to a numerical range
    Parameters
    -----------
       value: text or single number or range separated by ':'
    Returns
    -------
        value: a list of one string or a list of two floats defining a range
    """
    try: value=int(value)
    except ValueError: pass
    if isinstance(value, int): value=[value, value]
    if isinstance(value, str): value=[value]
    return value

#==================================================
def make_trial_list(behav_lines, params):   
    """
    select trials according to conditions
    Parameters
    -----------
        behav_lines: list of lines or data frame read from behavior file
        params: a dict {parameter_name: value}, includes conditions
    Returns
    -------
        trial_times: a list of tuples (trial_number, check_code)
    """
    trial_times=[]
    conditions=[key for key in params.keys() if key in behav_lines.columns]

    try:    
        for index, line in behav_lines.iterrows():
            ok=True                                                                              # 'and' condition
            for name in conditions:                                                       
                value=params[name]
                found=False                                                                    # 'or' condition
                for v in value:                                                                  
                    if isinstance(v, str) and ':' in v:                                     # detect range
                        v=v.split(':')
                        v=[float(x) for x in v]
                        start, end = v
                        if start <= float(line[name]) <=end :
##                            print(start, float(line[name]), end)
                            found=True
                    else:                                                                            # a string or number
                        if line[name].lower()==str(v).lower():
                            found=True
                if not found: ok=False
            if ok:                                                                                   # accept trial
##                print(line['essai'])
                trial_times+=[(index, int(line["check"].strip('\n')))]
                
    except ValueError:
        print("*** Error while testing conditions ***")
        print(name,"=",value)
        ask_and_stop()
        
    return trial_times

#==================================================        
def pd_from_text_file(text_name, convert=None):
    """
    read text data from .xls text file (processed data) into a Pandas dataframe
    option to convert values into specified type
    Parameters
    -----------
       text_name: full name of file
       convert: optional, a type (int, float,...)
    Returns
    -------
       text_lines: a Pandas dataframe
    """
    try:
        with open(text_name, "r") as text_file:
            titles=text_file.readline().strip('\n').split('\t')
            lines=[l.strip('\n').split('\t') for l in text_file.readlines()]
            text_lines=pd.DataFrame(lines)
            if len(text_lines.columns)!=len(titles):
                print("*** Anomaly: data found afer last column ***")
                ask_and_stop()            
            text_lines.columns=titles
            # print(text_lines)
            if convert: text_lines=text_lines.astype(convert)
            
    except IOError:
        print(File_error, text_name,"***\n")
        ask_and_stop()                                                 # fatal error

##    print(text_lines)
    return text_lines

#==================================================
def get_sampling_interval(data):
    """
    extract sampling interval from data titles
    Parameters
    -----------
        data: data frame, selected trials, no id columns
    Returns
    -------
        Photom_interval: time interval between data columns in ms
    """
    return int(data.columns[First_column+1]) - int(data.columns[First_column])
    
#==================================================
def compute_histogram(data, params):
    """
    pool data into histogram with specified bins
    else compute max height and position for each bin if required
    Parameters
    -----------
        data: data frame, selected trials, no id columns
        params: a dict {parameter_name: value}
    Returns
    -------
        histo: data frame, selected trials, no id columns
    """
    # extract intervals
    intervals=params["bins"]
    histo=pd.DataFrame()
    
    for k, (start, end, step) in enumerate(intervals):
        for i in range(start, end, step):
            one_bin=data.loc[ : , [str(t) for t in range(i, i+step, Photom_interval)]]

            name="("+str(k+1)+") "+str(float(i/1000))+"_"+str(float((i+step)/1000))
            if step==Photom_interval: name="("+str(k+1)+") "+str(float(i/1000))
            
            if params.get(maxi, False):
                histo[name]=one_bin.max(axis='columns')

            elif params.get(tmax, False):
                histo[name]=one_bin.idxmax(axis='columns')

            elif params.get(mini, False):
                histo[name]=one_bin.min(axis='columns')

            elif params.get(tmin, False):
                histo[name]=one_bin.idxmin(axis='columns')

            elif params.get(area, False) and step>=2*Photom_interval:
                rows=[]
                for index, line in one_bin.iterrows():
                    npa=np.array(line)
                    rows+=[np.trapz(npa)]
                histo[name]=rows

            else:
                histo[name]=one_bin.mean(axis='columns')

    return histo

#==================================================
def export_event_shapes(behav_select, histo, params):
    """
    store results of an analysis to .xls file
    Parameters
    -----------
        behav_select: data frame from behavior database with selected parameters
        histo: data frame computed with selected parameters
        params: a dict {parameter_name: value}
    Returns
    -------
        write to file (overwrite)
    """
    try:
        print("EVENT FILE", event_filename)
        with open(event_filename, 'w') as event_file:
            # write parameters
            param_list=[]
            for name, value in params.items():
                param_list+=[name+'='+str(value)[1:-1] if not name in [zscore, area] else name+'='+str(value)]
            param_string="\n".join(param_list)    
            event_file.write("Parameters\n"+param_string+"\n")

            # concatenate data
            histo.index=range(len(histo.index))                                    # match indices
            behav_select.index=range(len(histo.index))                        # match indices
            data=pd.concat([behav_select, histo], axis='columns')

            # write title line
            event_file.write('\t'.join(list(data.columns))+"\n")

            # write trial lines        
            for index, line in data.iterrows():
                strline=[str(v) for v in line]
                event_file.write('\t'.join(strline)+"\n")

    except IOError:
        print(File_error, event_filename," file may be open ***\n")
        ask_and_stop()

#===================================================== 
def get_regions(directory):
    """
    check filenames to deterrmine the number of regions
    """
    Regions=1
    if os.path.isfile(os.path.join(directory, Behav_database_name[2])): Regions=2
    elif os.path.isfile(os.path.join(directory, Behav_database_name[0])): Regions=0 
    elif not os.path.isfile(os.path.join(directory, Behav_database_name[1])):
        print("\nError: no behavioral database !")
        ask_and_stop()     
    print('\n Analysing', max(Regions, 1), "region(s)")
    return Regions
               
#===================================================== 
def dialog(prompt):
    """
    prompt user for a response
    return response as text
    """
    print(prompt+": ", end="")                    
    try: txt=input()
    except ValueError: txt=""
    return txt
               
#===================================================== 
def ask_and_stop():    
    print("Press a key to exit")
    try: input()                                                     
    except ValueError: pass
    os._exit(1)

#================================================== MAIN PROGRAM

directory= os.getcwd()                                                        # current program and data directory
directory_in= os.path.join(directory, Input_subdir)
directory_out= os.path.join(directory, Output_subdir)
if not os.path.isdir(directory_out):                                        # test if directory_out exists
    print(File_error, directory_out,"***\n")
    ask_and_stop()
    
print("Working on", directory)
Regions=get_regions(directory_in)
parameter_file=dialog("\nFile describing your analysis ")
##parameter_file="params"
if not parameter_file: ask_and_stop()

for region in range(min(Regions, 1), max(Regions+1, 1)):
    Behav_database=Behav_database_name[region]    
    Photom_database=Photom_database_name[region]
    region_marker=Region_marker[region]

    # read behavior file in totality
    behav_name=os.path.join(directory_in, Behav_database)
    print("Opening", behav_name.split("\\")[-1])
    behav_lines = pd_from_text_file(behav_name)
        
    # read deltaF file in totality
    photom_name=os.path.join(directory_in, Photom_database)
    print("Opening", photom_name.split("\\")[-1])
    photom_lines = pd_from_text_file(photom_name, convert=float)
    Photom_interval=get_sampling_interval(photom_lines)                             
        
    # get parameters from file
    parameter_file=os.path.join(directory_out, parameter_file)
    if not parameter_file.endswith(Param_ext): parameter_file+=Param_ext
    params=get_parameters_from_file(parameter_file)
    print("Parameters", params)

    # build list of trials and select rows
    trial_list=make_trial_list(behav_lines, params)
    trial_numbers=[x[0] for x in trial_list]
    if not trial_numbers: print("\n*** Selection is empty ***\n")
    check_codes=[float(x[1]) for x in trial_list]
    behav_select=behav_lines.loc[trial_numbers]
    photom_select=photom_lines.loc[trial_numbers]
    bad_select=photom_select.loc[(photom_select["check"]!=check_codes)]
    if len(bad_select.index):
        print("\n*** Error: Databases do not match ***")
        ask_and_stop()
        
    # extract data
    delta_f_f_select=photom_select.iloc[:, ignore_cols:].astype(float)

    # compute histogram with z-scores if specified
    if params.get(zscore, False):
        mean_select=photom_select["mean"].astype(float)
        stdev_select=photom_select["stdev"].astype(float)
        z_score_select=delta_f_f_select.sub(mean_select, axis='rows')
        z_score_select=z_score_select.div(stdev_select, axis='rows')
        
        histo=compute_histogram(z_score_select, params)
    else: 
        histo=compute_histogram(delta_f_f_select, params)
        
    # add to event file
    event_filename=os.path.splitext(parameter_file)[0]+region_marker+Event_ext
    export_event_shapes(behav_select, histo, params)

print("Analysis complete")
ask_and_stop()


