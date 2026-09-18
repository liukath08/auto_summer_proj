"""Reusable helpers for the BioLogic experiment launchers."""

import asyncio
import copy
import math
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import data_parser as dp
from easy_biologic.lib import ec_lib as ecl
from easy_biologic.program import BiologicProgram, DataSegment


STANDARD_COLUMNS = [
    "time(sec)",
    "Ewe(V)",
    "Q-Q0(mAh)",
    "I(mA)",
    "cycle#",
    "Ece (V)",
]
GCPL_COLUMNS = [
    "sequence step",
    "technique",
    "channel",
    *STANDARD_COLUMNS,
]


# Device helpers
def connect(address=None):
    """Connect to one BioLogic device without querying optional device info."""

    if address is None:
        address = get_hardware_parameters("DEVICE")["address"]

    device = ebl.BiologicDevice(address, populate_info=False)
    device.connect()
    return device


def disconnect(device):
    """Disconnect only when the device is still connected."""

    if device.is_connected():
        device.disconnect()


def enum_value(enum_class, value):
    """Accept either an enum member or its string name."""

    return value if isinstance(value, enum_class) else enum_class[value]


def apply_channel_config(device, connection, mode, channel=0):
    """Apply one channel's electrode connection and grounding mode."""

    device.set_channel_configuration(
        channel,
        mode=enum_value(ecl.ChannelMode, mode),
        connection=enum_value(ecl.ElectrodeConnection, connection),
    )

#change this, redundant
def apply_channel_configurations(device, configurations):
    """Apply a configuration dictionary to every listed channel."""

    for channel, configuration in configurations.items():
        apply_channel_config(device, channel=channel, **configuration)


def build_limit(variable, comparison, value):
    """Build one OR-connected BioLogic technique limit."""

    return ebp.configure_limit(
        variable,
        comparison,
        ecl.LimitLogic.OR,
        value,
    )


def sync_step_limits(params, step_key, variable, bounds=(-50.0, 50.0)):
    """Resize step_limits in place before compiling CA/CP parameters.

    Keep existing rows by position. New rows use technique-wide ``limits``
    when provided, otherwise the supplied lower/upper bounds (V or A).
    """

    steps = len(params[step_key])
    existing = params.get("step_limits") or []
    defaults = params.get("limits")
    if defaults is None:
        defaults = build_step_limits(variable, bounds)[0]

    rows = [
        list(existing[index]) if index < len(existing) else list(defaults)
        for index in range(steps)
    ]
    if any(len(row) > 3 for row in rows):
        raise ValueError("BioLogic supports at most three limits per step.")
    params["step_limits"] = rows
    return rows


# All editable experiment settings live in these three lists.
CHANNEL_PARAMETERS = [
    {
        "channel": 0,
        "connection": ecl.ElectrodeConnection.CETOGRND,
        "mode": ecl.ChannelMode.GROUNDED,
    },
]

HARDWARE_PARAMETERS = [
    {
        "name": "DEVICE",
        "address": "USB0",
    },
    {
        "name": "CA_LIMIT",
        "current_range": ecl.IRange.m10,
        "voltage_range": ecl.ERange.AUTO,
        "filter": ecl.Filter.h5,
        "average": True,
        "bandwidth": ecl.Bandwidth.BW1,
        "record_ece": True,
        "timebase": 34e-6,
    },
    {
        "name": "CP_LIMIT",
        "current_range": ecl.IRange.n1,
        "voltage_range": ecl.ERange.v5,
        "filter": ecl.Filter.h5,
        "average": False,
        "bandwidth": ecl.Bandwidth.BW5,
        "record_ece": True,
        "timebase": 34e-6,
    },
    {
        "name": "CV",
        "current_range": ecl.IRange.AUTO,
        "voltage_range": ecl.ERange.v2_5,
        "filter": ecl.Filter.h5,
        "average": False,
        "bandwidth": ecl.Bandwidth.BW5,
        "record_ece": True,
        "timebase": 45e-6,
    },
    {
        "name": "OCV",
        "voltage_range": ecl.ERange.v5,
        "bandwidth": ecl.Bandwidth.BW5,
        "record_ece": True,
        "timebase": 20e-6,
    },
    {
        "name": "GCPL_CP",
        "current_range": ecl.IRange.n1,
        "voltage_range": ecl.ERange.v5,
        "filter": ecl.Filter.h5,
        "average": False,
        "bandwidth": ecl.Bandwidth.BW5,
        "record_ece": True,
        "timebase": 34e-6,
    },
    {
        "name": "GCPL_CA",
        "current_range": ecl.IRange.AUTO,
        "voltage_range": ecl.ERange.AUTO,
        "filter": ecl.Filter.h5,
        "average": True,
        "bandwidth": ecl.Bandwidth.BW1,
        "record_ece": True,
        "timebase": 34e-6,
    },
    {
        "name": "GCPL_OCV",
        "voltage_range": ecl.ERange.v5,
        "bandwidth": ecl.Bandwidth.BW5,
        "record_ece": True,
        "timebase": 20e-6,
    },
]

TECHNIQUE_PARAMETERS = [
    {
        "name": "CA_LIMIT",
        "charge_limit_mAh": 0.000010,
        "voltages": [-0.5],
        "durations": [6000],
        "time_interval": 0.5,
        "current_interval": 1e-3,
        "step_limits": [[
            build_limit(
                ecl.LimitVariable.I,
                ecl.LimitComparison.GT,
                200.0,
            )
        ]],
        "exit_condition": ecl.ExitCondition.STOP,
        "cycles": 0,
    },
    {
        "name": "CP_LIMIT",
        "currents": [-1e-9],
        "durations": [60],
        "time_interval": 1.0,
        "voltage_interval": 1e-3,
        "step_limits": [[
            build_limit(
                ecl.LimitVariable.E,
                ecl.LimitComparison.LT,
                -2.0,
            )
        ]],
        "exit_condition": ecl.ExitCondition.NEXTSTEP,
        "cycles": 0,
    },
    {
        "name": "CV",
        "vs_initial": [],
        "start": 0.0,
        "end": -1.5,
        "E2": 1.0,
        "Ef": 0.0,
        "rate": 0.1,
        "step": 0.001,
        "N_Cycles": 2,
        "Begin_measuring_I": 0.0,
        "End_measuring_I": 1.0,
    },
    {
        "name": "OCV",
        "time": 10.0,
        "time_interval": 1.0,
        "voltage_interval": 0.01,
    },
    {
        "name": "GCPL_CP",
        "currents": [-1e-9],
        "durations": [60.0],
        "time_interval": 0.5,
        "cycles": 0,
    },
    {
        "name": "GCPL_CA",
        "voltages": [-1.0],
        "durations": [30.0],
        "time_interval": 0.5,
        "current_interval": 1e-3,
        "cycles": 0,
    },
    {
        "name": "GCPL_OCV",
        "time": 10.0,
        "time_interval": 0.5,
        "voltage_interval": 0.01,
    },
    {
        "name": "GCPL",
        "read_interval": 0.5,
        "cp_voltage_limits": (-2.0, 1.0),
        "ca_current_limits": (-2.0, 2.0),
        "sequence_groups": [
            {
                "CP": {"current": -1.25e-9, "duration": 60.0},
                "CA": {"voltage": -1.7, "duration": 30.0},
                "OCV": {"duration": 10.0},
            },
            {
                "CP": {"current": 1e-9, "duration": 120.0},
                "CA": {"voltage": 1.0, "duration": 30.0},
                "OCV": {"duration": 10.0},
            },
        ],
    },
]


def parameter_values(parameter_list, name):
    """Return a deep copy of one named record without its lookup name."""

    for record in parameter_list:
        if record["name"] == name:
            values = copy.deepcopy(record)
            values.pop("name")
            return values
    raise KeyError(f"Unknown parameter set: {name}")


def get_channel_configurations():
    """Return channel settings in the format expected by the device helpers."""

    return {
        record["channel"]: {
            "connection": record["connection"],
            "mode": record["mode"],
        }
        for record in copy.deepcopy(CHANNEL_PARAMETERS)
    }


def get_hardware_parameters(name):
    return parameter_values(HARDWARE_PARAMETERS, name)


def get_technique_parameters(name):
    """Merge one technique's hardware and procedure parameters."""

    params = get_hardware_parameters(name)
    params.update(parameter_values(TECHNIQUE_PARAMETERS, name))
    if name == "CA_LIMIT":
        sync_step_limits(params, "voltages", ecl.LimitVariable.I)
    elif name == "CP_LIMIT":
        sync_step_limits(params, "currents", ecl.LimitVariable.E)
    return params


# Single-technique execution
def run_program(
    program_class,
    params,
    configurations=None,
    channels=None,
    address=None,
):
    """Connect, configure, run, and safely disconnect one technique."""

    if configurations is None:
        configurations = get_channel_configurations()
    selected_channels = list(configurations) if channels is None else channels
    if program_class is ebp.CALimit:
        sync_step_limits(params, "voltages", ecl.LimitVariable.I)
    elif program_class is ebp.CPLimit:
        sync_step_limits(params, "currents", ecl.LimitVariable.E)
    device = connect(address)

    try:
        apply_channel_configurations(device, configurations)
        program = program_class(
            device,
            params,
            channels=selected_channels,
            autoconnect=False,
        )
        program.run()
    finally:
        disconnect(device)

    return program


def run_ca_limit(params=None, configurations=None, channels=None, address=None):
    """Run charge-limited chronoamperometry."""

    if params is None:
        params = get_technique_parameters("CA_LIMIT")
    return run_program(
        ebp.CALimit,
        params,
        configurations,
        channels,
        address,
    )


def run_cp_limit(params=None, configurations=None, channels=None, address=None):
    """Run limit-controlled chronopotentiometry."""

    if params is None:
        params = get_technique_parameters("CP_LIMIT")
    return run_program(
        ebp.CPLimit,
        params,
        configurations,
        channels,
        address,
    )


def run_cv(params=None, configurations=None, channels=None, address=None):
    """Run cyclic voltammetry."""

    if params is None:
        params = get_technique_parameters("CV")
    return run_program(ebp.CV, params, configurations, channels, address)


def run_ocv(params=None, configurations=None, channels=None, address=None):
    """Run open-circuit voltage."""

    if params is None:
        params = get_technique_parameters("OCV")
    return run_program(ebp.OCV, params, configurations, channels, address)


# Standard data export
def standard_row(datum, technique, include_current=True, include_cycle=True):
    """Convert one decoded measurement to the shared CSV schema."""

    for field in ("ece", "charge"):
        if not hasattr(datum, field):
            raise ValueError(
                f"{technique} data does not contain {field}. "
                "Confirm record_ece=True."
            )

    if include_current and not hasattr(datum, "current"):
        raise ValueError(f"{technique} data does not contain current.")
    if include_cycle and not hasattr(datum, "cycle"):
        raise ValueError(f"{technique} data does not contain cycle.")

    return {
        "time(sec)": datum.time,
        "Ewe(V)": datum.voltage,
        "Q-Q0(mAh)": datum.charge / 3.6,
        "I(mA)": datum.current * 1000 if include_current else None,
        "cycle#": int(datum.cycle) if include_cycle else None,
        "Ece (V)": datum.ece,
    }


def save_standard_data(
    program,
    output_path,
    technique,
    include_current=True,
    include_cycle=True,
):
    """Save any single technique using the shared CA/CP-style schema."""

    rows = [
        standard_row(datum, technique, include_current, include_cycle)
        for channel in program.channels
        for datum in program.data[channel]
    ]
    if not rows:
        raise ValueError(f"No {technique} measurements were collected.")

    dataframe = pd.DataFrame(rows, columns=STANDARD_COLUMNS)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False)
    return dataframe


def save_ca_data(program, output_path):
    return save_standard_data(program, output_path, "CA")


def save_cp_limit_data(program, output_path):
    return save_standard_data(program, output_path, "CPLimit")


def save_cv_data(program, output_path):
    return save_standard_data(program, output_path, "CV")


def save_ocv_data(program, output_path):
    return save_standard_data(
        program,
        output_path,
        "OCV",
        include_current=False,
        include_cycle=False,
    )


# Standard plotting
def as_dataframe(data) -> pd.DataFrame:
    """Accept either an existing dataframe or a CSV path."""

    return data.copy() if isinstance(data, pd.DataFrame) else pd.read_csv(data)


def prepare_plot_data(
    data,
    required_columns: list[str],
    sort_columns: list[str],
    technique: str,
) -> pd.DataFrame:
    """Validate and normalize the columns needed by a plot."""

    dataframe = as_dataframe(data)
    missing = [column for column in required_columns if column not in dataframe]
    if missing:
        raise ValueError(f"Missing required {technique} columns: {missing}")

    plot_data = (
        dataframe.loc[:, required_columns]
        .apply(pd.to_numeric, errors="coerce")
        .dropna()
        .sort_values(by=sort_columns)
    )
    if plot_data.empty:
        raise ValueError(f"The data contains no valid {technique} measurements.")

    return plot_data


def save_figure(figure, output_path):
    """Create the output folder, save a 300-DPI figure, and close it."""

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output_path, dpi=300, bbox_inches="tight")
    plt.close(figure)


def plot_cycle_data(
    data,
    output_path,
    measurement_column,
    measurement_label,
    technique,
):
    """Plot one measurement and charge against time, grouped by cycle."""

    time_column = "time(sec)"
    cycle_column = "cycle#"
    charge_column = "Q-Q0(mAh)"
    plot_data = prepare_plot_data(
        data,
        [time_column, measurement_column, cycle_column, charge_column],
        [cycle_column, time_column],
        technique,
    )
    cycle_groups = list(plot_data.groupby(cycle_column, sort=True))
    color_map = plt.get_cmap("turbo")
    figure, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(9, 9),
        sharex=True,
        constrained_layout=True,
    )

    for color_index, (cycle, cycle_data) in enumerate(cycle_groups):
        color = color_map(color_index / max(len(cycle_groups) - 1, 1))
        label = f"Cycle {int(cycle)}"
        axes[0].plot(
            cycle_data[time_column],
            cycle_data[measurement_column],
            color=color,
            linewidth=1.5,
            label=label,
        )
        axes[1].plot(
            cycle_data[time_column],
            cycle_data[charge_column],
            color=color,
            linewidth=1.5,
            label=label,
        )

    axes[0].set_ylabel(measurement_label)
    axes[0].set_title(f"{technique}: {measurement_label} vs Time by Cycle")
    axes[1].set_xlabel("Time (s)")
    axes[1].set_ylabel("Q-Q0 (mAh)")
    axes[1].set_title(f"{technique}: Q-Q0 vs Time by Cycle")

    for axis in axes:
        axis.grid(True, alpha=0.3)
        axis.legend(title="Cycles")

    save_figure(figure, output_path)


def plot_ca_limit(data, output_path):
    plot_cycle_data(data, output_path, "I(mA)", "Current (mA)", "CALimit")


def plot_cp_limit(data, output_path):
    plot_cycle_data(data, output_path, "Ewe(V)", "Ewe (V)", "CPLimit")


def remove_cv_startup_point(plot_data):
    """Remove a first CV point only when it is a clear voltage-jump outlier."""

    cycle_column = "cycle#"
    voltage_column = "Ewe(V)"
    first_cycle = plot_data[cycle_column].iloc[0]
    first_cycle_data = plot_data[plot_data[cycle_column] == first_cycle]

    if len(first_cycle_data) < 4:
        return plot_data

    voltage_steps = first_cycle_data[voltage_column].diff().abs()
    initial_step = voltage_steps.iloc[1]
    typical_step = voltage_steps.iloc[2:102].median()
    if (
        pd.notna(typical_step)
        and typical_step > 0
        and initial_step > 20 * typical_step
    ):
        return plot_data.drop(first_cycle_data.index[0])

    return plot_data


def plot_cv(data, output_path):
    """Create the shared four-panel cyclic-voltammetry plot."""

    columns = ["time(sec)", "Ewe(V)", "I(mA)", "cycle#", "Ece (V)"]
    plot_data = prepare_plot_data(
        data,
        columns,
        ["cycle#", "time(sec)"],
        "CV",
    ).reset_index(drop=True)
    plot_data = remove_cv_startup_point(plot_data)

    figure, axes = plt.subplots(
        2,
        2,
        figsize=(14, 10),
        dpi=300,
        constrained_layout=True,
    )
    axes = axes.flatten()
    color_map = plt.get_cmap("tab10")

    for color_index, (cycle, cycle_data) in enumerate(
        plot_data.groupby("cycle#", sort=True)
    ):
        color = color_map(color_index % 10)
        label = f"Cycle {int(cycle)}"
        averaged = cycle_data[["Ewe(V)", "I(mA)"]].copy()
        averaged["group_number"] = range(len(averaged))
        averaged["group_number"] //= 3
        averaged = averaged.groupby("group_number", as_index=False).agg(
            {"Ewe(V)": "mean", "I(mA)": "mean"}
        )

        plots = [
            (averaged["Ewe(V)"], averaged["I(mA)"]),
            (cycle_data["time(sec)"], cycle_data["I(mA)"]),
            (cycle_data["time(sec)"], cycle_data["Ewe(V)"]),
            (cycle_data["time(sec)"], cycle_data["Ece (V)"]),
        ]
        for axis, (x_values, y_values) in zip(axes, plots):
            axis.plot(
                x_values,
                y_values,
                color=color,
                linewidth=1.2,
                label=label,
            )

    labels = [
        ("Ewe (V)", "Current (mA)", "CV: Current vs Ewe"),
        ("Time (s)", "Current (mA)", "CV: Current vs Time"),
        ("Time (s)", "Ewe (V)", "CV: Ewe vs Time"),
        ("Time (s)", "Ece (V)", "CV: Ece vs Time"),
    ]
    for axis, (xlabel, ylabel, title) in zip(axes, labels):
        axis.set(xlabel=xlabel, ylabel=ylabel, title=title)
        axis.grid(True, alpha=0.3)
        axis.legend(title="Cycle", loc="best")

    figure.suptitle("Cyclic Voltammetry Results", fontsize=16)
    save_figure(figure, output_path)


def plot_ocv(data, output_path):
    """Plot OCV potential and charge against time."""

    columns = ["time(sec)", "Ewe(V)", "Q-Q0(mAh)"]
    plot_data = prepare_plot_data(data, columns, ["time(sec)"], "OCV")
    figure, axes = plt.subplots(
        nrows=2,
        ncols=1,
        figsize=(9, 9),
        sharex=True,
        constrained_layout=True,
    )
    axes[0].plot(
        plot_data["time(sec)"],
        plot_data["Ewe(V)"],
        color="tab:blue",
        linewidth=1.5,
    )
    axes[1].plot(
        plot_data["time(sec)"],
        plot_data["Q-Q0(mAh)"],
        color="tab:orange",
        linewidth=1.5,
    )
    axes[0].set(ylabel="Ewe (V)", title="OCV: Ewe vs Time")
    axes[1].set(
        xlabel="Time (s)",
        ylabel="Q-Q0 (mAh)",
        title="OCV: Q-Q0 vs Time",
    )
    for axis in axes:
        axis.grid(True, alpha=0.3)

    save_figure(figure, output_path)


# GCPL sequence creation and execution
def build_step_limits(variable, bounds):
    """Build lower and upper limits for one GCPL step."""

    lower, upper = bounds
    if lower >= upper:
        raise ValueError("A lower technique limit must be less than its upper limit.")

    return [[
        build_limit(variable, ecl.LimitComparison.LT, lower),
        build_limit(variable, ecl.LimitComparison.GT, upper),
    ]]


def build_params(template, **updates):
    """Return an independent parameter dictionary with selected updates."""

    params = copy.deepcopy(template)
    params.update(updates)
    return params


def finite_number(value, name):
    """Convert one setting to a finite float."""

    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be a number.") from error
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


def build_group_steps(
    group,
    group_number,
    cp_template,
    ca_template,
    ocv_template,
    cp_voltage_limits,
    ca_current_limits,
):
    """Create CP, CA, and OCV parameters for one GCPL group."""

    missing = {"CP", "CA", "OCV"} - set(group)
    if missing:
        raise ValueError(f"Sequence group {group_number} is missing {sorted(missing)}.")

    cp_current = finite_number(group["CP"]["current"], "CP current")
    ca_voltage = finite_number(group["CA"]["voltage"], "CA voltage")
    durations = {
        label: finite_number(group[label]["duration"], f"{label} duration")
        for label in ("CP", "CA", "OCV")
    }
    if any(duration <= 0 for duration in durations.values()):
        raise ValueError(f"Sequence group {group_number} durations must be positive.")

    return [
        (
            "CP",
            ebp.CPLimit,
            build_params(
                cp_template,
                currents=[cp_current],
                durations=[durations["CP"]],
                limits=build_step_limits(
                    ecl.LimitVariable.E,
                    cp_voltage_limits,
                )[0],
                step_limits=None,
                exit_condition=ecl.ExitCondition.NEXTTECHNIQUE,
            ),
        ),
        (
            "CA",
            ebp.CALimit,
            build_params(
                ca_template,
                voltages=[ca_voltage],
                durations=[durations["CA"]],
                limits=build_step_limits(
                    ecl.LimitVariable.I,
                    ca_current_limits,
                )[0],
                step_limits=None,
                exit_condition=ecl.ExitCondition.NEXTTECHNIQUE,
            ),
        ),
        ("OCV", ebp.OCV, build_params(ocv_template, time=durations["OCV"])),
    ]


def capture_technique_parameters(program):
    """Compile a base program's parameters without starting the technique."""

    captured = {}
    original_run = program._run

    def capture(technique, parameters, **kwargs):
        captured["technique"] = technique
        captured["parameters"] = parameters

    program._run = capture
    try:
        program.run(retrieve_data=False)
    finally:
        program._run = original_run

    if not captured:
        raise RuntimeError(f"Could not build parameters for {type(program).__name__}.")
    return captured


def compile_step(device, channels, step_number, label, program_class, params):
    """Package one technique and its compiled device parameters."""

    if label == "CP":
        sync_step_limits(params, "currents", ecl.LimitVariable.E)
    elif label == "CA":
        sync_step_limits(params, "voltages", ecl.LimitVariable.I)
    program = program_class(
        device,
        params,
        channels=channels,
        autoconnect=False,
    )
    compiled = capture_technique_parameters(program)
    return {
        "step": step_number,
        "label": label,
        "program": program,
        "technique": compiled["technique"],
        "parameters": compiled["parameters"],
        "parameter_types": program._parameter_types,
    }


def create_sequence(
    device,
    sequence_groups,
    cp_template,
    ca_template,
    ocv_template,
    channels,
    cp_voltage_limits,
    ca_current_limits,
):
    """Compile all configured CP -> CA -> OCV groups in order."""

    sequence = []
    for group_number, group in enumerate(sequence_groups, start=1):
        definitions = build_group_steps(
            group,
            group_number,
            cp_template,
            ca_template,
            ocv_template,
            cp_voltage_limits,
            ca_current_limits,
        )
        for label, program_class, params in definitions:
            sequence.append(
                compile_step(
                    device,
                    channels,
                    len(sequence) + 1,
                    label,
                    program_class,
                    params,
                )
            )
    return sequence


def empty_segment(raw):
    return DataSegment([], raw.info, raw.values)


def optional_measurement(point, name, scale=1.0):
    """Read and scale an optional numeric field, returning NaN when absent."""

    value = getattr(point, name, math.nan)
    try:
        value = float(value)
    except (TypeError, ValueError):
        return math.nan
    return value * scale if math.isfinite(value) else math.nan


def gcpl_measurement_row(point, technique_info, channel):
    """Convert a technique-specific point to the common GCPL schema."""

    cycle = optional_measurement(point, "cycle")
    return {
        "sequence step": technique_info["step"],
        "technique": technique_info["label"],
        "channel": channel,
        "time(sec)": point.time,
        "Ewe(V)": point.voltage,
        "Q-Q0(mAh)": optional_measurement(point, "charge", 1 / 3.6),
        "I(mA)": optional_measurement(point, "current", 1000),
        "cycle#": int(cycle) if math.isfinite(cycle) else math.nan,
        "Ece (V)": optional_measurement(point, "ece"),
    }


class GCPLProgram(BiologicProgram):
    """Run and decode multiple BioLogic techniques as one sequence."""

    def __init__(self, device, sequence, channels):
        super().__init__(
            device,
            {channel: {} for channel in channels},
            autoconnect=False,
        )
        self.sequence = sequence
        self.rows = []

    def load_sequence(self):
        techniques = [item["technique"] for item in self.sequence]
        parameter_types = [item["parameter_types"] for item in self.sequence]

        for channel in self.channels:
            parameters = [item["parameters"][channel] for item in self.sequence]
            self.device.load_techniques(
                channel,
                techniques,
                parameters,
                types=parameter_types,
            )

    async def _retrieve_data_segment(self, channel):
        raw = await self.device.get_data(channel)
        if raw.info.NbRows == 0 or raw.info.NbCols == 0:
            return empty_segment(raw)

        technique_index = raw.info.TechniqueIndex
        if not 0 <= technique_index < len(self.sequence):
            raise RuntimeError(
                f"Device returned invalid technique index {technique_index}."
            )

        technique_info = self.sequence[technique_index]
        program = technique_info["program"]
        try:
            parsed_data = dp.parse(
                raw.data,
                raw.info,
                program._data_fields,
                self.device,
            )
        except RuntimeError:
            return empty_segment(raw)

        segment = DataSegment(parsed_data, raw.info, raw.values)
        processed_points = []
        for raw_point in parsed_data:
            point = program._fields(*program._field_values(raw_point, segment))
            processed_points.append(point)
            self.rows.append(gcpl_measurement_row(point, technique_info, channel))

        return DataSegment(processed_points, raw.info, raw.values)

    async def retrieve_data(self, read_interval):
        return await super()._retrieve_data(read_interval)

    def run(self, read_interval=0.5):
        self.load_sequence()
        self.device.start_channels(self.channels)
        asyncio.run(self.retrieve_data(read_interval))


def run_gcpl(
    sequence_groups=None,
    cp_template=None,
    ca_template=None,
    ocv_template=None,
    configurations=None,
    cp_voltage_limits=None,
    ca_current_limits=None,
    channels=None,
    read_interval=None,
    address=None,
):
    """Connect, compile, run, and safely disconnect one GCPL sequence."""

    settings = parameter_values(TECHNIQUE_PARAMETERS, "GCPL")
    if sequence_groups is None:
        sequence_groups = settings["sequence_groups"]
    if cp_template is None:
        cp_template = get_technique_parameters("GCPL_CP")
    if ca_template is None:
        ca_template = get_technique_parameters("GCPL_CA")
    if ocv_template is None:
        ocv_template = get_technique_parameters("GCPL_OCV")
    if configurations is None:
        configurations = get_channel_configurations()
    if cp_voltage_limits is None:
        cp_voltage_limits = settings["cp_voltage_limits"]
    if ca_current_limits is None:
        ca_current_limits = settings["ca_current_limits"]
    if read_interval is None:
        read_interval = settings["read_interval"]

    selected_channels = list(configurations) if channels is None else channels
    device = connect(address)
    try:
        apply_channel_configurations(device, configurations)
        sequence = create_sequence(
            device,
            sequence_groups,
            cp_template,
            ca_template,
            ocv_template,
            selected_channels,
            cp_voltage_limits,
            ca_current_limits,
        )
        program = GCPLProgram(device, sequence, selected_channels)
        program.run(read_interval)
    finally:
        disconnect(device)

    return program


def make_column_continuous(dataframe, column, reset_only=False, use_max=False):
    """Offset every technique step from the preceding step on each channel."""

    adjusted = dataframe.copy()
    for channel in adjusted["channel"].drop_duplicates():
        previous_end = None
        channel_indexes = adjusted.index[adjusted["channel"] == channel]
        steps = adjusted.loc[channel_indexes, "sequence step"].drop_duplicates()

        for step in steps:
            indexes = adjusted.index[
                (adjusted["channel"] == channel)
                & (adjusted["sequence step"] == step)
            ]
            values = pd.to_numeric(adjusted.loc[indexes, column], errors="coerce")
            valid = values.dropna()
            if valid.empty:
                continue

            should_shift = previous_end is not None and (
                not reset_only or valid.iloc[0] < previous_end
            )
            if should_shift:
                adjusted.loc[valid.index, column] = (
                    valid + previous_end - valid.iloc[0]
                )

            adjusted_values = pd.to_numeric(
                adjusted.loc[valid.index, column],
                errors="coerce",
            )
            previous_end = (
                adjusted_values.max() if use_max else adjusted_values.iloc[-1]
            )

    return adjusted


def make_time_continuous(dataframe):
    return make_column_continuous(
        dataframe,
        "time(sec)",
        reset_only=True,
        use_max=True,
    )


def make_charge_continuous(dataframe):
    return make_column_continuous(dataframe, "Q-Q0(mAh)")


def save_gcpl_data(rows, output_path):
    """Save every GCPL technique using one common CSV format."""

    if not rows:
        raise ValueError("No GCPL measurements were collected.")

    dataframe = make_time_continuous(pd.DataFrame(rows, columns=GCPL_COLUMNS))
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    dataframe.to_csv(output_path, index=False)
    return dataframe


GCPL_PLOT_SPECS = [
    ("Ewe(V)", "Ewe vs Time", "Ewe (V)", 1.0),
    ("I(mA)", "Current vs Time", "Current (nA)", 1_000_000),
    ("Q-Q0(mAh)", "Q-Q0 vs Time", "Q-Q0 (mAh)", 1.0),
    ("Ece (V)", "Ece vs Time", "Ece (V)", 1.0),
]


def plot_gcpl_measurement(axis, dataframe, column, scale):
    multiple_channels = dataframe["channel"].nunique() > 1
    for (channel, step), step_data in dataframe.groupby(
        ["channel", "sequence step"],
        sort=True,
    ):
        valid = step_data.dropna(subset=["time(sec)", column])
        if valid.empty:
            continue

        label = f"{step}: {valid['technique'].iloc[0]}"
        if multiple_channels:
            label += f" (channel {channel})"
        axis.plot(valid["time(sec)"], valid[column] * scale, label=label)


def plot_gcpl_data(data, output_path):
    """Generate the shared four-panel GCPL plot."""

    dataframe = as_dataframe(data)
    if dataframe.empty:
        raise ValueError("No GCPL measurements are available to plot.")

    plot_dataframe = make_charge_continuous(dataframe)
    figure, axes = plt.subplots(
        nrows=2,
        ncols=2,
        figsize=(12, 8),
        constrained_layout=True,
    )
    for axis, (column, title, ylabel, scale) in zip(
        axes.flat,
        GCPL_PLOT_SPECS,
    ):
        plot_gcpl_measurement(axis, plot_dataframe, column, scale)
        axis.set(title=title, xlabel="Time (s)", ylabel=ylabel)
        axis.grid(True, alpha=0.3)
        if axis.lines:
            axis.legend(fontsize=8)

    save_figure(figure, output_path)

"""Run limit-controlled chronopotentiometry using shared parameters.

from pathlib import Path

if __package__:
    from . import technique_library as tl
else:
    import technique_library as tl


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "CP_LIMIT"
CSV_PATH = DATA_DIR / "080626_1319CP_-1nA_1C17_CETOGRND_.csv"
FIG_PATH = DATA_DIR / "080626_1319CP_-1nA_1C17_CETOGRND_.png"


def main():
    program = tl.run_cp_limit()
    dataframe = tl.save_cp_limit_data(program, CSV_PATH)
    tl.plot_cp_limit(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()


Run cyclic voltammetry using the shared parameters.

from pathlib import Path

if __package__:
    from . import technique_library as tl
else:
    import technique_library as tl


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "CV"
CSV_PATH = DATA_DIR / "0806526_1326_CV_-1V-1V_100mVs-1_1C16_CETOGRND.csv"
FIG_PATH = DATA_DIR / "0806526_1326_CV_-1V-1V_100mVs-1_1C16_CETOGRND.png"


def main():
    program = tl.run_cv()
    dataframe = tl.save_cv_data(program, CSV_PATH)
    tl.plot_cv(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()

Run open-circuit voltage using the shared parameters.

from pathlib import Path

if __package__:
    from . import technique_library as tl
else:
    import technique_library as tl


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "OCV"
CSV_PATH = DATA_DIR / "ocv_results.csv"
FIG_PATH = DATA_DIR / "ocv_results.png"


def main():
    program = tl.run_ocv()
    dataframe = tl.save_ocv_data(program, CSV_PATH)
    tl.plot_ocv(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()

Run galvanostatic cycling using the shared parameters.

from pathlib import Path

if __package__:
    from . import technique_library as tl
else:
    import technique_library as tl


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "GCPL"
CSV_PATH = DATA_DIR / "081826_1150_GPCL_3C02_CETOGRND_.csv"
FIG_PATH = DATA_DIR / "081826_1150_GPCL_3C02_CETOGRND_.png"


def main():
    program = tl.run_gcpl()
    dataframe = tl.save_gcpl_data(program.rows, CSV_PATH)
    tl.plot_gcpl_data(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()
"""
