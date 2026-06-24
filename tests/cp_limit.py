import easy_biologic as ebl
from easy_biologic.base_programs import CPLimit

print("Successfully imported CPLimit")

device = ebl.BiologicDevice("USB0")

params = {
    1: {
        "currents": [1e-6],
        "durations": [5],
        "limits": [],
    }
}

program = CPLimit(device, params)

print("Successfully created CPLimit object")
print(program)