import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl


logging.basicConfig(level=logging.DEBUG)

channels = [0]
by_channel = False
CSV_PATH = Path("data/cp-limit.csv")
FIG_PATH = Path("data/cp-limit_voltage_vs_time.png")

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

params = {
    "currents": [0.001],
    "durations": [10],
    "limits": [lower_voltage_limit, upper_voltage_limit],
    "exit_condition": ecl.ExitCondition.STOP
}

def plot_voltage_vs_time():
    """Plot the saved CPLimit voltage measurements against elapsed time."""
    print("Reading saved CPLimit CSV...")
    df = pd.read_csv(CSV_PATH, skiprows=1)

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
    plt.savefig(FIG_PATH, dpi=300)
    plt.close()

    print(f"Saved figure to: {FIG_PATH}")


def main():
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)

    bl = ebl.BiologicDevice("USB0")
    program = ebp.CPLimit(bl, params, channels=channels)

    program.run()
    program.save_data(CSV_PATH, by_channel=by_channel)
    plot_voltage_vs_time()


if __name__ == "__main__":
    main()
