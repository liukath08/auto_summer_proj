import logging
import matplotlib.pyplot as plt
import pandas as pd


import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl

from pathlib import Path

Path("data").mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.DEBUG)

channels = [0]
by_channel = False

lower_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.LT,
    ecl.LimitLogic.OR,
    -2.0,
)

upper_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    2.0,
)

params = {
    #Current range  
	# units in Amps, with p, n, u ,n, a for pico, nano, micro, milli, and Amps
    # (p100, n1, n10,n100, u1, u10, u,100, m1, m10, m100, a1, KEEP, BOOSTER, AUTO)
	"current_range": ecl.IRange.m10, 
    
	#Voltage range 
    #(v2_5, +-2.5V),(v5, +-5V),(v10, +-10V), (AUTO, automatic voltage range)
	"voltage_range": ecl.ERange.AUTO, 

	#Hardware filtering
    #(k50: 50kHz), (k1: 1kHz), (h5: 5Hz), (OFF)
	"filter": ecl.Filter.h5, 

	#Average, 
	# True = average, False = no average)
	"average": True, 

    #Hardware bandwidth 
	#(BW1-9), 1= slow, 9=fast
	"bandwidth": ecl.Bandwidth.BW5, 

    #Electrode Connection
    #(STND, CETOGRND, WETOGRND, HV)
    "electrode_connection": ecl.ElectrodeConnection.STND,

    #Channel Mode
    #(GROUNDED, FLOATING)
    "channel_mode": ecl.ChannelMode.GROUNDED,
           
	#If step is vs initial or previous
    #Array of 20 boolean, defualt false
	'vs_initial': [], 

    #Apply I (A)
     #Array of up to 20 currents, in Amps
    "currents": [-0.0000000004],#List of currents in Amps
    
	#Duration of applied currents (s) 
	#Array of up to 20 durations, in seconds
    'durations': [ 2,2,2,2,2,2 ], 

    #Maximum time interval between recordedpoints.
	'time_interval': 1.0, 

 	#Max current change bewteen recorded points
	"current_interval": 1e-3,

    #List of LimitConfig tuples defining limits for the technique. 
    # LimitConfig objects should be constructed with configure_limit. Up to 3 limits can be supplied.
    "limits": [lower_voltage_limit, upper_voltage_limit], 


    #How to exit the technique when a limit is violated.   
    #NEXTSTEP, NEXTTECHNIQUE, STOP
    "exit_condition": ecl.ExitCondition.STOP, 
     
    # Cycles, starts from 0
    'cycles': 4, 
}

save_path = 'data/cp-limit'
if not by_channel:
	# file if saving individually
	save_path += '.csv'

bl = ebl.BiologicDevice("USB0")
program = ebp.CPLimit(bl, params, channels=[0])

program.run()
program.save_data( save_path, by_channel = by_channel )

#plot


def plot_voltage_vs_time():
    print("Reading saved CPLimit CSV...")

    # easy-biologic writes an extra first line.
    # The actual column headers begin on the second line.
    df = pd.read_csv(save_path, skiprows=1)

    time_col = "Time [s]"
    voltage_col = "Voltage [V]"

    if time_col not in df.columns:
        raise ValueError(f"Could not find time column: {time_col}")

    if voltage_col not in df.columns:
        raise ValueError(f"Could not find voltage column: {voltage_col}")

    time = df[time_col]
    voltage = df[voltage_col]

    plt.figure(figsize=(6, 5))
    plt.plot(time, voltage)

    plt.xlabel("Time (s)")
    plt.ylabel("Voltage (V)")
    plt.title("CPLimit: Voltage vs Time")

    plt.tight_layout()
    plt.savefig(  "data/CPLimit_voltage_vs_time.png", dpi=300)
    plt.close()

    print("Saved voltage-vs-time figure.")

plot_voltage_vs_time()