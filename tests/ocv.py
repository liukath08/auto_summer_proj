"""Run an OCV experiment with Ece and Q-Q0 recording."""

import logging
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl


logging.basicConfig(level=logging.DEBUG)

BIOLOGIC_ADDRESS = "USB0"

# This test currently supports one channel.
channels = [0]

DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "OCV"
)

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

CSV_PATH = DATA_DIR / "ocv_results.csv"
FIG_PATH = DATA_DIR / "ocv_results.png"


# Channel hardware configuration.
CHANNEL_CONFIGURATIONS = {
    0: {
        # Electrode connection:
        # STND, CETOGRND, WETOGRND, or HV
        "connection": (
            ecl.ElectrodeConnection.CETOGRND
        ),

        # Channel mode:
        # GROUNDED or FLOATING
        "mode": ecl.ChannelMode.GROUNDED,
    },
}


# OCV technique parameters.
params_ocv = {
    # Ewe measurement range:
    # v2_5, v5, v10, or AUTO
    "voltage_range": ecl.ERange.v5,

    # Hardware bandwidth:
    # BW1 is slowest and BW9 is fastest.
    "bandwidth": ecl.Bandwidth.BW5,

    # Total OCV duration in seconds.
    "time": 10.0,

    # Maximum time between recorded points.
    "time_interval": 1.0,

    # Record when Ewe changes by this amount.
    "voltage_interval": 0.01,

    # Record Ece and Q-Q0 through XCTR.
    "record_ece": True,

    # Original OCV timebase.
    # The OCV class adds 6 microseconds for Ece and
    # charge, producing a final 26-microsecond timebase.
    "timebase": 20e-6,
}


def apply_channel_configurations(
    device,
    configurations,
):
    """Apply and verify each channel configuration."""

    for (
        channel,
        configuration,
    ) in configurations.items():

        device.set_channel_configuration(
            channel,
            mode=configuration["mode"],
            connection=configuration[
                "connection"
            ],
        )

        applied = (
            device.channel_configuration(
                channel
            )
        )

        print(
            f"Channel {channel}: "
            f"mode={applied.mode}, "
            f"connection={applied.connection}"
        )


def save_ocv_data(
    ocv_program,
    output_path,
):
    """Save OCV data in a CP/CA-style CSV."""

    rows = []

    for channel in ocv_program.channels:
        for datum in ocv_program.data[channel]:

            if not hasattr(datum, "ece"):
                raise ValueError(
                    "OCV data does not contain Ece. "
                    "Confirm record_ece=True."
                )

            if not hasattr(datum, "charge"):
                raise ValueError(
                    "OCV data does not contain Q-Q0. "
                    "Confirm XCTR charge recording "
                    "is enabled."
                )

            rows.append(
                {
                    "time(sec)": datum.time,
                    "Ewe(V)": datum.voltage,
                    "Q-Q0(mAh)": datum.charge,
                    "Ece (V)": datum.ece,
                }
            )

    if not rows:
        raise ValueError(
            "No OCV measurements were collected."
        )

    dataframe = pd.DataFrame(
        rows,
        columns=[
            "time(sec)",
            "Ewe(V)",
            "Q-Q0(mAh)",
            "Ece (V)",
        ],
    )

    dataframe.to_csv(
        output_path,
        index=False,
    )

    print(
        f"Saved {len(dataframe)} OCV measurements "
        f"to: {output_path}"
    )


def run_ocv():
    """Create and run the OCV program."""

    print(
        "Creating BioLogic device object..."
    )

    bl = ebl.BiologicDevice(
        BIOLOGIC_ADDRESS
    )

    print("Creating OCV program...")

    ocv = ebp.OCV(
        bl,
        params_ocv,
        channels=channels,
    )

    print(
        "Applying channel configuration..."
    )

    bl.connect()

    apply_channel_configurations(
        bl,
        CHANNEL_CONFIGURATIONS,
    )

    print("Running OCV...")

    ocv.run()

    print(
        f"Saving OCV data to: {CSV_PATH}"
    )

    save_ocv_data(
        ocv,
        CSV_PATH,
    )

    print("OCV finished.")


def plot_ocv():
    """Plot Ewe and Q-Q0 versus time at 300 DPI."""

    print("Reading saved OCV CSV...")

    dataframe = pd.read_csv(
        CSV_PATH
    )

    time_col = "time(sec)"
    voltage_col = "Ewe(V)"
    charge_col = "Q-Q0(mAh)"

    required_columns = [
        time_col,
        voltage_col,
        charge_col,
    ]

    missing_columns = [
        column
        for column in required_columns
        if column not in dataframe.columns
    ]

    if missing_columns:
        raise ValueError(
            "Missing required OCV columns: "
            f"{missing_columns}"
        )

    plot_data = (
        dataframe[required_columns]
        .apply(
            pd.to_numeric,
            errors="coerce",
        )
        .dropna()
        .sort_values(time_col)
    )

    if plot_data.empty:
        raise ValueError(
            "The CSV contains no valid OCV data."
        )

    figure, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(9, 9),
        sharex=True,
        constrained_layout=True,
    )

    voltage_axis, charge_axis = axes

    voltage_axis.plot(
        plot_data[time_col],
        plot_data[voltage_col],
        color="tab:blue",
        linewidth=1.5,
    )

    charge_axis.plot(
        plot_data[time_col],
        plot_data[charge_col],
        color="tab:orange",
        linewidth=1.5,
    )

    voltage_axis.set_ylabel(
        "Ewe (V)"
    )

    voltage_axis.set_title(
        "OCV: Ewe vs Time"
    )

    charge_axis.set_xlabel(
        "Time (s)"
    )

    charge_axis.set_ylabel(
        "Q-Q0 (mAh)"
    )

    charge_axis.set_title(
        "OCV: Q-Q0 vs Time"
    )

    for axis in axes:
        axis.grid(
            True,
            alpha=0.3,
        )

    figure.savefig(
        FIG_PATH,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)

    print(
        f"Saved OCV graph to: {FIG_PATH}"
    )


def main():
    run_ocv()
    plot_ocv()

    print("Done.")


if __name__ == "__main__":
    main()