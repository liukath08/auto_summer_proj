from pathlib import Path
import logging

import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl

logging.basicConfig(level=logging.INFO)

BIOLOGIC_ADDRESS = "USB0"
CHANNEL = 0

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CSV_PATH = DATA_DIR / "dummy_cell_CV.csv"
FIG_PATH = DATA_DIR / "dummy_cell_CV.png"

params_cv = {
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

    #Start voltage
    "start": 0.0, 

    #End voltage
    "end": -2.0, 

    #Boundary voltage in backwards scan
    "E2": 1.4, 

    #End voltage in the final cycle scan
    "Ef": 0.0, 
    
    # Scan rate in V/s. 
    "rate": 0.05,  

    # Voltage step. dEN/1000     
    "step": 0.001,      

    # Cycles, starts from 0
    "N_Cycles": 1, 

    #Begin step accumulation.“1” means 100% of step    
    "begin_measuring_I": 0.0, 

    # End step accumulation. “1” means 100% of step
    "End_measuring_I": 1.0, 
}

def run_cv():
    print("Creating BioLogic device object...")
    bl = ebl.BiologicDevice(BIOLOGIC_ADDRESS)

    print("Creating CV program...")
    cv = ebp.CV(
        bl,
        params_cv,
        channels=[CHANNEL],
    )

    print("Running CV on dummy cell...")
    cv.run("data")

    print(f"Saving CV data to: {CSV_PATH}")
    cv.save_data(CSV_PATH)

    print("CV finished.")

""""
def plot_v_vs_i():
    print("Reading saved CSV...")

    # easy-biologic writes one extra first line:
    # 0,0,0,0,0
    # The real header starts on line 2.
    df = pd.read_csv(CSV_PATH, skiprows=1)

    print("First few rows:")
    print(df.head())

    print("Columns:")
    print(list(df.columns))

    voltage_col = "Voltage [V]"
    current_col = "Current [A]"

    if voltage_col not in df.columns:
        raise ValueError(f"Could not find voltage column: {voltage_col}")

    if current_col not in df.columns:
        raise ValueError(f"Could not find current column: {current_col}")

    voltage = df[voltage_col]
    current = df[current_col]

    plt.figure(figsize=(6, 5))
    plt.plot(voltage, current)
    plt.ylabel("Current, I (A)")
    plt.xlabel("Voltage, V (V)")
    plt.title("CV")
    plt.tight_layout()
    plt.savefig(FIG_PATH, dpi=300)
    plt.close()

    print(f"Saved figure to: {FIG_PATH}")

"""

def plot_cv_by_cycle():
    print("Reading saved CV CSV...")

    df = pd.read_csv(CSV_PATH, skiprows=1)

    time_col = "Time [s]"
    current_col = "Current [A]"
    voltage_col = "Voltage [V]"
    cycle_col = "Cycle"

    required_columns = [
        time_col,
        current_col,
        voltage_col,
        cycle_col,
    ]

    missing_columns = [
        column for column in required_columns
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
        .reset_index(drop=True)
    )

    if plot_data.empty:
        raise ValueError("The CSV contains no valid data to plot.")

    # Remove an initial startup point only when its voltage jump is
    # much larger than the normal voltage step.
    first_cycle = plot_data[cycle_col].iloc[0]
    first_cycle_data = plot_data[
        plot_data[cycle_col] == first_cycle
    ]

    if len(first_cycle_data) >= 4:
        voltage_steps = (
            first_cycle_data[voltage_col]
            .diff()
            .abs()
        )

        initial_step = voltage_steps.iloc[1]
        typical_step = voltage_steps.iloc[2:102].median()

        if (
            pd.notna(typical_step)
            and typical_step > 0
            and initial_step > 20 * typical_step
        ):
            startup_index = first_cycle_data.index[0]
            plot_data = plot_data.drop(startup_index)

    figure, axes = plt.subplots(
        3,
        1,
        figsize=(7, 13),
        constrained_layout=True,
    )

    color_map = plt.get_cmap("tab10")

    for color_index, (cycle, cycle_data) in enumerate(
        plot_data.groupby(cycle_col, sort=True)
    ):
        cycle_number = int(cycle)
        color = color_map(color_index % 10)
        label = f"Cycle {cycle_number}"

        time = cycle_data[time_col]
        current_na = cycle_data[current_col] * 1e9
        voltage = cycle_data[voltage_col]

        # Average consecutive groups of three measurements.
        averaged = cycle_data[
            [current_col, voltage_col]
        ].copy()

        averaged["group_number"] = (
            range(len(averaged))
        )
        averaged["group_number"] //= 3

        averaged = (
            averaged
            .groupby("group_number", as_index=False)
            .agg({
                current_col: "mean",
                voltage_col: "mean",
            })
        )

        averaged_current_na = (
            averaged[current_col] * 1e9
        )

        axes[0].plot(
            averaged[voltage_col],
            averaged_current_na,
            color=color,
            linewidth=1.2,
            label=label,
        )

        axes[1].plot(
            time,
            current_na,
            color=color,
            linewidth=1.2,
            label=label,
        )

        axes[2].plot(
            time,
            voltage,
            color=color,
            linewidth=1.2,
            label=label,
        )

    axes[0].set_xlabel("Voltage (V)")
    axes[0].set_ylabel("Current (nA)")
    axes[0].set_title("CV: Current vs Voltage")

    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Current (nA)")
    axes[1].set_title("CV: Current vs Time")

    axes[2].set_xlabel("Time (s)")
    axes[2].set_ylabel("Voltage (V)")
    axes[2].set_title("CV: Voltage vs Time")

    for axis in axes:
        axis.grid(True, alpha=0.3)
        axis.legend()


    figure.savefig(
        FIG_PATH,
        dpi=300,
        bbox_inches="tight",
    )
    plt.close(figure)

    print(f"Saved graphs to: {FIG_PATH}")

def main():
    run_cv()
    plot_cv_by_cycle()
    print("Done.")

if __name__ == "__main__":
    main()