import os
import math
import time
from datetime import datetime as dt
import asyncio
from collections import namedtuple
import logging
import warnings
from enum import Enum

from . import BiologicProgram
from .program import CallBack, DataSegment
from .lib import ec_lib as ecl
from .lib import data_parser as dp
from .lib import technique_fields as tfs


class CallBack_Timeout:
    """A timeout callback.
    The callback must be started before it can be called.
    """

    def __init__(
        self,
        program,
        cb,
        timeout,
        repeat=True,
        args=[],
        kwargs={},
        timeout_type="interval",
    ):
        """Creates a CallBack_Timeout.

        :param program: BiologicProgram the function is running in.
        :param cb: Callback function to run.
            Should accept the program as the first parameter.
        :param timeout: Timeout is seconds.
        :param repeat: Repeat the callback.
            If True, repeats indefinitely.
            If a number, repeats that many times.
            If False, only runs once.
            [Default: True]
        :param args: List of arguments to pass to the callback function.
            [Default: []]
        :param kwargs: Dictionary of keywrod arguments to pass to the callback function.
            [Default: {}]
        :param timeout_type: Type of timeout.
            Values are [ 'interval', 'between' ]
            interval: Time between callback starts
            between: Time between last finish and next start
            [Default: 'interval']
        """
        self.__program = program
        self.__cb = CallBack(cb, args, kwargs)
        self.timeout = timeout
        self.timeout_type = timeout_type
        self.is_alive = False

        self.repeat = 1 if (repeat is False) else repeat

        self.__calls = 0
        self.__last_call = None

    @property
    def callback(self):
        """
        :returns: CallBack structure of the callback function.
        """
        return self.__cb

    @property
    def elapsed(self):
        """
        :returns: time since last call.
        """
        return time.time() - self.__last_call

    @property
    def calls(self):
        """
        :returns: Number of calls.
        """
        return self.__calls

    @property
    def exhausted(self):
        """
        :returns: If number of calls has reached number of repititions.
        """
        if self.repeat is True:
            return False

        return self.calls >= self.repeat

    def is_due(self):
        """
        :returns: If the function is due to be run or not.
        """
        return self.elapsed >= self.timeout

    def run(self):
        """Runs the callback function."""
        # function set up
        cb = self.callback.function
        args = self.callback.args
        kwargs = self.callback.kwargs

        # internal trackers
        self.__calls += 1
        if self.timeout_type == "interval":
            self.__last_call = time.time()

        # callback
        cb(self.__program, *args, **kwargs)

        if self.timeout_type == "between":
            self.__last_call = time.time()

    def start(self):
        """Starts the callback."""
        self.is_alive = True
        self.__last_call = time.time()

    def cancel(self):
        """Cancels the callback."""
        self.is_alive = False

    def call(self):
        """Runs the callback is all conditions are met."""
        if self.is_alive and not self.exhausted and self.is_due():
            self.run()


# --- helper function ---


def set_defaults(params, defaults, channels):
    """Combines parameter and default dictionaries.

    :param params: Parameter or channel parameter dictionary.
    :param defaults: Default dictionary.
        Values used if key is not present in parameter dictionary.
    :param channels: List of channels or None if params is keyed by channel.
    :returns: Dictionary with defualt values set, if not set in parameters dictionary.
    """
    if channels is None:
        # parameters by channel
        for ch, ch_params in params.items():
            params[ch] = {**defaults, **ch_params}

    else:
        params = {**defaults, **params}

    return params


def map_params(
    key_map,
    params,
    by_channel=True,
    keep=False,
    inplace=False,
    discard_unmapped=False,
    convert_enums=False,
):
    """Returns a dictionary with names mapped.

    :param key_map: Dictionary keyed by original keys with new keys as values.
    :param params: Dictionary of parameters.
    :param by_channel: Whether params is by channel, or only parameters.
        [Default: True]
    :param keep: True to keep original name, False to remove it.
        [Default: False]
    :param inplace: Transform original params dictionary, or create a new one.
        [Default: False]
    :param discard_unmapped: True to discard items in params if not in key_map,
        False to keep unapped items.
        [Default: False]
    :param convert_enums: True to convert Enum instances to values, False to leave as Enums.
        [Default: False]
    :returns: Dictionary with mapped keys.
    """

    def map_ch_params(ch_params):
        """Maps channel parameters inplace.

        :param ch_params: Parameter dictionary.
        :returns: Modified parameter dictionary.
        """
        mapped = {n_key: ch_params[o_key] for o_key, n_key in key_map.items()}
        if convert_enums:
            mapped = {
                key: value.value if isinstance(value, Enum) else value
                for key, value in mapped.items()
            }

        if not keep:
            # remove original keys
            for o_key in key_map:
                del ch_params[o_key]

        ch_params.update(mapped)

        if discard_unmapped:
            # Remove any unmapped keys
            for key in list(ch_params.keys()):
                if key not in key_map.values() and not (keep and key in key_map):
                    del ch_params[key]

    if not inplace:
        params = (
            {ch: ch_params.copy() for ch, ch_params in params.items()}
            if by_channel
            else params.copy()
        )

    if by_channel:
        for ch, ch_params in params.items():
            map_ch_params(ch_params)

    else:
        map_ch_params(params)

    return params


def map_hardware_params(params, by_channel=True, keep=False, inplace=False):
    """Returns a dictionary with ONLY common hardware parameter names mapped.

    :param params: Dictionary of parameters.
    :param by_channel: Whether params is by channel, or only parameters.
        [Default: True]
    :param keep: True to keep original name, False to remove it.
        [Default: False]
    :param inplace: Transform original params dictionary, or create a new one.
        [Default: False]
    :returns: Dictionary with mapped keys.
    """
    if by_channel:
        mapped = {
            ch: map_hardware_params(
                ch_params,
                by_channel=False,
                keep=keep,
                inplace=inplace,
            )
            for ch, ch_params in params.items()
        }
        if inplace:
            params.update(mapped)
            return params
        return mapped

    hardware_param_map = {
        "voltage_range": "E_Range",
        "current_range": "I_Range",
        "bandwidth": "Bandwidth",
        "timebase": "tb",
    }

    # Only map parameters that exist in params
    hardware_param_map = {
        k: v for k, v in hardware_param_map.items() if k in params.keys()
    }

    if len(hardware_param_map) == 0:
        if inplace:
            params.clear()
            return params
        return {}

    # Return only the mapped params
    return map_params(
        hardware_param_map,
        params,
        by_channel=by_channel,
        keep=keep,
        inplace=inplace,
        discard_unmapped=True,
        convert_enums=True,
    )

#must be in VMP-300 device families to use
def configure_ece_and_charge(
    params,
    fields=None,
    technique_params=None,
    base_timebase=None,
):
    """Configure XCTR Ece and charge recording for a program."""

    settings = {
        bool(channel_params.get("record_ece", False))
        for channel_params in params.values()
    }

    if len(settings) > 1:
        raise ValueError("record_ece must be identical across channels.")

    enabled = settings.pop() if settings else False
    configured_fields = fields

    if enabled and fields is not None:
        configured_fields = [
            *fields,
            dp.FieldInfo(
                "ece",
                ecl.ParameterType.SINGLE,
            ),
            dp.FieldInfo(
                "charge",
                ecl.ParameterType.SINGLE,
            ),
        ]

    if enabled and technique_params is not None:

        for channel in params:
            channel_technique_params = technique_params[channel]
            original_timebase = float(
                channel_technique_params.get(
                    "tb",
                    base_timebase,
                )
            )
            channel_technique_params.update(
                {
                    "xctr": 0x01 | 0x40,
                    "tb": original_timebase + 6e-6,
                }
            )

    return enabled, configured_fields

def get_current_range(i_max):
    """Get current range based on maximum current.

    :param i_max: Maximum expected current
    :returns: ec_lib.IRange corresponding to maximum current.
    """
    i_max = abs(i_max)
    if i_max < 100e-12:
        i_range = ecl.IRange.p100
    elif i_max < 1e-9:
        i_range = ecl.IRange.n1
    elif i_max < 10e-9:
        i_range = ecl.IRange.n10
    elif i_max < 100e-9:
        i_range = ecl.IRange.n100
    elif i_max < 1e-6:
        i_range = ecl.IRange.u1
    elif i_max < 10e-6:
        i_range = ecl.IRange.u10
    elif i_max < 100e-6:
        i_range = ecl.IRange.u100
    elif i_max < 1e-3:
        i_range = ecl.IRange.m1
    elif i_max < 10e-3:
        i_range = ecl.IRange.m10
    elif i_max < 100e-3:
        i_range = ecl.IRange.m100
    elif i_max <= 1:
        i_range = ecl.IRange.a1
    else:
        raise ValueError("Current too large.")

    return i_range

def set_current_range(ch_params, i_max):
    user_i_range = ch_params.get("current_range", None)
    if user_i_range is None:
        # No user-specified value. Set based on expected i_max
        ch_params["current_range"] = get_current_range(i_max)
    else:
        # Check user-specified current range
        if not isinstance(user_i_range, ecl.IRange):
            user_i_range = ecl.IRange(user_i_range)

        # Warn, but don't overwrite
        # Fixed range codes 0..10 represent 10**(code - 10) amperes.
        # KEEP, BOOSTER, and AUTO do not specify a fixed capacity.
        if (
            ecl.IRange.p100.value <= user_i_range.value <= ecl.IRange.a1.value
            and abs(i_max) > 10.0 ** (user_i_range.value - ecl.IRange.a1.value)
        ):
            warnings.warn(
                "Expected maximum current of {:.1e} A exceeds "
                "provided current range {}".format(i_max, user_i_range)
            )

def get_voltage_range(v_max):
    """Get voltage range based on maximum voltage.

    :param v_max: Maximum expected voltage
    :returns: ec_lib.ERange corresponding to maximum voltage.
    """
    v_max = abs(v_max)

    if v_max < 2.5:
        v_range = ecl.ERange.v2_5

    elif v_max < 5:
        v_range = ecl.ERange.v5

    elif v_max < 10:
        v_range = ecl.ERange.v10

    else:
        raise ValueError("Voltage too large.")

    return v_range

LimitConfig = namedtuple("LimitConfig", ["config_int", "value"])

def configure_limit(
    variable: ecl.LimitVariable,
    comparison: ecl.LimitComparison,
    logic: ecl.LimitLogic,
    limit_value: float,
):
    """Create a limit configuration for CA Limit or CP Limit techniques.
    Exit behavior is controlled separately by the exit_condition parameter.
    Example: create a limit that will stop the technique if the current exceeds 1 mA:
        limit = configure_limit(
            ecl.LimitVariable.I,  # Apply limit to current
            ecl.LimitComparison.GT,  # Stop if greater than
            ecl.LimitLogic.OR,  # Stop if this limit OR another limit is violated
            1e-3  # limit value 0.001 A (1 mA)
        )
        params = {..., 'limits': [ limit ]}
        ca = CALimit(device, params)

    :param ecl.LimitVariable variable: Variable to limit.
        Options: I, E, AUX1, AUX2 (see ec_lib.LimitVariable).
    :param ecl.LimitComparison comparison: Comparison operator (see ec_lib.LimitComparison).
        If GT, stop the technique if the variable is greater than limit_value.
        If LT, stop the technique if the variable is less than limit_value.
    :param ecl.LimitLogic logic: Logical operator for assessing multiple limits.
        Options: AND, OR (see ec_lib.LimitLogic)
    :param float limit_value: Limit value applied to specified variable.
        Has units of volts for voltage limit or amps for current limit.
    :returns: LimitConfig tuple
    """
    # Bit 0: Active; bit 1: Logic; bits 2..4: Sign; bits 5..31: Variable.
    config_int = (
        1
        | (logic.value << 1)
        | (comparison.value << 2)
        | (variable.value << 5)
    )

    return LimitConfig(config_int, limit_value)


class OCV(BiologicProgram):
    """Runs an open-circuit-voltage measurement."""

    def __init__(
        self,
        device,
        params,
        **kwargs,
    ):
        """
        Parameters
        ----------
        time:
            OCV duration in seconds.

        time_interval:
            Maximum time between readings.
            Default: 1 second.

        voltage_interval:
            Maximum voltage change between readings.
            Default: 0.01 V.

        record_ece:
            Record Ece and Q-Q0 through XCTR.
            Only supported by VMP-300-family devices.
            Default: False.

        timebase:
            Original OCV timebase before adding the
            XCTR measurement delay.
            VMP-300 default: 20 microseconds.
        """

        defaults = {
            "time_interval": 1.0,
            "voltage_interval": 0.01,
            "record_ece": False,
            "timebase": 20e-6,
        }

        channels = (
            kwargs["channels"]
            if "channels" in kwargs
            else None
        )

        params = set_defaults(
            params,
            defaults,
            channels,
        )

        super().__init__(
            device,
            params,
            **kwargs,
        )

        is_vmp300_family = (
            ecl.is_in_SP300_family(
                self.device.kind
            )
        )

        base_fields = (
            dp.SP300_Fields.OCV
            if is_vmp300_family
            else dp.VMP3_Fields.OCV
        )

        (
            self._record_ece,
            self._data_fields,
        ) = configure_ece_and_charge(
            self.params,
            fields=base_fields,
        )


        self._techniques = ["ocv"]
        self._parameter_types = tfs.OCV

        if self._record_ece:
            self.field_titles = [
                "Time [s]",
                "Voltage [V]",
                "Q-Q0 [A*s]",
                "Ece [V]",
            ]

            self._fields = namedtuple(
                "OCV_Datum",
                [
                    "time",
                    "voltage",
                    "charge",
                    "ece",
                ],
            )

        else:
            self.field_titles = [
                "Time [s]",
                "Voltage [V]",
            ]

            self._fields = namedtuple(
                "OCV_Datum",
                [
                    "time",
                    "voltage",
                ],
            )

        def field_values(
            datum,
            segment,
        ):
            time = dp.calculate_time(
                datum.t_high,
                datum.t_low,
                segment.info,
                segment.values,
            )

            if self._record_ece:
                return (
                    time,
                    datum.voltage,
                    datum.charge,
                    datum.ece,
                )

            return (
                time,
                datum.voltage,
            )

        self._field_values = field_values

    def run(
        self,
        retrieve_data=True,
    ):
        """
        Run the OCV technique.

        Parameters
        ----------
        retrieve_data:
            Retrieve data and disconnect automatically.
            Default: True.
        """

        parameters = {}

        for (
            channel,
            channel_params,
        ) in self.params.items():

            parameters[channel] = {
                "Rest_time_T": (
                    channel_params["time"]
                ),
                "Record_every_dE": (
                    channel_params[
                        "voltage_interval"
                    ]
                ),
                "Record_every_dT": (
                    channel_params[
                        "time_interval"
                    ]
                ),
            }

            parameters[channel].update(
                map_hardware_params(
                    channel_params,
                    by_channel=False,
                )
            )

        configure_ece_and_charge(
            self.params,
            technique_params=parameters,
            base_timebase=20e-6,
        )

        return self._run(
            "ocv",
            parameters,
            retrieve_data=retrieve_data,
        )

class CALimit(BiologicProgram):
    """Runs a cyclic amperometry technqiue."""

    def __init__(self, device, params, **kwargs):
        """
        :param device: BiologicDevice.
        :param params: Program parameters.
            Params are
            voltages: List of voltages in Volts.
            durations: List of times in seconds.
            vs_initial: If step is vs. initial or previous.
                [Default: False]
            time_interval: Maximum time interval between points.
                [Default: 1]
            current_interval: Maximum current change between points.
                [Default: 0.001]
            current_range: Current range. Use ec_lib.IRange.
                [Default: IRange.m10 ]
            limits: List of LimitConfig tuples defining limits for the
                technique. LimitConfig objects should be constructed
                with configure_limit. Up to 3 limits can be supplied.
                If no limits are supplied, you should use the standard
                CA technique instead of CALimit.
                [Default: []]
            step_limits: List containing one list of LimitConfig tuples for
                each voltage step. Each step supports up to 3 limits. When
                supplied, this overrides limits and must have the same length
                as voltages.
                [Default: None]
            exit_condition: How to exit the technique when a limit is
                violated. Use ec_lib.ExitCondition.
                [Default: ExitCondition.STOP]
            record_ece: Record Ece and Q-Q0 using XCTR.
                This is only supported by VMP-300 family devices.
                [Default: False]
            timebase: Original CALimit timebase before the XCTR delay.
                The VMP-300 default is 34 us.
                [Default: 34e-6]
            charge_limit_mAh: Host-monitored maximum absolute change
                in XCTR charge. The channel is stopped when
                |change in Q| exceeds this value. Requires
                record_ece=True. Use None to disable the limit.
                [Default: None]
        :param **kwargs: Parameters passed to BiologicProgram.
        """
        defaults = {
            "vs_initial": False,
            "time_interval": 1.0,
            "current_interval": 1e-3,
            "current_range": ecl.IRange.m10,
            "limits": [],
            "step_limits": None,
            "exit_condition": ecl.ExitCondition.STOP,
            "record_ece": False,
            "timebase": 34e-6,
            "charge_limit_mAh": None,
        }

        channels = kwargs["channels"] if ("channels" in kwargs) else None
        params = set_defaults(params, defaults, channels)

        super().__init__(device, params, **kwargs)

        is_vmp300_family = ecl.is_in_SP300_family(
            self.device.kind
        )

        base_fields = (
            dp.SP300_Fields.CALIMIT
            if is_vmp300_family
            else dp.VMP3_Fields.CALIMIT
        )

        (
            self._record_ece,
            self._data_fields,
        ) = configure_ece_and_charge(
            self.params,
            fields=base_fields,
        )

        if (
            self._record_ece
            and not is_vmp300_family
        ):
            raise ValueError(
                "XCTR Ece and charge recording is only "
                "supported on VMP-300 family devices."
            )

        # Charge is not a native CALimit limit variable.  Keep the
        # requested limits on the host and evaluate them as decoded
        # XCTR data arrives.
        self._charge_limits_mAh = {}
        self._charge_origins_As = {}
        self.charge_progress_mAh = {
            channel: 0.0
            for channel in self.channels
        }
        self.charge_limit_reached = {
            channel: False
            for channel in self.channels
        }

        for channel, channel_params in self.params.items():
            charge_limit = channel_params.get(
                "charge_limit_mAh"
            )

            if charge_limit is not None:
                charge_limit = float(charge_limit)


            self._charge_limits_mAh[channel] = (
                charge_limit
            )

        self._techniques = ["calimit"]
        self._parameter_types = tfs.CALIMIT

        field_titles = [
            "Time [s]",
            "Voltage [V]",
            "Current [A]",
            "Power [W]",
            "Cycle",
        ]

        field_names = [
            "time",
            "voltage",
            "current",
            "power",
            "cycle",
        ]

        if self._record_ece:
            field_titles.extend(
                [
                    "Ece [V]",
                    "Q-Q0 [A*s]",
                ]
            )
            field_names.extend(
                [
                    "ece",
                    "charge",
                ]
            )

        self.field_titles = field_titles

        self._fields = namedtuple(
            "CALimit_Datum",
            field_names,
        )

        def field_values(datum, segment):
            values = [
                dp.calculate_time(
                    datum.t_high,
                    datum.t_low,
                    segment.info,
                    segment.values,
                ),
                datum.voltage,
                datum.current,
                datum.voltage * datum.current,
                datum.cycle,
            ]

            if self._record_ece:
                values.extend(
                    [
                        datum.ece,
                        datum.charge,
                    ]
                )

            return tuple(values)

        self._field_values = field_values

    def set_charge_limit(
        self,
        charge_limit_mAh,
        channel=None,
    ):
        """Set or disable the host-monitored charge limit."""

        selected_channels = (
            self.channels
            if channel is None
            else [channel]
        )

        for selected_channel in selected_channels:
            if selected_channel not in self.channels:
                raise ValueError(
                    f"Invalid channel: {selected_channel}"
                )

            if charge_limit_mAh is None:
                validated_limit = None
            else:
                validated_limit = float(
                    charge_limit_mAh
                )

            self._charge_limits_mAh[
                selected_channel
            ] = validated_limit
            self._charge_origins_As.pop(
                selected_channel,
                None,
            )
            self.charge_progress_mAh[
                selected_channel
            ] = 0.0
            self.charge_limit_reached[
                selected_channel
            ] = False

    def check_charge_limit(self, channel, point):
        """Stop the channel when |change in Q| exceeds its limit."""

        charge_limit = self._charge_limits_mAh[
            channel
        ]

        if (
            charge_limit is None
            or self.charge_limit_reached[channel]
        ):
            return False

        charge_As = float(point.charge)

        if not math.isfinite(charge_As):
            return False

        if channel not in self._charge_origins_As:
            self._charge_origins_As[channel] = charge_As
            return False

        change_in_charge_mAh = abs(
            (
                charge_As
                - self._charge_origins_As[channel]
            )
            / 3.6
        )

        self.charge_progress_mAh[
            channel
        ] = change_in_charge_mAh

        if change_in_charge_mAh > charge_limit:
            self.charge_limit_reached[channel] = True

            logging.info(
                "Channel %s reached its charge limit: "
                "%.6f mAh > %.6f mAh",
                channel,
                change_in_charge_mAh,
                charge_limit,
            )

            self.device.stop_channel(channel)
            return True

        return False

    async def _retrieve_data_segment(self, channel):
        """Retrieve CA data and inspect only the newly decoded rows."""

        previous_length = len(self._data[channel])

        segment = await super()._retrieve_data_segment(
            channel
        )

        new_points = self._data[channel][
            previous_length:
        ]

        for point in new_points:
            if self.check_charge_limit(channel, point):
                break

        return segment

    def run(self, retrieve_data=True):
        """
        :param retrieve_data: Automatically retrieve and disconnect from device.
            [Default: True]
        """
        self._charge_origins_As.clear()

        for channel in self.channels:
            self.charge_progress_mAh[channel] = 0.0
            self.charge_limit_reached[channel] = False

        params = {}
        for ch, ch_params in self.params.items():
            steps = len(ch_params["voltages"])
            params[ch] = {
                "Voltage_step": ch_params["voltages"],
                "vs_initial": [ch_params["vs_initial"]] * steps,
                "Duration_step": ch_params["durations"],
                "Step_number": steps - 1,
                "Record_every_dT": ch_params["time_interval"],
                "Record_every_dI": ch_params["current_interval"],
                "Exit_Cond": [ch_params["exit_condition"].value] * steps,
                "N_Cycles": ch_params["cycles"] if "cycles" in ch_params else 0,
            }

            step_limits = ch_params["step_limits"]

            # Preserve the original behavior when omitted.
            if step_limits is None:
                step_limits = [
                    ch_params["limits"]
                    for _ in range(steps)
                ]

            for test_index in range(3):
                test_configs = []
                test_values = []

                for limits_for_step in step_limits:
                    if test_index < len(limits_for_step):
                        limit = limits_for_step[test_index]
                        test_configs.append(limit.config_int)
                        test_values.append(limit.value)
                    else:
                        test_configs.append(0)
                        test_values.append(0.0)

                test_number = test_index + 1

                params[ch][
                    f"Test{test_number}_Config"
                ] = test_configs

                params[ch][
                    f"Test{test_number}_Value"
                ] = test_values

            params[ch].update(map_hardware_params(ch_params, by_channel=False))

        configure_ece_and_charge(
            self.params,
            technique_params=params,
            base_timebase=34e-6,
        )

        # run technique
        data = self._run("calimit", params, retrieve_data=retrieve_data)

    def update_voltages(self, voltages, durations=None, vs_initial=None):
        """Update voltage and duration parameters.

        :param voltages: Dictionary of voltages list keyed by channel,
            or single voltage to apply to all channels.
        :param durations: Dictionary of durations list keyed by channel,
            or single duration to apply to all channels.
        :param vs_initial: Dictionary of vs. initial booleans keyed by channel,
            or single vs. initial boolean to apply to all channels.
        """
        # format params
        if not isinstance(voltages, dict):
            # transform to dictionary if needed
            voltages = {ch: voltages for ch in self.channels}

        if (durations is not None) and (not isinstance(durations, dict)):
            # transform to dictionary if needed
            durations = {ch: durations for ch in self.channels}

        if (vs_initial is not None) and (not isinstance(vs_initial, dict)):
            # transform to dictionary if needed
            vs_initial = {ch: vs_initial for ch in self.channels}

        # update voltages
        for ch, ch_voltages in voltages.items():
            if not isinstance(ch_voltages, list):
                # single voltage given, make list
                ch_voltages = [ch_voltages]

            steps = len(ch_voltages)
            params = {"Voltage_step": ch_voltages, "Step_number": steps - 1}

            if durations is not None:
                params["Duration_step"] = (
                    durations[ch]
                    if isinstance(durations[ch], list)
                    else [durations[ch]] * steps
                )

            if vs_initial is not None:
                params["vs_initial"] = [vs_initial[ch]] * steps

            self.device.update_parameters(
                ch, "calimit", params, types=self._parameter_types
            )
            self.params[ch]["voltages"] = ch_voltages.copy()
            if durations is not None:
                self.params[ch]["durations"] = params["Duration_step"].copy()
            if vs_initial is not None:
                self.params[ch]["vs_initial"] = vs_initial[ch]

class CPLimit(BiologicProgram):
    """Runs a chrono-potentiometry technique with limit conditions."""

    def __init__(self, device, params, **kwargs):
        """
        :param device: BiologicDevice.
        :param params: Program parameters.
            Params are
            currents: List of currents in Amps.
            durations: List of times in seconds.
            vs_initial: If step is vs. initial or previous.
                [Default: False]
            time_interval: Maximum time interval between points in seconds.
                [Default: 1]
            voltage_interval: Maximum voltage change between points in Volts.
                [Default: 0.001]
            limits: List of LimitConfig tuples defining limits for the
                technique. LimitConfig objects should be constructed with
                configure_limit. Up to 3 limits can be supplied. If no limits
                are supplied, use the standard CP technique instead.
                [Default: []]
            exit_condition: How to exit the technique when a limit is
                violated. Use ec_lib.ExitCondition.
                [Default: ExitCondition.STOP]
        :param **kwargs: Parameters passed to BiologicProgram.
        """
        defaults = {
            "vs_initial": False,
            "time_interval": 1.0,
            "voltage_interval": 1e-3,
            "limits": [],
            "step_limits": None,
            "exit_condition": ecl.ExitCondition.STOP,
            "record_ece": False,
            "timebase": 34e-6,
        }

        channels = kwargs["channels"] if ("channels" in kwargs) else None
        params = set_defaults(params, defaults, channels)
        super().__init__(device, params, **kwargs)

        is_vmp300_family = ecl.is_in_SP300_family(
            self.device.kind
        )

        base_fields = (
            dp.SP300_Fields.CPLIMIT
            if is_vmp300_family
            else dp.VMP3_Fields.CPLIMIT
        )

        (
            self._record_ece,
            self._data_fields,
        ) = configure_ece_and_charge(
            self.params,
            fields=base_fields,
        )

        if (
            self._record_ece
            and not is_vmp300_family
        ):
            raise ValueError(
                "XCTR Ece and charge recording is only "
                "supported on VMP-300 family devices."
            )

        # CPLimit requires a fixed current range based on the applied steps.
        for ch_params in self.params.values():
            i_max = max(abs(current) for current in ch_params["currents"])
            set_current_range(ch_params, i_max)

        self._techniques = ["cplimit"]
        self._parameter_types = tfs.CPLimit

        field_titles = [
            "Time [s]",
            "Voltage [V]",
            "Current [A]",
            "Power [W]",
            "Cycle",
        ]

        field_names = [
            "time",
            "voltage",
            "current",
            "power",
            "cycle",
        ]

        if self._record_ece:
            field_titles.extend(
                [
                    "Ece [V]",
                    "Q-Q0 [A*s]",
                ]
            )
            field_names.extend(
                [
                    "ece",
                    "charge",
                ]
            )

        self.field_titles = field_titles

        self._fields = namedtuple(
            "CPLimit_Datum",
            field_names,
        )

        def field_values(datum, segment):
            values = [
                dp.calculate_time(
                    datum.t_high,
                    datum.t_low,
                    segment.info,
                    segment.values,
                ),
                datum.voltage,
                datum.current,
                datum.voltage * datum.current,
                datum.cycle,
            ]

            if self._record_ece:
                values.extend(
                    [
                        datum.ece,
                        datum.charge,
                    ]
                )

            return tuple(values)

        self._field_values = field_values

    def run(self, retrieve_data=True):
        """
        :param retrieve_data: Automatically retrieve and disconnect from device.
            [Default: True]
        """
        params = {}
        for ch, ch_params in self.params.items():
            steps = len(ch_params["currents"])
            params[ch] = {
                "Current_step": ch_params["currents"],
                "vs_initial": [ch_params["vs_initial"]] * steps,
                "Duration_step": ch_params["durations"],
                "Step_number": steps - 1,
                "Record_every_dT": ch_params["time_interval"],
                "Record_every_dE": ch_params["voltage_interval"],
                "Exit_Cond": [ch_params["exit_condition"].value] * steps,
                "N_Cycles": ch_params["cycles"] if "cycles" in ch_params else 0,
            }

            step_limits = ch_params["step_limits"]

            # Preserve the original behavior when omitted.
            if step_limits is None:
                step_limits = [
                    ch_params["limits"]
                    for _ in range(steps)
                ]

            for test_index in range(3):
                test_configs = []
                test_values = []

                for limits_for_step in step_limits:
                    if test_index < len(limits_for_step):
                        limit = limits_for_step[test_index]
                        test_configs.append(limit.config_int)
                        test_values.append(limit.value)
                    else:
                        test_configs.append(0)
                        test_values.append(0.0)

                test_number = test_index + 1

                params[ch][
                    f"Test{test_number}_Config"
                ] = test_configs

                params[ch][
                    f"Test{test_number}_Value"
                ] = test_values

            params[ch].update(
                map_hardware_params(
                    ch_params,
                    by_channel=False,
                )
            )

        configure_ece_and_charge(
            self.params,
            technique_params=params,
            base_timebase=34e-6,
        )

        return self._run(
            "cplimit",
            params,
            retrieve_data=retrieve_data,
        )

    def update_currents(self, currents, durations=None, vs_initial=None):
        """Update current and duration parameters."""
        if not isinstance(currents, dict):
            currents = {ch: currents for ch in self.channels}

        if (durations is not None) and (not isinstance(durations, dict)):
            durations = {ch: durations for ch in self.channels}

        if (vs_initial is not None) and (not isinstance(vs_initial, dict)):
            vs_initial = {ch: vs_initial for ch in self.channels}

        for ch, ch_currents in currents.items():
            if not isinstance(ch_currents, list):
                ch_currents = [ch_currents]

            params = {
                "Current_step": ch_currents,
                "Step_number": len(ch_currents) - 1,
            }

            if durations is not None:
                params["Duration_step"] = (
                    durations[ch]
                    if isinstance(durations[ch], list)
                    else [durations[ch]] * len(ch_currents)
                )

            if vs_initial is not None:
                params["vs_initial"] = [vs_initial[ch]] * len(ch_currents)

            self.device.update_parameters(
                ch, "cplimit", params, types=self._parameter_types
            )
            self.params[ch]["currents"] = ch_currents.copy()
            if durations is not None:
                self.params[ch]["durations"] = params["Duration_step"].copy()
            if vs_initial is not None:
                self.params[ch]["vs_initial"] = vs_initial[ch]

class CV(BiologicProgram):
    """Runs a CV scan."""

    def __init__(self, device, params, **kwargs):
        """
        :param device: BiologicDevice.
        :param params: Program parameters.
            Params are
            start: Dictionary of start voltages keyed by channels. Ei in the figure [Defualt: 0]
            end: Dictionary of end voltages keyed by channels. Boundary voltage in forward scan.
                E1 in the figure [Defualt: 0.5]
            E2: Boundary voltage in backward scan. E2 in the figure [Defualt:0]
            Ef: End voltage in the final cycle scan [Defualt: 0]
            step: Voltage step. dEN/1000. [Default: 0.01]
            rate: Scan rate in V/s. [Default: 0.01]
            average: Average over points. [Default: False]
        :param **kwargs: Parameters passed to BiologicProgram.
        """
        """
        Ewe ^
            |        E1
            |        /\\
            |       /  \\        Ef
            |      /    \\      /
            |     /      \\    /
            |    /        \\  /
            |  Ei          \\/
            |               E2
            |
            –––––––––––––––––––––––––––––> t
        """
        # defaults
        defaults = {
            "vs_initial": False,
            "start": 0,
            "end": 0.5,
            "E2": 0,
            "Ef": 0,
            "step": 0.01,
            "rate": 0.01,  # V/s
            "average": False,
            "N_Cycles": 0,
            "Begin_measuring_I": 0.5,
            "End_measuring_I": 1,
            "record_ece": True,
        }
        channels = kwargs["channels"] if ("channels" in kwargs) else None
        params = set_defaults(params, defaults, channels)

        super().__init__(device, params, **kwargs)

        is_vmp300_family = ecl.is_in_SP300_family(
            self.device.kind
        )

        base_fields = (
            dp.SP300_Fields.CV
            if is_vmp300_family
            else dp.VMP3_Fields.CV
        )

        (
            self._record_ece,
            self._data_fields,
        ) = configure_ece_and_charge(
            self.params,
            fields=base_fields,
        )

        if (
            self._record_ece
            and not is_vmp300_family
        ):
            raise ValueError(
                "XCTR Ece and charge recording is only supported "
                "on VMP-300 family devices."
            )

        self._techniques = ["cv"]
        self._parameter_types = tfs.CV

        if self._record_ece:
            self.field_titles = [
                "Voltage [V]",
                "Ece [V]",
                "Current [A]",
                "Time [s]",
                "Power [W]",
                "Cycle",
                "Q-Q0 [A*s]",
            ]

            self._fields = namedtuple(
                "CV_Datum",
                [
                    "voltage",
                    "ece",
                    "current",
                    "time",
                    "power",
                    "cycle",
                    "charge",
                ],
            )

            self._field_values = (
                lambda datum, segment: (
                    datum.voltage,
                    datum.ece,
                    datum.current,
                    dp.calculate_time(
                        datum.t_high,
                        datum.t_low,
                        segment.info,
                        segment.values,
                    ),
                    datum.voltage
                    * datum.current,
                    datum.cycle,
                    datum.charge,
                )
            )

        else:
            self.field_titles = [
                "Voltage [V]",
                "Current [A]",
                "Time [s]",
                "Power [W]",
                "Cycle",
            ]

            self._fields = namedtuple(
                "CV_Datum",
                [
                    "voltage",
                    "current",
                    "time",
                    "power",
                    "cycle",
                ],
            )

            self._field_values = (
                lambda datum, segment: (
                    datum.voltage,
                    datum.current,
                    dp.calculate_time(
                        datum.t_high,
                        datum.t_low,
                        segment.info,
                        segment.values,
                    ),
                    datum.voltage
                    * datum.current,
                    datum.cycle,
                )
            )

    def run(self, retrieve_data=True):
        """
        :param retrieve_data: Automatically retrieve and disconenct form device.
            [Default: True]
        """
        # setup scan profile ( start -> end -> start )
        params = {}
        for ch, ch_params in self.params.items():
            """ "
            # Previously voltage_profile:
            voltage_profile = [ ch_params[ 'start' ] ]* 5
            voltage_profile[ 1 ] = ch_params[ 'end' ]
            """
            voltage_profile = [
                ch_params["start"],
                ch_params["end"],
                ch_params["E2"],
                ch_params["start"],
                ch_params["Ef"],
            ]

            params[ch] = {
                "vs_initial": [ch_params["vs_initial"]] * 5,
                "Voltage_step": voltage_profile,
                "Scan_Rate": [ch_params["rate"]] * 5,
                "Scan_number": 2,
                "Record_every_dE": ch_params["step"],
                "Average_over_dE": ch_params["average"],
                "N_Cycles": ch_params["N_Cycles"],
                "Begin_measuring_I": ch_params[
                    "Begin_measuring_I"
                ],  # start measurement at beginning of interval
                "End_measuring_I": ch_params[
                    "End_measuring_I"
                ],  # finish measurement at end of interval
            }
            params[ch].update(map_hardware_params(ch_params, by_channel=False))

        configure_ece_and_charge(
            self.params,
            technique_params=params,
            base_timebase=45e-6,
        )

        # run technique
        data = self._run("cv", params, retrieve_data=retrieve_data)

class GCPL(BiologicProgram):
    """Run and decode multiple BioLogic techniques as one sequence.

    Host charge limits are not supported. Data contains technique-specific
    points; use rows for the standardized mAh/mA export.
    """

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
            return DataSegment([], raw.info, raw.values)

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
            return DataSegment([], raw.info, raw.values)

        segment = DataSegment(parsed_data, raw.info, raw.values)
        processed_points = []
        for raw_point in parsed_data:
            point = program._fields(*program._field_values(raw_point, segment))
            processed_points.append(point)

            measurements = {}
            for name, scale in (
                ("charge", 1 / 3.6),
                ("current", 1000),
                ("ece", 1),
                ("cycle", 1),
            ):
                value = getattr(point, name, math.nan)
                try:
                    value = float(value)
                except (TypeError, ValueError):
                    value = math.nan

                measurements[name] = (
                    value * scale
                    if math.isfinite(value)
                    else math.nan
                )

            cycle = measurements["cycle"]
            self.rows.append(
                {
                    "sequence step": technique_info["step"],
                    "technique": technique_info["label"],
                    "channel": channel,
                    "time(sec)": point.time,
                    "Ewe(V)": point.voltage,
                    "Q-Q0(mAh)": measurements["charge"],
                    "I(mA)": measurements["current"],
                    "cycle#": (
                        int(cycle)
                        if math.isfinite(cycle)
                        else math.nan
                    ),
                    "Ece (V)": measurements["ece"],
                }
            )

        self._data[channel].extend(processed_points)
        for callback in self._cb_data:
            callback(segment, self)

        return DataSegment(processed_points, raw.info, raw.values)

    def run(self, read_interval=0.5):
        self.load_sequence()
        self.device.start_channels(self.channels)
        asyncio.run(self._retrieve_data(read_interval))
