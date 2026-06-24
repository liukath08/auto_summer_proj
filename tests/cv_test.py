from pathlib import Path
import logging

import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as ebp


# -------------------------
# Logging
# -------------------------
logging.basicConfig(level=logging.INFO)


# -------------------------
# BioLogic settings
# -------------------------
BIOLOGIC_ADDRESS = "USB0"
CHANNEL = 0


# -------------------------
# File paths
# -------------------------
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CSV_PATH = DATA_DIR / "dummy_cell_CV.csv"
FIG_PATH = DATA_DIR / "dummy_cell_CV_V_vs_I.png"


# -------------------------
# CV parameters for dummy cell
# -------------------------
# This runs:
# 0.0 V -> +0.2 V -> -0.2 V -> 0.0 V
# at 50 mV/s
params_cv = {
    "start": 0.0,
    "end": 0.2,
    "E2": -0.2,
    "Ef": 0.0,
    "rate": 0.05,       # V/s = 50 mV/s
    "step": 0.001,      # V = 1 mV
    "N_Cycles": 1,
    "begin_measuring_I": 0.0,
    "End_measuring_I": 1.0,
    "average": False,
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
    plt.plot(current, voltage)
    plt.xlabel("Current, I (A)")
    plt.ylabel("Voltage, V (V)")
    plt.title("Dummy cell CV: V vs I")
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