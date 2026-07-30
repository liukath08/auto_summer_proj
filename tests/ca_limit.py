
import logging
import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl
from pathlib import Path

Path("data").mkdir(parents=True, exist_ok=True)


logging.basicConfig( level = logging.DEBUG )

channels = [ 0 ]
by_channel = False
bl = ebl.BiologicDevice( 'USB0' )

#Configure Limits
lower_current_limit = ebp.configure_limit(
    ecl.LimitVariable.I,
    ecl.LimitComparison.LT,
    ecl.LimitLogic.OR,
    -2.0, #lower current limit (A)
)

upper_current_limit = ebp.configure_limit(
    ecl.LimitVariable.I,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    2.0, #upper limit (A)
    
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

	 #Apply Ewe (V)
	 #Array of up to 20 voltages, in Volts
    'voltages':  [ 0, 1,2,-2,1,0 ], 

	#Duration of applied voltage (s) 
	#Array of up to 20 durations, in seconds
    'durations': [ 2,2,2,2,2,2 ], 

	#Maximum time interval between recordedpoints.
	'time_interval': 1.0, 

 	#Max current change bewteen recorded points
	"current_interval": 1e-3,
	
	#List of LimitConfig tuples defining limits for the technique. 
	# LimitConfig objects should be constructed with configure_limit. Up to 3 limits can be supplied.
	"limits": [lower_current_limit, upper_current_limit], 

	#How to exit the technique when a limit is violated.   
    #NEXTSTEP, NEXTTECHNIQUE, STOP
	"exit_condition": ecl.ExitCondition.STOP, 
     
	# Cycles, starts from 0
	'cycles': 4, 
}

save_path = 'data/tests'
if not by_channel:
	# file if saving individually
	save_path += '.csv'


prg = ebp.CALimit( bl, params, channels=channels )

prg.run()
prg.save_data( save_path, by_channel = by_channel )

"""""
def plot_current_vs_time():
    print("Reading saved CSV...")

    # Skip the extra first line written by easy-biologic.
    df = pd.read_csv(save_path, skiprows=1)

    time_col = "Time [s]"
    current_col = "Current [A]"

    if time_col not in df.columns:
        raise ValueError(f"Could not find time column: {time_col}")

    if current_col not in df.columns:
        raise ValueError(f"Could not find current column: {current_col}")

    time = df[time_col]
    current = df[current_col]

    plt.figure(figsize=(6, 5))
    plt.plot(time, current)

    plt.xlabel("Time (s)")
    plt.ylabel("Current (A)")
    plt.title("CALimit: Current vs Time")

    plt.tight_layout()
    plt.savefig("data/tests_current_vs_time.png", dpi=300)
    plt.close()

    print("Saved current-vs-time figure.")
    

plot_current_vs_time()
"""

def plot_ca_limit_by_cycle():
    print("Reading saved CALimit CSV...")

    # Skip the extra first line written by easy-biologic.
    df = pd.read_csv(save_path, skiprows=1)

    time_col = "Time [s]"
    current_col = "Current [A]"
    cycle_col = "Cycle"

    required_columns = [
        time_col,
        current_col,
        cycle_col,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            f"Missing required CSV columns: {missing_columns}"
        )

    # Convert values to numbers, remove invalid rows, and sort
    # measurements into acquisition order.
    plot_data = (
        df[required_columns]
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
        .sort_values([cycle_col, time_col])
    )

    if plot_data.empty:
        raise ValueError("The CSV contains no valid data to plot.")

    cycle_groups = list(
        plot_data.groupby(cycle_col, sort=True)
    )

    number_of_cycles = len(cycle_groups)
    color_map = plt.get_cmap("turbo")

    figure, axis = plt.subplots(
        figsize=(8, 6),
        constrained_layout=True,
    )

    for color_index, (cycle, cycle_data) in enumerate(
        cycle_groups
    ):
        cycle_number = int(cycle)

        # Select a different color for every cycle.
        color_position = (
            color_index / max(number_of_cycles - 1, 1)
        )
        color = color_map(color_position)

        time = cycle_data[time_col]
        current = cycle_data[current_col]

        axis.plot(
            time,
            current,
            color=color,
            linewidth=1.5,
            label=f"Cycle {cycle_number}",
        )

    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Current (A)")
    axis.set_title("CALimit: Current vs Time by Cycle")

    axis.grid(True, alpha=0.3)
    axis.legend(title="Cycles")

    output_path = Path(
        "data/CALimit_current_by_cycle.png"
    )

    figure.savefig(
        output_path,
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(f"Saved graph to: {output_path}")

plot_ca_limit_by_cycle()


