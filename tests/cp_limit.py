from pathlib import Path
import logging

import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as blp
from easy_biologic.lib import ec_lib as ecl


device = ebl.BiologicDevice("USB0")

limit = blp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    0.5,
)

params = {
    0: {
        "currents": [1e-6],
        "durations": [10],
        "vs_initial": False,
        "time_interval": 0.1,
        "voltage_interval": 0.001,
        "limits": [limit],
        "exit_condition": ecl.ExitCondition.STOP,
    }
}

prg = blp.CPLimit(device, params, channels=[0])

prg.run()
prg.save_data("cplimit_test.csv")

df = pd.read_csv("cplimit_test.csv")
print(df.head())

plt.plot(df["Time [s]"], df["Voltage [V]"])
plt.xlabel("Time [s]")
plt.ylabel("Voltage [V]")
plt.title("CPLimit Voltage vs Time")
plt.grid(True)
plt.show()

plt.plot(df["Time [s]"], df["Current [A]"])
plt.xlabel("Time [s]")
plt.ylabel("Current [A]")
plt.title("CPLimit Current vs Time")
plt.grid(True)
plt.show()