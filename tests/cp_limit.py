import logging
import matplotlib.pyplot as plt
import pandas as pd


import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl

from pathlib import Path

Path("data").mkdir(parents=True, exist_ok=True)
logging.basicConfig(level=logging.DEBUG)

channels = [0]
by_channel = False

lower_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.LT,
    ecl.LimitLogic.OR,
    -2.0,
)

upper_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    2.0,
)

params = {
    "currents": [-0.0000000004],
    "durations": [120],
    "limits": [lower_voltage_limit, upper_voltage_limit],
    "exit_condition": ecl.ExitCondition.STOP
}

save_path = 'data/cp-limit'
if not by_channel:
	# file if saving individually
	save_path += '.csv'

bl = ebl.BiologicDevice("USB0")
program = ebp.CPLimit(bl, params, channels=[0])

program.run()
program.save_data( save_path, by_channel = by_channel )

#plot


def plot_voltage_vs_time():
    print("Reading saved CPLimit CSV...")

    # easy-biologic writes an extra first line.
    # The actual column headers begin on the second line.
    df = pd.read_csv(save_path, skiprows=1)

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
    plt.savefig(  "data/CPLimit_voltage_vs_time.png", dpi=300)
    plt.close()

    print("Saved voltage-vs-time figure.")

plot_voltage_vs_time()