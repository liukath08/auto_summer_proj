import logging

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl


logging.basicConfig(level=logging.DEBUG)

channels = [0, 1, 2, 3, 7]
by_channel = False

lower_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    -1.0,
)

upper_voltage_limit = ebp.configure_limit(
    ecl.LimitVariable.E,
    ecl.LimitComparison.GT,
    ecl.LimitLogic.OR,
    1.0,
)

params = {
    "currents": [0.001],
    "durations": [10],
    "limits": [lower_voltage_limit, upper_voltage_limit],
    "exit_condition": ecl.ExitCondition.NEXTSTEP
}

program = ebp.CPLimit(device, params, channels=[0])
program.run()

params = {
    "currents": [0, 1e-3] ,
    "durations": [2],
}

save_path = "data/cp-limit"
if not by_channel:
    save_path += ".csv"

bl = ebl.BiologicDevice("USB0")
prg = ebp.CPLimit(bl, params, channels=channels)

prg.run()
prg.save_data(save_path, by_channel=by_channel)
