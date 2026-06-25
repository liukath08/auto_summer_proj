from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as blp


DEVICE_ADDRESS = "USB0"
CHANNEL = 0

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

CSV_PATH = DATA_DIR / "cp_limit_test.csv"
FIG_PATH = DATA_DIR / "cp_limit_test_voltage_vs_time.png"


params = {
    CHANNEL: {
        "currents": [1e-6],
        "durations": [5],
        "limits": [],
    }
}


def run_cp_limit():
    print("Creating BioLogic device object...")
    device = ebl.BiologicDevice(DEVICE_ADDRESS)

    print("Creating CPLimit program...")
    prg = blp.CPLimit(device, params, channels=[CHANNEL])

    print("CPLimit object created successfully.")
    print(prg)

    print("Running CPLimit...")
    prg.run()

    print(f"Saving data to {CSV_PATH}...")
    prg.save_data(CSV_PATH)

    print("CPLimit finished.")


def plot_voltage_vs_time():
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
    voltage_col = "Voltage [V]"

    if time_col not in df.columns:
        raise ValueError(f"Could not find time column: {time_col}")

    if voltage_col not in df.columns:
        raise ValueError(f"Could not find voltage column: {voltage_col}")

    time = df[time_col]
    voltage = df[voltage_col]

    plt.figure(figsize=(6, 5))
    plt.plot(time, voltage)
    plt.xlabel("Time, t (s)")
    plt.ylabel("Voltage, V (V)")
    plt.title("Dummy Cell CPLimit: V vs Time")
    plt.tight_layout()
    plt.savefig(FIG_PATH, dpi=300)
    plt.close()

    print(f"Saved figure to {FIG_PATH}")


def main():
    run_cp_limit()
    plot_voltage_vs_time()
    print("Done.")


if __name__ == "__main__":
    main()