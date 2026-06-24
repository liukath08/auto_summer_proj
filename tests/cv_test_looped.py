from pathlib import Path
import logging

import pandas as pd
import matplotlib.pyplot as plt

import easy_biologic as ebl
import easy_biologic.base_programs as ebp


logging.basicConfig(level=logging.INFO)

BIOLOGIC_ADDRESS = "USB0"

# define all channels you want to run
CHANNELS = [0, 1,]  

DATA_DIR = Path("data")

params_cv = {
    "start": 0.0,
    "end": 0.2,
    "E2": -0.2,
    "Ef": 0.0,
    "rate": 0.05,
    "step": 0.001,
    "N_Cycles": 1,
    "begin_measuring_I": 0.0,
    "End_measuring_I": 1.0,
    "average": False,
}


def find_column(df, possible_names):
    normalized = {
        col.lower().replace(" ", "").replace("_", ""): col
        for col in df.columns
    }

    for name in possible_names:
        key = name.lower().replace(" ", "").replace("_", "")
        if key in normalized:
            return normalized[key]

    raise ValueError(
        f"Could not find any of these columns: {possible_names}\n"
        f"Available columns are: {list(df.columns)}"
    )


def main():
    print("Creating BioLogic device object...")
    bl = ebl.BiologicDevice(BIOLOGIC_ADDRESS)

    # store plots on same figure (optional)
    plt.figure(figsize=(6, 5))

    for channel in CHANNELS:
        print(f"\n=== Running CV on Channel {channel} ===")

        csv_path = DATA_DIR / f"dummy_cell_CV_channel_{channel}.csv"

        cv = ebp.CV(
            bl,
            params_cv,
            channels=[channel],
        )

        cv.run("data")
        cv.save_data(csv_path)

        print(f"Saved CV data to: {csv_path}")

        df = pd.read_csv(csv_path)

        voltage_col = find_column(
            df,
            ["voltage", "Ewe", "Ewe/V", "Ewe_V", "Ecell", "E"]
        )

        current_col = find_column(
            df,
            ["current", "I", "I/A", "I_A", "current_A"]
        )

        voltage = df[voltage_col]
        current = df[current_col]

        # label each channel curve
        plt.plot(current, voltage, label=f"Channel {channel}")

    plt.xlabel("Current, I (A)")
    plt.ylabel("Voltage, V (V)")
    plt.title("Dummy cell CV: V vs I (multi-channel)")
    plt.legend()
    plt.tight_layout()

    fig_path = DATA_DIR / "dummy_cell_CV_V_vs_I_multichannel.png"
    plt.savefig(fig_path, dpi=300)
    plt.close()

    print(f"\nSaved figure to: {fig_path}")
    print("Done.")


if __name__ == "__main__":
    main()
