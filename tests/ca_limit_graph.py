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

CSV_PATH = DATA_DIR / "dummy_cell_CALimit.csv"
FIG_PATH = DATA_DIR / "dummy_cell_CALimit_I_vs_t.png"


# -------------------------
# CALimit parameters for dummy cell
# -------------------------
# This runs a chronoamperometry-limit style test with four voltage steps:
# 0.0 V -> +0.2 V -> 0.0 V -> -0.2 V
# Each voltage step lasts 2 seconds.
#
# NOTE:
# CALimit is mainly useful when actual limit conditions are supplied.
# With limits=[], this behaves similarly to a basic CA sequence.
params_ca_limit = {
    "voltages": [0.0, 0.2, 0.0, -0.2],
    "durations": [2.0, 2.0, 2.0, 2.0],
    "vs_initial": False,
    "time_interval": 0.1,
    "current_interval": 1e-6,
    "limits": [],
}


def run_ca_limit():
    print("Creating BioLogic device object...")
    bl = ebl.BiologicDevice(BIOLOGIC_ADDRESS)

    print("Creating CALimit program...")
    ca_limit = ebp.CALimit(
        bl,
        params_ca_limit,
        channels=[CHANNEL],
    )

    print("Running CALimit on dummy cell...")
    ca_limit.run()

    print(f"Saving CALimit data to: {CSV_PATH}")
    ca_limit.save_data(CSV_PATH)

    print("CALimit finished.")


def plot_i_vs_t():
    print("Reading saved CSV...")

    # easy-biologic writes one extra first line:
    # 0,0,0,0,0
    # The real header starts on line 2.
    df = pd.read_csv(CSV_PATH, skiprows=1)

    print("First few rows:")
    print(df.head())

    print("Columns:")
    print(list(df.columns))

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
    plt.xlabel("Time, t (s)")
    plt.ylabel("Current, I (A)")
    plt.title("Dummy cell CALimit: I vs t")
    plt.tight_layout()
    plt.savefig(FIG_PATH, dpi=300)
    plt.close()

    print(f"Saved figure to: {FIG_PATH}")


def main():
    run_ca_limit()
    plot_i_vs_t()
    print("Done.")


if __name__ == "__main__":
    main()