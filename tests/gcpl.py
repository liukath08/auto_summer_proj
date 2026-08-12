#sequence is: (CP, CA, OCV, CP, CA, OCV )

import asyncio
import copy
import logging
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import data_parser as dp
from easy_biologic.lib import ec_lib as ecl
from easy_biologic.program import BiologicProgram, DataSegment

import cp
import ca
import ocv


logging.basicConfig(level=logging.INFO)

BIOLOGIC_ADDRESS = "USB0"
CHANNELS = [0]
READ_INTERVAL = 0.5

DATA_DIR = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "GCPL"
)

DATA_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

CSV_PATH = DATA_DIR / "gcpl.csv"
FIG_PATH = DATA_DIR / "gcpl.png"


def capture_technique_parameters(program):
    """
    Use an existing base-program class to build the parameters that
    are passed to the BioLogic device without starting the technique.
    """

    captured = {}

    original_run = program._run

    def capture(
        technique,
        parameters,
        **kwargs,
    ):
        captured["technique"] = technique
        captured["parameters"] = parameters

    program._run = capture

    try:
        program.run(retrieve_data=False)
    finally:
        program._run = original_run

    if not captured:
        raise RuntimeError(
            f"Could not build parameters for "
            f"{type(program).__name__}."
        )

    return captured


def create_sequence(device):
    """
    Create and compile:

        CP -> CA -> OCV -> CP -> CA -> OCV
    """

    if not hasattr(ocv, "params_ocv"):
        raise RuntimeError(
            "tests/ocv.py must define an OCV params dictionary "
            "before running GCPL.py."
        )

    sequence_definitions = [
        (
            "CP",
            ebp.CPLimit,
            cp.params,
        ),
        (
            "CA",
            ebp.CALimit,
            ca.params,
        ),
        (
            "OCV",
            ebp.OCV,
            ocv.params_ocv,
        ),
        (
            "CP",
            ebp.CPLimit,
            cp.params,
        ),
        (
            "CA",
            ebp.CALimit,
            ca.params,
        ),
        (
            "OCV",
            ebp.OCV,
            ocv.params_ocv,
        ),
    ]

    sequence = []

    for step_number, (
        label,
        program_class,
        source_params,
    ) in enumerate(
        sequence_definitions,
        start=1,
    ):
        technique_params = copy.deepcopy(
            source_params
        )

        # All three techniques record Ece and Q-Q0.
        technique_params["record_ece"] = True

        # If a CP or CA limit is reached, continue to the
        # next technique instead of stopping the channel.
        if label in {"CP", "CA"}:
            technique_params[
                "exit_condition"
            ] = ecl.ExitCondition.NEXTTECHNIQUE

        program = program_class(
            device,
            technique_params,
            channels=CHANNELS,
            autoconnect=False,
        )

        compiled = capture_technique_parameters(
            program
        )

        sequence.append(
            {
                "step": step_number,
                "label": label,
                "program": program,
                "technique": compiled[
                    "technique"
                ],
                "parameters": compiled[
                    "parameters"
                ],
                "parameter_types": (
                    program._parameter_types
                ),
            }
        )

    return sequence


class GCPLProgram(BiologicProgram):
    """
    Run several different BioLogic techniques as one linked sequence.

    Each returned data segment is decoded according to its
    TechniqueIndex because OCV, CALimit and CPLimit do not have the
    same raw data layout.
    """

    def __init__(
        self,
        device,
        sequence,
        channels,
    ):
        empty_params = {
            channel: {}
            for channel in channels
        }

        super().__init__(
            device,
            empty_params,
            autoconnect=False,
        )

        self.sequence = sequence
        self.rows = []

    def load_sequence(self):
        """Load the complete sequence onto every channel."""

        techniques = [
            item["technique"]
            for item in self.sequence
        ]

        parameter_types = [
            item["parameter_types"]
            for item in self.sequence
        ]

        for channel in self.channels:
            parameters = [
                item["parameters"][channel]
                for item in self.sequence
            ]

            self.device.load_techniques(
                channel,
                techniques,
                parameters,
                types=parameter_types,
            )

    async def _retrieve_data_segment(
        self,
        channel,
    ):
        raw = await self.device.get_data(
            channel
        )

        if (
            raw.info.NbRows == 0
            or raw.info.NbCols == 0
        ):
            return DataSegment(
                [],
                raw.info,
                raw.values,
            )

        technique_index = (
            raw.info.TechniqueIndex
        )

        if not (
            0
            <= technique_index
            < len(self.sequence)
        ):
            raise RuntimeError(
                "Device returned invalid technique "
                f"index {technique_index}."
            )

        technique_info = self.sequence[
            technique_index
        ]

        program = technique_info["program"]

        try:
            parsed_data = dp.parse(
                raw.data,
                raw.info,
                program._data_fields,
                self.device,
            )
        except RuntimeError as error:
            logging.debug(
                "Could not parse channel %s, "
                "technique %s: %s",
                channel,
                technique_info["label"],
                error,
            )

            return DataSegment(
                [],
                raw.info,
                raw.values,
            )

        segment = DataSegment(
            parsed_data,
            raw.info,
            raw.values,
        )

        processed_points = []

        for raw_point in parsed_data:
            point = program._fields(
                *program._field_values(
                    raw_point,
                    segment,
                )
            )

            processed_points.append(point)

            current = getattr(
                point,
                "current",
                math.nan,
            )

            cycle = getattr(
                point,
                "cycle",
                math.nan,
            )

            charge = getattr(
                point,
                "charge",
                math.nan,
            )

            ece = getattr(
                point,
                "ece",
                math.nan,
            )

            self.rows.append(
                {
                    "sequence step": (
                        technique_info["step"]
                    ),
                    "technique": (
                        technique_info["label"]
                    ),
                    "channel": channel,
                    "time(sec)": point.time,
                    "Ewe(V)": point.voltage,

                    # XCTR charge is recorded in A*s.
                    # 1 A*s = 1/3.6 mAh.
                    "Q-Q0(mAh)": (
                        charge / 3.6
                        if not math.isnan(charge)
                        else math.nan
                    ),

                    "I(mA)": (
                        current * 1000
                        if not math.isnan(current)
                        else math.nan
                    ),

                    "cycle#": (
                        int(cycle)
                        if not math.isnan(cycle)
                        else math.nan
                    ),

                    "Ece (V)": ece,
                }
            )

        return DataSegment(
            processed_points,
            raw.info,
            raw.values,
        )

    def run(self, auto_retrieve = True):
        """Load and run the linked technique sequence."""

        self.load_sequence()

        print(
            "Starting linked sequence: "
            "CP -> CA -> OCV -> "
            "CP -> CA -> OCV"
        )

        self.device.start_channels(
            self.channels
        )

        asyncio.run(
            self._retrieve_data(
                READ_INTERVAL
            )
        )


def make_time_continuous(dataframe):
    """
    Correct the time column only if the device resets time when a
    new technique starts.

    If EC-Lab already supplies cumulative StartTime values, no
    correction is made.
    """

    previous_end = None

    sequence_steps = (
        dataframe["sequence step"]
        .drop_duplicates()
        .tolist()
    )

    for step in sequence_steps:
        indexes = dataframe.index[
            dataframe["sequence step"] == step
        ]

        step_times = pd.to_numeric(
            dataframe.loc[
                indexes,
                "time(sec)",
            ],
            errors="coerce",
        )

        valid_times = step_times.dropna()

        if valid_times.empty:
            continue

        first_time = valid_times.iloc[0]
        shift = 0.0

        if (
            previous_end is not None
            and first_time < previous_end
        ):
            shift = previous_end - first_time

        adjusted_times = step_times + shift

        dataframe.loc[
            indexes,
            "time(sec)",
        ] = adjusted_times

        previous_end = adjusted_times.max()

    return dataframe


def save_gcpl_data(rows):
    """Save every technique using one common CSV format."""

    if not rows:
        raise ValueError(
            "No GCPL measurements were collected."
        )

    columns = [
        "sequence step",
        "technique",
        "channel",
        "time(sec)",
        "Ewe(V)",
        "Q-Q0(mAh)",
        "I(mA)",
        "cycle#",
        "Ece (V)",
    ]

    dataframe = pd.DataFrame(
        rows,
        columns=columns,
    )

    dataframe = make_time_continuous(
        dataframe
    )

    dataframe.to_csv(
        CSV_PATH,
        index=False,
    )

    print(
        f"Saved {len(dataframe)} measurements "
        f"to: {CSV_PATH}"
    )

    return dataframe


def plot_gcpl_data(dataframe):
    """Generate a shared four-panel GCPL plot."""

    figure, axes = plt.subplots(
        nrows=2,
        ncols=2,
        figsize=(12, 8),
        constrained_layout=True,
    )

    voltage_axis = axes[0, 0]
    current_axis = axes[0, 1]
    charge_axis = axes[1, 0]
    ece_axis = axes[1, 1]

    for step, step_data in dataframe.groupby(
        "sequence step",
        sort=True,
    ):
        technique = step_data[
            "technique"
        ].iloc[0]

        label = f"{step}: {technique}"

        voltage_data = step_data.dropna(
            subset=[
                "time(sec)",
                "Ewe(V)",
            ]
        )

        current_data = step_data.dropna(
            subset=[
                "time(sec)",
                "I(mA)",
            ]
        )

        charge_data = step_data.dropna(
            subset=[
                "time(sec)",
                "Q-Q0(mAh)",
            ]
        )

        ece_data = step_data.dropna(
            subset=[
                "time(sec)",
                "Ece (V)",
            ]
        )

        if not voltage_data.empty:
            voltage_axis.plot(
                voltage_data["time(sec)"],
                voltage_data["Ewe(V)"],
                label=label,
            )

        # OCV contains no current, so OCV rows are skipped here.
        if not current_data.empty:
            current_axis.plot(
                current_data["time(sec)"],
                current_data["I(mA)"],
                label=label,
            )

        if not charge_data.empty:
            charge_axis.plot(
                charge_data["time(sec)"],
                charge_data["Q-Q0(mAh)"],
                label=label,
            )

        if not ece_data.empty:
            ece_axis.plot(
                ece_data["time(sec)"],
                ece_data["Ece (V)"],
                label=label,
            )

    voltage_axis.set_title(
        "Ewe vs Time"
    )
    voltage_axis.set_xlabel(
        "Time (s)"
    )
    voltage_axis.set_ylabel(
        "Ewe (V)"
    )

    current_axis.set_title(
        "Current vs Time"
    )
    current_axis.set_xlabel(
        "Time (s)"
    )
    current_axis.set_ylabel(
        "Current (mA)"
    )

    charge_axis.set_title(
        "Q-Q0 vs Time"
    )
    charge_axis.set_xlabel(
        "Time (s)"
    )
    charge_axis.set_ylabel(
        "Q-Q0 (mAh)"
    )

    ece_axis.set_title(
        "Ece vs Time"
    )
    ece_axis.set_xlabel(
        "Time (s)"
    )
    ece_axis.set_ylabel(
        "Ece (V)"
    )

    for axis in axes.flat:
        axis.grid(
            True,
            alpha=0.3,
        )

        if axis.lines:
            axis.legend(
                fontsize=8,
            )

    figure.savefig(
        FIG_PATH,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)

    print(
        f"Saved GCPL graph to: {FIG_PATH}"
    )


def main():
    print(
        "Creating BioLogic device object..."
    )

    device = ebl.BiologicDevice(
        BIOLOGIC_ADDRESS
    )

    print(
        "Building linked technique sequence..."
    )

    sequence = create_sequence(
        device
    )

    gcpl = GCPLProgram(
        device,
        sequence,
        CHANNELS,
    )

    device.connect()

    try:
        print(
            "Applying channel configuration..."
        )

        cp.apply_channel_configurations(
            device,
            cp.CHANNEL_CONFIGURATIONS,
        )

        gcpl.run()

    except BaseException:
        try:
            device.stop_channels(
                CHANNELS
            )
        except Exception:
            pass

        raise

    finally:
        if device.is_connected():
            device.disconnect()

    dataframe = save_gcpl_data(
        gcpl.rows
    )

    plot_gcpl_data(
        dataframe
    )

    print(
        "GCPL sequence finished."
    )


if __name__ == "__main__":
    main()