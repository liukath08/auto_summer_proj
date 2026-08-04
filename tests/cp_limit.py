import logging
import matplotlib.pyplot as plt
import pandas as pd

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl

from pathlib import Path

Path("data").mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.DEBUG)

BIOLOGIC_ADDRESS = "USB0"

#program only compatible with one channel currently
channels = [0]

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "CP_LIMIT"
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

#voltage limits
lower_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.LT,
    ecl.LimitLogic.OR,
    -1.0,
)
upper_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    1.0,
)

#CPLimit technique parameters
params = {
    #Current range  
	# units in Amps, with p, n, u ,n, a for pico, nano, micro, milli, and Amps
    # (p100, n1, n10,n100, u1, u10, u,100, m1, m10, m100, a1, KEEP, BOOSTER, AUTO)
	"current_range": ecl.IRange.n10, 
    
	#Voltage range 
    #(v2_5, +-2.5V),(v5, +-5V),(v10, +-10V), (AUTO, automatic voltage range)
	"voltage_range": ecl.ERange.v5, 

	#Hardware filtering
    #(k50: 50kHz), (k1: 1kHz), (h5: 5Hz), (OFF)
	"filter": ecl.Filter.h5, 

	#Average, 
	# True = average, False = no average)
	"average": False, 

    #Hardware bandwidth 
	#(BW1-9), 1= slow, 9=fast
	"bandwidth": ecl.Bandwidth.BW5, 
           
	#If step is vs initial or previous
    #Array of 20 boolean, defualt false
	#'vs_initial': [], 

    #Apply I (A)
     #Array of up to 20 currents, in Amps
    "currents": [-0.000000001, 0.000000001],#List of currents in Amps
    
	#Duration of applied currents (s) 
	#Array of up to 20 durations, in seconds
    'durations': [ 30, 30],#List of durations in seconds

    #Maximum time interval between recordedpoints.
	'time_interval': 1.0, 

 	#Max current change bewteen recorded points

    #List of LimitConfig tuples defining limits for the technique. 
    # LimitConfig objects should be constructed with configure_limit. Up to 3 limits can be supplied.
    "limits": [lower_voltage_limit, upper_voltage_limit], 


    #How to exit the technique when a limit is violated.   
    #NEXTSTEP, NEXTTECHNIQUE, STOP
    "exit_condition": ecl.ExitCondition.NEXTSTEP, 
     
    # Cycles, starts from 0
    'cycles': 0 
}

#apply channel configurations   
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
def run_cp_limit():
    print("Creating BioLogic device object...")
    bl = ebl.BiologicDevice(BIOLOGIC_ADDRESS)

    print("Creating CPLimit program...")
    cp_limit = ebp.CPLimit(
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

    print("Running CPLimit...")
    cp_limit.run()

    print(f"Saving CPLimit data to: {CSV_PATH}")
    cp_limit.save_data(CSV_PATH)

    print("CPLimit finished.")

#plot
def plot_cp_limit():
    print("Reading saved CPLimit CSV...")

    # Skip the extra first line written by easy-biologic.
    df = pd.read_csv(CSV_PATH, skiprows=1)

    time_col = "Time [s]"
    voltage_col = "Voltage [V]"
    cycle_col = "Cycle"

    required_columns = [
        time_col,
        voltage_col,
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
        voltage = cycle_data[voltage_col]

        axis.plot(
            time,
            voltage,
            color=color,
            linewidth=1.5,
            label=f"Cycle {cycle_number}",
        )

    axis.set_xlabel("Time (s)")
    axis.set_ylabel("Voltage (V)")
    axis.set_title("CPLimit: Voltage vs Time by Cycle")

    axis.grid(True, alpha=0.3)
    axis.legend(title="Cycles")

    figure.savefig(
        FIG_PATH,
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(f"Saved graph to: {FIG_PATH}")

#run
def main():
    run_cp_limit()
    plot_cp_limit()
    print("Done.")

if __name__ == "__main__":
    main()

