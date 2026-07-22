import logging

import easy_biologic as ebl
import easy_biologic.base_programs as ebp


logging.basicConfig(level=logging.DEBUG)

channels = [0, 1, 2, 3, 7]
by_channel = False
params = {
    "currents": [0, 1e-3] * 2,
    "durations": [2] * 4,
}

save_path = "data/cp-limit"
if not by_channel:
    save_path += ".csv"

bl = ebl.BiologicDevice("USB0")
prg = ebp.CPLimit(bl, params, channels=channels)

prg.run()
prg.save_data(save_path, by_channel=by_channel)
