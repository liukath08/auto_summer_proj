"""Shared CP, CA, and OCV configuration for linked GCPL tests."""

import copy
import math

import matplotlib.pyplot as plt
import pandas as pd

import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl




LOWER_VOLTAGE_LIMIT = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.LT,
    ecl.LimitLogic.OR,
    -2.0,
)

UPPER_VOLTAGE_LIMIT = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    1.0,
)

LOWER_CURRENT_LIMIT = ebp.configure_limit(
    ecl.LimitVariable.I,
    ecl.LimitComparison.LT,
    ecl.LimitLogic.OR,
    -2.0,
)

UPPER_CURRENT_LIMIT = ebp.configure_limit(
    ecl.LimitVariable.I,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    2.0,
)


# CPLimit parameter template.
CP_PARAMS = {
    "current_range": ecl.IRange.n1,
    "voltage_range": ecl.ERange.v5,
    "filter": ecl.Filter.h5,
    "average": False,
    "bandwidth": ecl.Bandwidth.BW5,

    # XCTR records Ece and Q-Q0. CPLimit adds 6 us to this
    # original timebase, producing a final 40 us timebase.
    "record_ece": True,
    "timebase": 34e-6,

    # These values are templates. GCPL replaces them using
    # the corresponding SETPOINTS and DURATIONS row.
    "currents": [-1e-9],
    "durations": [60.0],

    "time_interval": 0.5,
    "step_limits": [
        [LOWER_VOLTAGE_LIMIT],
    ],
    "exit_condition": ecl.ExitCondition.NEXTTECHNIQUE,
    "cycles": 0,
}


# CALimit parameter template.
CA_PARAMS = {
    "current_range": ecl.IRange.u10,
    "voltage_range": ecl.ERange.AUTO,
    "filter": ecl.Filter.h5,
    "average": True,
    "bandwidth": ecl.Bandwidth.BW1,

    # XCTR records Ece and Q-Q0. CALimit adds 6 us to this
    # original timebase, producing a final 40 us timebase.
    "record_ece": True,
    "timebase": 34e-6,

    # These values are templates. GCPL replaces them using
    # the corresponding SETPOINTS and DURATIONS row.
    "voltages": [-1.0],
    "durations": [30.0],

    "time_interval": 0.5,
    "current_interval": 1e-3,
    "step_limits": [
        [LOWER_CURRENT_LIMIT],
    ],
    "exit_condition": ecl.ExitCondition.NEXTTECHNIQUE,
    "cycles": 0,
}


# OCV parameter template.
OCV_PARAMS = {
    "voltage_range": ecl.ERange.v5,
    "bandwidth": ecl.Bandwidth.BW5,

    # GCPL replaces this value using DURATIONS[i][2].
    "time": 10.0,
    "time_interval": 0.5,
    "voltage_interval": 0.01,

    # XCTR records Ece and Q-Q0. OCV adds 6 us to this
    # original timebase, producing a final 26 us timebase.
    "record_ece": True,
    "timebase": 20e-6,
}


def apply_channel_configurations(
    device,
    configurations=None,
):
    """Apply and verify the shared hardware configuration."""

    if configurations is None:
        configurations = CHANNEL_CONFIGURATIONS

    for channel, configuration in configurations.items():
        device.set_channel_configuration(
            channel,
            mode=configuration["mode"],
            connection=configuration[
                "connection"
            ],
        )

        applied = device.channel_configuration(
            channel
        )

        print(
            f"Channel {channel}: "
            f"mode={applied.mode}, "
            f"connection={applied.connection}"
        )

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

def create_sequence(
    device, setpoint_rows, duration_rows, lower_limit_rows,
    upper_limit_rows, hardware_rows, channels,
):
    """
    Create and compile:

        CP -> CA -> OCV
    """

    if not (
        len(setpoint_rows)
        == len(duration_rows)
        == len(lower_limit_rows)
        == len(upper_limit_rows)
        == len(hardware_rows)
    ):
        raise ValueError(
            "SETPOINTS, DURATIONS, LOWER_LIMITS, "
            "UPPER_LIMITS, and HARDWARE_PARAMETERS must "
            "contain the same number of rows."
        )

    sequence_definitions = []

    for pair_index, (
        setpoints,
        durations,
        lower_limits,
        upper_limits,
        hardware_parameters,
    ) in enumerate(
        zip(
            setpoint_rows,
            duration_rows,
            lower_limit_rows,
            upper_limit_rows,
            hardware_rows,
        ),
        start=1,
    ):
        if len(setpoints) != 2:
            raise ValueError(
                f"Setpoint row {pair_index} must be "
                "[CP current, CA voltage]."
            )

        if len(durations) != 3:
            raise ValueError(
                f"Duration row {pair_index} must be "
                "[CP duration, CA duration, OCV duration]."
            )

        if len(lower_limits) != 2:
            raise ValueError(
                f"Lower-limit row {pair_index} must be "
                "[CP voltage, CA current]."
            )

        if len(upper_limits) != 2:
            raise ValueError(
                f"Upper-limit row {pair_index} must be "
                "[CP voltage, CA current]."
            )

        required_techniques = {
            "CP",
            "CA",
            "OCV",
        }

        if set(hardware_parameters) != required_techniques:
            raise ValueError(
                f"Hardware row {pair_index} must contain "
                "exactly CP, CA, and OCV entries."
            )

        for technique_name in required_techniques:
            if len(
                hardware_parameters[
                    technique_name
                ]
            ) != 3:
                raise ValueError(
                    f"Hardware row {pair_index} "
                    f"{technique_name} entry must be "
                    "[I_Range, E_Range, Bandwidth]."
                )

        cp_current, ca_voltage = (
            float(value)
            for value in setpoints
        )
        cp_duration, ca_duration, ocv_duration = (
            float(value)
            for value in durations
        )
        cp_lower_voltage, ca_lower_current = (
            float(value)
            for value in lower_limits
        )
        cp_upper_voltage, ca_upper_current = (
            float(value)
            for value in upper_limits
        )

        (
            cp_current_range,
            cp_voltage_range,
            cp_bandwidth,
        ) = hardware_parameters["CP"]

        (
            ca_current_range,
            ca_voltage_range,
            ca_bandwidth,
        ) = hardware_parameters["CA"]

        (
            ocv_current_range,
            ocv_voltage_range,
            ocv_bandwidth,
        ) = hardware_parameters["OCV"]

        try:
            cp_current_range = ecl.IRange(
                cp_current_range
            )
            cp_voltage_range = ecl.ERange(
                cp_voltage_range
            )
            cp_bandwidth = ecl.Bandwidth(
                cp_bandwidth
            )

            ca_current_range = ecl.IRange(
                ca_current_range
            )
            ca_voltage_range = ecl.ERange(
                ca_voltage_range
            )
            ca_bandwidth = ecl.Bandwidth(
                ca_bandwidth
            )

            ocv_voltage_range = ecl.ERange(
                ocv_voltage_range
            )
            ocv_bandwidth = ecl.Bandwidth(
                ocv_bandwidth
            )
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"Hardware row {pair_index} contains "
                "an invalid range or bandwidth."
            ) from error

        if ocv_current_range is not None:
            raise ValueError(
                f"Hardware row {pair_index} OCV I_Range "
                "must be None."
            )

        if not all(
            math.isfinite(value)
            for value in (
                cp_current,
                ca_voltage,
                cp_duration,
                ca_duration,
                ocv_duration,
                cp_lower_voltage,
                ca_lower_current,
                cp_upper_voltage,
                ca_upper_current,
            )
        ):
            raise ValueError(
                f"Pair {pair_index} contains a "
                "non-finite value."
            )

        if any(
            duration <= 0
            for duration in (
                cp_duration,
                ca_duration,
                ocv_duration,
            )
        ):
            raise ValueError(
                f"Pair {pair_index} durations must "
                "all be positive."
            )

        if cp_lower_voltage >= cp_upper_voltage:
            raise ValueError(
                f"Pair {pair_index} CP lower voltage limit "
                "must be less than its upper voltage limit."
            )

        if ca_lower_current >= ca_upper_current:
            raise ValueError(
                f"Pair {pair_index} CA lower current limit "
                "must be less than its upper current limit."
            )

        cp_params = copy.deepcopy(
            CP_PARAMS
        )
        ca_params = copy.deepcopy(
            CA_PARAMS
        )
        ocv_params = copy.deepcopy(
            OCV_PARAMS
        )

        cp_params["currents"] = [cp_current]
        cp_params["durations"] = [cp_duration]
        cp_params["current_range"] = cp_current_range
        cp_params["voltage_range"] = cp_voltage_range
        cp_params["bandwidth"] = cp_bandwidth

        ca_params["voltages"] = [ca_voltage]
        ca_params["durations"] = [ca_duration]
        ca_params["current_range"] = ca_current_range
        ca_params["voltage_range"] = ca_voltage_range
        ca_params["bandwidth"] = ca_bandwidth

        ocv_params["time"] = ocv_duration
        ocv_params["voltage_range"] = ocv_voltage_range
        ocv_params["bandwidth"] = ocv_bandwidth

        cp_params["step_limits"] = [
            [
                ebp.configure_limit(
                    ecl.LimitVariable.E,
                    ecl.LimitComparison.LT,
                    ecl.LimitLogic.OR,
                    cp_lower_voltage,
                ),
                ebp.configure_limit(
                    ecl.LimitVariable.E,
                    ecl.LimitComparison.GT,
                    ecl.LimitLogic.OR,
                    cp_upper_voltage,
                ),
            ]
        ]

        ca_params["step_limits"] = [
            [
                ebp.configure_limit(
                    ecl.LimitVariable.I,
                    ecl.LimitComparison.LT,
                    ecl.LimitLogic.OR,
                    ca_lower_current,
                ),
                ebp.configure_limit(
                    ecl.LimitVariable.I,
                    ecl.LimitComparison.GT,
                    ecl.LimitLogic.OR,
                    ca_upper_current,
                ),
            ]
        ]

        sequence_definitions.extend(
            [
                (
                    "CP",
                    ebp.CPLimit,
                    cp_params,
                ),
                (
                    "CA",
                    ebp.CALimit,
                    ca_params,
                ),
                (
                    "OCV",
                    ebp.OCV,
                    ocv_params,
                ),
            ]
        )

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
            channels=channels,
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

def save_gcpl_data(rows, output_path):
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
        output_path,
        index=False,
    )

    print(
        f"Saved {len(dataframe)} measurements "
        f"to: {output_path}"
    )

    return dataframe

def make_charge_continuous(dataframe):
    """
    Offset each new technique's charge values so its first valid
    charge equals the preceding technique's last valid charge.

    Work independently for each channel and leave the saved CSV data
    unchanged by operating on a copy of the dataframe.
    """

    adjusted_dataframe = dataframe.copy()

    for channel in (
        adjusted_dataframe["channel"]
        .drop_duplicates()
        .tolist()
    ):
        previous_charge = None

        channel_indexes = adjusted_dataframe.index[
            adjusted_dataframe["channel"] == channel
        ]

        sequence_steps = (
            adjusted_dataframe.loc[
                channel_indexes,
                "sequence step",
            ]
            .drop_duplicates()
            .tolist()
        )

        for step in sequence_steps:
            step_indexes = adjusted_dataframe.index[
                (
                    adjusted_dataframe["channel"]
                    == channel
                )
                & (
                    adjusted_dataframe["sequence step"]
                    == step
                )
            ]

            step_charge = pd.to_numeric(
                adjusted_dataframe.loc[
                    step_indexes,
                    "Q-Q0(mAh)",
                ],
                errors="coerce",
            )

            valid_indexes = step_charge.dropna().index

            if valid_indexes.empty:
                continue

            if previous_charge is not None:
                charge_shift = (
                    previous_charge
                    - step_charge.loc[valid_indexes[0]]
                )

                adjusted_dataframe.loc[
                    valid_indexes,
                    "Q-Q0(mAh)",
                ] = (
                    step_charge.loc[valid_indexes]
                    + charge_shift
                )

            previous_charge = adjusted_dataframe.loc[
                valid_indexes[-1],
                "Q-Q0(mAh)",
            ]

    return adjusted_dataframe

def plot_gcpl_data(dataframe, output_path):
    """Generate a shared four-panel GCPL plot."""

    plot_dataframe = make_charge_continuous(
        dataframe
    )

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

    for step, step_data in plot_dataframe.groupby(
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
                current_data["I(mA)"] * 1_000_000,
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
        "Current (nA)"
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
        output_path,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(figure)

    print(
        f"Saved GCPL graph to: {output_path}"
    )
