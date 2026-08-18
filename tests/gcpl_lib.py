"""Shared CP, CA, and OCV configuration for linked GCPL tests."""

import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl


CHANNEL_CONFIGURATIONS = {
    0: {
        "connection": (
            ecl.ElectrodeConnection.CETOGRND
        ),
        "mode": ecl.ChannelMode.GROUNDED,
    },
}


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
