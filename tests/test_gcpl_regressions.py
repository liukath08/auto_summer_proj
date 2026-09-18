"""Regression checks for GCPL metadata and native API error handling."""

import asyncio
import ctypes
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from easy_biologic.device import BiologicDevice
from easy_biologic.lib import data_parser as dp, ec_lib as ecl
from easy_biologic.lib.ec_errors import EcError


class GCPLRegressionChecks(unittest.TestCase):
    def test_documented_metadata_bytes_decode_correctly(self):
        # Manual field order: seven int32, one double, one int32; alignment 4.
        raw = struct.pack("<7idi", 1, 2, 7, 3, 155, 0, 4, 123.5, 0)
        self.assertEqual(ctypes.sizeof(ecl.DataInfo), len(raw))
        self.assertEqual(ecl.DataInfo.StartTime.offset, 28)
        self.assertEqual(ecl.DataInfo.MuxPad.offset, 36)
        info = ecl.DataInfo.from_buffer_copy(raw)
        self.assertEqual(info.TechniqueIndex, 3)
        self.assertEqual(info.TechniqueID, 155)
        self.assertEqual(info.StartTime, 123.5)
        self.assertEqual(
            dp.calculate_time(0, 25, info, SimpleNamespace(TimeBase=0.04)),
            124.5,
        )

    def test_error_retains_numeric_code_and_original_message(self):
        error = EcError(-8)
        self.assertEqual(error.value, -8)
        self.assertEqual(
            str(error), "ERR_GEN_INVALIDCONF (-8): invalid instrument configuration"
        )

    def check_firmware_error(self, code, allowed):
        error = EcError(code)
        disconnect = MagicMock()
        with patch.multiple(
            ecl,
            connect=MagicMock(return_value=(77, ecl.DeviceInfo())),
            get_channels=MagicMock(return_value=[True]),
            init_channels=MagicMock(side_effect=error),
            disconnect=disconnect,
        ):
            device = BiologicDevice("USB0", populate_info=False)
            try:
                if allowed:
                    device.connect()
                    self.assertEqual(device.techniques, [[]])
                else:
                    with self.assertRaises(EcError) as caught:
                        device.connect()
                    self.assertIs(caught.exception, error)
            finally:
                if device.idn is not None:
                    device.disconnect()
        disconnect.assert_called_once_with(77)

    def test_already_loaded_firmware_is_allowed(self):
        self.check_firmware_error(-9, allowed=True)

    def test_other_firmware_errors_propagate(self):
        for code in (-4, -5, -8, -103):
            with self.subTest(code=code):
                self.check_firmware_error(code, allowed=False)


class NativeErrorChecks(unittest.TestCase):
    def test_each_parameter_definition_reports_errors(self):
        for name, value in (
            ("BL_DefineBoolParameter", False),
            ("BL_DefineIntParameter", 1),
            ("BL_DefineSglParameter", 1e-9),
        ):
            with self.subTest(function=name):
                with patch.object(ecl, name, return_value=-4):
                    with self.assertRaises(EcError) as caught:
                        ecl.create_parameter("Test", value, index=2)
                self.assertEqual(caught.exception.value, -4)

    def test_parameter_failure_prevents_loading(self):
        device = BiologicDevice("USB0", populate_info=False)
        with patch.object(device, "_validate_connection"), patch.object(
            ecl, "BL_DefineSglParameter", side_effect=[0, -4, 0]
        ) as define, patch.object(ecl, "BL_LoadTechnique") as load:
            with self.assertRaises(EcError):
                device.load_technique(
                    0, "cplimit", {"Current_step": [1e-9, 2e-9, 3e-9]}
                )
        self.assertEqual(define.call_count, 2)
        load.assert_not_called()

    def test_successful_parameter_definitions_preserve_values_and_indexes(self):
        for name, value, kind, raw in (
            ("BL_DefineBoolParameter", True, 1, 1),
            ("BL_DefineIntParameter", 7, 0, 7),
            ("BL_DefineSglParameter", -1.25e-9, 2,
             struct.unpack("<i", struct.pack("<f", -1.25e-9))[0]),
        ):
            def define(label, native_value, index, pointer):
                pointer._obj.ParamStr = label
                pointer._obj.ParamType = kind
                pointer._obj.ParamIndex = index.value
                pointer._obj.ParamVal = raw
                self.assertAlmostEqual(native_value.value, value)
                return 0

            with self.subTest(function=name), patch.object(ecl, name, side_effect=define):
                parameter = ecl.create_parameter("Test", value, index=2)
                self.assertEqual(parameter.ParamStr, b"Test")
                self.assertEqual(parameter.ParamIndex, 2)
                self.assertEqual(parameter.ParamType, kind)
                self.assertEqual(parameter.ParamVal, raw)

    def call_channels(self, operation, results, overall=0, asynchronous=False):
        names = {
            "firmware": ("BL_LoadFirmware", "init_channels"),
            "start": ("BL_StartChannels", "start_channels"),
            "stop": ("BL_StopChannels", "stop_channels"),
        }
        native_name, wrapper_name = names[operation]
        if asynchronous:
            native_name += "_async"
            wrapper_name += "_async"

        def native(identifier, active, returned, length, *args):
            self.assertEqual(list(active._obj), [1, 0, 1])
            self.assertEqual(length, 3)
            for channel, result in enumerate(results):
                returned._obj[channel] = result
            return overall

        mock = AsyncMock(side_effect=native) if asynchronous else MagicMock(side_effect=native)
        with patch.object(ecl, native_name, mock):
            result = getattr(ecl, wrapper_name)(77, [0, 2])
            return asyncio.run(result) if asynchronous else result

    def test_selected_channel_failure_is_reported(self):
        for operation in ("firmware", "start", "stop"):
            for asynchronous in (False, True):
                with self.subTest(operation=operation, asynchronous=asynchronous):
                    with self.assertRaises(EcError) as caught:
                        self.call_channels(operation, [0, 0, -103], asynchronous=asynchronous)
                    self.assertEqual(caught.exception.value, -103)
                    self.assertEqual(caught.exception.channel, 2)
                    self.assertIn("Channel 2:", str(caught.exception))

    def test_success_and_inactive_channel_results(self):
        for operation in ("firmware", "start", "stop"):
            for asynchronous in (False, True):
                with self.subTest(operation=operation, asynchronous=asynchronous):
                    result = self.call_channels(operation, [0, -103, 0], asynchronous=asynchronous)
                    if operation == "firmware":
                        self.assertEqual(list(result), [0, -103, 0])
                    else:
                        self.assertIsNone(result)

    def test_overall_errors_still_propagate(self):
        for operation in ("firmware", "start", "stop"):
            for asynchronous in (False, True):
                with self.subTest(operation=operation, asynchronous=asynchronous):
                    with self.assertRaises(EcError) as caught:
                        self.call_channels(operation, [-103, 0, -103], -4, asynchronous)
                    self.assertEqual(caught.exception.value, -4)

    def test_loaded_firmware_does_not_hide_another_channel_failure(self):
        for overall in (0, -9):
            for asynchronous in (False, True):
                with self.subTest(overall=overall, asynchronous=asynchronous):
                    with self.assertRaises(EcError) as caught:
                        self.call_channels("firmware", [-9, 0, -103], overall, asynchronous)
                    self.assertEqual(caught.exception.value, -103)
                    self.assertEqual(caught.exception.channel, 2)

    def test_already_loaded_channel_firmware_is_allowed(self):
        for asynchronous in (False, True):
            with self.subTest(asynchronous=asynchronous):
                result = self.call_channels("firmware", [-9, 0, -9], asynchronous=asynchronous)
                self.assertEqual(list(result), [-9, 0, -9])
                with self.assertRaises(EcError) as caught:
                    self.call_channels("firmware", [-9, 0, -9], -9, asynchronous)
                self.assertEqual(caught.exception.value, -9)

    def test_start_stop_do_not_allow_already_loaded_error(self):
        for operation in ("start", "stop"):
            for asynchronous in (False, True):
                with self.subTest(operation=operation, asynchronous=asynchronous):
                    with self.assertRaises(EcError) as caught:
                        self.call_channels(operation, [0, 0, -9], asynchronous=asynchronous)
                    self.assertEqual(caught.exception.value, -9)
                    self.assertEqual(caught.exception.channel, 2)


if __name__ == "__main__":
    unittest.main()
