
import logging
import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl
from pathlib import Path

Path("data").mkdir(parents=True, exist_ok=True)


logging.basicConfig( level = logging.DEBUG )

channels = [ 0 ]
by_channel = False
bl = ebl.BiologicDevice( 'USB0' )
params = { 
	'voltages':  [ 0, 1,2,-2,1,0 ],
	'durations': [ 2,2,2,2,2,2 ],
	'cycles': 4,
}

save_path = 'data/tests'
if not by_channel:
	# file if saving individually
	save_path += '.csv'


prg = ebp.CALimit( bl, params, channels=channels )

prg.run()
prg.save_data( save_path, by_channel = by_channel )

#plotting
def plot_current_vs_time():
    print("Reading saved csv...")

    # Skip the extra first line written by easy-biologic
    df = pd.read_csv(save_path, skiprows=1)

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

    plt.xlabel("Time (s)")
    plt.ylabel("Current (A)")
    plt.title("CALimit: Current vs Time")

    plt.tight_layout()
    plt.savefig("data/tests_current_vs_time.png", dpi=300)
    plt.close()

    print("Saved current-vs-time figure.")

plot_current_vs_time()