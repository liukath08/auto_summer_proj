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
FIG_PATH = DATA_DIR / "dummy_cell_CV_V_vs_I.png"

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


def main():
    run_cv()
    plot_v_vs_i()
    print("Done.")


if __name__ == "__main__":
    main()