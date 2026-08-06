from pathlib import Path
import logging

import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
from easy_biologic import device
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl

logging.basicConfig(level=logging.DEBUG)

BIOLOGIC_ADDRESS = "USB0"

#program only compatible with one channel currently
channels = [0]

DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "CV"
DATA_DIR.mkdir(parents=True, exist_ok=True)

CSV_PATH = DATA_DIR / "0806526_1326_CV_-1V-1V_100mVs-1_1C16_CETOGRND.csv"
FIG_PATH = DATA_DIR / "0806526_1326_CV_-1V-1V_100mVs-1_1C16_CETOGRND.png"

#channel configurations
CHANNEL_CONFIGURATIONS = {
    0: {
        #Electrode Connection
        #(STND, CETOGRND, WETOGRND, HV)
        "connection": ecl.ElectrodeConnection.CETOGRND,

        #Channel Mode
        #(GROUNDED, FLOATING)
        "mode": ecl.ChannelMode.GROUNDED,
  
    },
}

#cv technique parameters
params_cv = {
    #Current range  
	# units in Amps, with p, n, u ,n, a for pico, nano, micro, milli, and Amps
    # (p100, n1, n10,n100, u1, u10, u,100, m1, m10, m100, a1, KEEP, BOOSTER, AUTO)
	"current_range": ecl.IRange.AUTO, 
    
	#Ewe range 
    #(v2_5, +-2.5V),(v5, +-5V),(v10, +-10V), (AUTO, automatic voltage range)
	"voltage_range": ecl.ERange.v2_5, 

	#Hardware filtering
    #(k50: 50kHz), (k1: 1kHz), (h5: 5Hz), (OFF)
	"filter": ecl.Filter.h5, 

	#Average, 
	# True = average, False = no average)
	"average": False, 

	#Hardware bandwidth 
	#(BW1-9), 1= slow, 9=fast
	"bandwidth": ecl.Bandwidth.BW5, 

    # Record Ece and Q-Q0 through XCTR. Q-Q0 is parsed by the
    # program but intentionally omitted from the existing CV CSV.
    "record_ece": True,

    # Original CV timebase. The program adds 6 us for
    # the two XCTR fields, producing a final 51 us timebase.
    "timebase": 45e-6,

    #If step is vs initial or previous
    #Array of 20 boolean, defualt false
	#'vs_initial': [], 

    #Start voltage
    "start": 0.0, 

    #End voltage
    "end": -1.5, 

    #Boundary voltage in backwards scan
    "E2": 1.0, 

    #End voltage in the final cycle scan
    "Ef": 0.0, 
    
    # Scan rate in V/s. 
    "rate": 0.1,  

    # Voltge step. dEN/1000     
    "step": 0.001,      

    # Cycles, starts from 0
    "N_Cycles": 2, 

    #Begin step accumulation.“1” means 100% of step    
    #"Begin_measuring_I": 0.0, 

    # End step accumulation. “1” means 100% of step
    #"End_measuring_I": 1.0, 
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

#format data and save
def save_cv_data(
    cv_program,
    output_path,
):
    """Save CV data directly in the required CSV format."""

    rows = []

    for channel in cv_program.channels:
        for datum in cv_program.data[channel]:
            if not hasattr(datum, "ece"):
                raise ValueError(
                    "CV data does not contain Ece. "
                    "Confirm record_ece=True."
                )

            rows.append(
                {
                    "time(sec)": datum.time,
                    "Ewe(V)": datum.voltage,
                    "I(mA)": datum.current * 1000,
                    "cycle #": int(datum.cycle),
                    "Ece(V)": datum.ece,
                }
            )

    if not rows:
        raise ValueError(
            "No CV measurements were collected."
        )

    dataframe = pd.DataFrame(
        rows,
        columns=[
            "time(sec)",
            "Ewe(V)",
            "I(mA)",
            "cycle #",
            "Ece(V)",
        ],
    )

    dataframe.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Saved {len(dataframe)} CV measurements "
        f"to: {output_path}"
    )

#define program
def run_cv():
    print("Creating BioLogic device object...")
    bl = ebl.BiologicDevice(BIOLOGIC_ADDRESS)

    print("Creating CV program...")
    cv = ebp.CV(
        bl,
        params_cv,
        channels=channels,
    )

    print("Applying Channel Config...")
    bl.connect()
    apply_channel_configurations(
    bl,
    CHANNEL_CONFIGURATIONS, 
    )

    print("Running CV...")
    cv.run()

    print(f"Saving CV data to: {CSV_PATH}")
    save_cv_data(
        cv,
        CSV_PATH,
    )

    print("CV finished.")

#plot data
def plot_cv():
    """Create a 2-by-2 CV plot at 300 DPI."""

    print("Reading saved CV CSV...")

    dataframe = pd.read_csv(CSV_PATH)

    time_col = "time(sec)"
    voltage_col = "Ewe(V)"
    current_col = "I(mA)"
    cycle_col = "cycle #"
    ece_col = "Ece(V)"

    required_columns = [
        time_col,
        voltage_col,
        current_col,
        cycle_col,
        ece_col,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required CV columns: "
            f"{missing_columns}"
        )

    plot_data = (
        dataframe[required_columns]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .dropna()
        .sort_values(
            [
                cycle_col,
                time_col,
            ]
        )
        .reset_index(drop=True)
    )

    if plot_data.empty:
        raise ValueError(
            "The CSV contains no valid CV data."
        )

    # Remove an initial startup point only when its
    # voltage jump is much larger than the normal step.
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

        typical_step = voltage_steps.iloc[
            2:102
        ].median()

        if (
            pd.notna(typical_step)
            and typical_step > 0
            and initial_step > 20 * typical_step
        ):
            startup_index = (
                first_cycle_data.index[0]
            )

            plot_data = plot_data.drop(
                startup_index
            )

    # The entire 2-by-2 figure is created and saved
    # at 300 DPI.
    figure, axes = plt.subplots(
        2,
        2,
        figsize=(14, 10),
        dpi=300,
        constrained_layout=True,
    )

    axes = axes.flatten()

    current_vs_voltage_axis = axes[0]
    current_vs_time_axis = axes[1]
    voltage_vs_time_axis = axes[2]
    ece_vs_time_axis = axes[3]

    color_map = plt.get_cmap("tab10")

    grouped_cycles = plot_data.groupby(
        cycle_col,
        sort=True,
    )

    for color_index, (
        cycle,
        cycle_data,
    ) in enumerate(grouped_cycles):

        cycle_number = int(cycle)
        color = color_map(color_index % 10)
        label = f"Cycle {cycle_number}"

        time = cycle_data[time_col]
        voltage = cycle_data[voltage_col]
        current = cycle_data[current_col]
        ece = cycle_data[ece_col]

        # Average consecutive groups of three points
        # for the current-versus-voltage graph.
        averaged = cycle_data[
            [
                voltage_col,
                current_col,
            ]
        ].copy()

        averaged["group_number"] = (
            range(len(averaged))
        )

        averaged["group_number"] //= 3

        averaged = (
            averaged
            .groupby(
                "group_number",
                as_index=False,
            )
            .agg(
                {
                    voltage_col: "mean",
                    current_col: "mean",
                }
            )
        )

        current_vs_voltage_axis.plot(
            averaged[voltage_col],
            averaged[current_col],
            color=color,
            linewidth=1.2,
            label=label,
        )

        current_vs_time_axis.plot(
            time,
            current,
            color=color,
            linewidth=1.2,
            label=label,
        )

        voltage_vs_time_axis.plot(
            time,
            voltage,
            color=color,
            linewidth=1.2,
            label=label,
        )

        ece_vs_time_axis.plot(
            time,
            ece,
            color=color,
            linewidth=1.2,
            label=label,
        )

    current_vs_voltage_axis.set_xlabel(
        "Ewe (V)"
    )

    current_vs_voltage_axis.set_ylabel(
        "Current (mA)"
    )

    current_vs_voltage_axis.set_title(
        "CV: Current vs Ewe"
    )

    current_vs_time_axis.set_xlabel(
        "Time (s)"
    )

    current_vs_time_axis.set_ylabel(
        "Current (mA)"
    )

    current_vs_time_axis.set_title(
        "CV: Current vs Time"
    )

    voltage_vs_time_axis.set_xlabel(
        "Time (s)"
    )

    voltage_vs_time_axis.set_ylabel(
        "Ewe (V)"
    )

    voltage_vs_time_axis.set_title(
        "CV: Ewe vs Time"
    )

    ece_vs_time_axis.set_xlabel(
        "Time (s)"
    )

    ece_vs_time_axis.set_ylabel(
        "Ece (V)"
    )

    ece_vs_time_axis.set_title(
        "CV: Ece vs Time"
    )

    for axis in axes:
        axis.grid(
            True,
            alpha=0.3,
        )

        axis.legend(
            title="Cycle",
            loc="best",
        )

    figure.suptitle(
        "Cyclic Voltammetry Results",
        fontsize=16,
    )

    figure.savefig(
        FIG_PATH,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)

    print(
        f"Saved 300 DPI CV graphs to: "
        f"{FIG_PATH}"
    )

    print(f"Saved graphs to: {FIG_PATH}")

#run program
def main():
    run_cv()
    plot_cv()
    print("Done.")

if __name__ == "__main__":
    main()
    
