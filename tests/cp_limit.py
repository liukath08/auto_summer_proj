import easy_biologic as ebl

import easy_biologic.base_programs as blp

device = ebl.BiologicDevice("USB0")

params = {

    0: {

        "currents": [1e-6],

        "durations": [5],

        "limits": [],

    }

}

prg = blp.CPLimit(device, params, channels=[0])

print("CPLimit object created successfully.")

print(prg)