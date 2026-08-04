
import logging
import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl
from pathlib import Path

Path("data").mkdir(parents=True, exist_ok=True)
logging.basicConfig( level = logging.DEBUG )

BIOLOGIC_ADDRESS = "USB0"

#program only compatible with one channel currently
channels = [ 0 ]

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "CA_LIMIT"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CSV_PATH = DATA_DIR / "080426_1055_CP_-1nA_1C08_CETOGRND_.csv"
FIG_PATH = DATA_DIR / "080426_1055_CP_-1nA_1C08_CETOGRND_.png"

#channel configurations
CHANNEL_CONFIGURATIONS = {
    0: {
        #Electrode Connection
        #(STND, CETOGRND, WETOGRND, HV)
        "connection": ecl.ElectrodeConnection.STND,

        #Channel Mode
        #(GROUNDED, FLOATING)
        "mode": ecl.ChannelMode.GROUNDED,
  
    },
}

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

#CAlimit technique parameters
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

#apply channel config
def apply_channel_configurations(
    device,
    configurations,
):
    """Apply and verify each channel's hardware configuration."""

    for ch, configuration in configurations.items():
        device.set_channel_configuration(
            ch,
            mode=configuration["mode"],
            connection=configuration["connection"],
        )

        applied = device.channel_configuration(ch)

        print(
            f"Channel {ch}: "
            f"mode={applied.mode}, "
            f"connection={applied.connection}"
        )

#define program
def run_ca_limit():
    print("Creating BioLogic device object...")
    bl = ebl.BiologicDevice(BIOLOGIC_ADDRESS)

    print("Creating CALimit program...")
    ca_limit = ebp.CALimit(
        bl,
        params,
        channels=channels,
    )

    print("Applying Channel Config...")
    bl.connect()
    apply_channel_configurations(
    bl,
    CHANNEL_CONFIGURATIONS, 
    )

    print("Running CALimit...")
    ca_limit.run()

    print(f"Saving CALimit data to: {CSV_PATH}")
    ca_limit.save_data(CSV_PATH)

    print("CALimit finished.")

#plot data
def plot_ca_limit():
    print("Reading saved CALimit CSV...")

    # easy-biologic writes the channel numbers on the first line, if there are multiple channels. Skip this line when reading the CSV.
    df = pd.read_csv(CSV_PATH, skiprows=1)

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

        color_position = (
            color_index / max(number_of_cycles - 1, 1)
        )
        color = color_map(color_position)

        axis.plot(
            cycle_data[time_col],
            cycle_data[current_col],
            color=color,
            linewidth=1.5,
            label=f"Cycle {cycle_number}",
        )

    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Current (A)")
    axis.set_title("CALimit: Current vs Time by Cycle")
    axis.grid(True, alpha=0.3)
    axis.legend(title="Cycles")

    figure.savefig(
        FIG_PATH,
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(f"Saved graph to: {FIG_PATH}")

#run program
def main():
    run_ca_limit()
    plot_ca_limit()
    print("Done.")

if __name__ == "__main__":
    main()

