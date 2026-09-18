# Sequence: CP -> CA -> OCV

import logging
from pathlib import Path

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl

if __package__:
    from . import gcpl_lib as gl
else:
    import gcpl_lib as gl


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

CSV_PATH = DATA_DIR / "081826_1150_GPCL_3C02_CETOGRND_.csv"
FIG_PATH = DATA_DIR / "081826_1150_GPCL_3C02_CETOGRND_.png"


# Each row configures the hardware parameters for the corresponding CP -> CA -> OCV group
#(p100, n1, n10,n100, u1, u10, u,100, m1, m10, m100, a1, KEEP, BOOSTER, AUTO)
#(v2_5, +-2.5V),(v5, +-5V),(v10, +-10V), (AUTO)
#(k50: 50kHz), (k1: 1kHz), (h5: 5Hz), (OFF)
HARDWARE_PARAMETERS = [
    {
        "CP": [
            ecl.IRange.n10,
            ecl.ERange.AUTO,
            ecl.Bandwidth.BW5,
        ],
        "CA": [
            ecl.IRange.AUTO,
            ecl.ERange.AUTO,
            ecl.Bandwidth.BW1,
        ],
        "OCV": [
            None,
            ecl.ERange.AUTO,
            ecl.Bandwidth.BW5,
        ],
    },
    {
        "CP": [
            ecl.IRange.n10,
            ecl.ERange.AUTO,
            ecl.Bandwidth.BW5,
        ],
        "CA": [
            ecl.IRange.AUTO,
            ecl.ERange.AUTO,
            ecl.Bandwidth.BW1,
        ],
        "OCV": [
            None,
            ecl.ERange.AUTO,
            ecl.Bandwidth.BW5,
        ],
    },
]

CHANNEL_CONFIGURATIONS = {
    0: {
        "connection": (
            ecl.ElectrodeConnection.CETOGRND
        ),
        "mode": ecl.ChannelMode.GROUNDED,
    },
}

#  Each row configures one CP -> CA pair:[CP applied current (A), CA applied voltage (V)].
SETPOINTS = [
    [-1.25e-9, -1.7],
    [1e-9, 1.0],
]

# [CP lower voltage limit (V), CA lower current limit (A)].
LOWER_LIMITS = [
    [-2.0, -2.0],
    [-2.0, -2.0],
]

# [CP upper voltage limit (V), CA upper current limit (A)].
UPPER_LIMITS = [
    [1.0, 2.0],
    [1.0, 2.0],
]

# Each row configures the corresponding CP -> CA -> OCV group: [CP duration (s), CA duration (s), OCV duration (s)].
DURATIONS = [
    [60.0, 30.0, 10.0],
    [120.0, 30.0, 10.0],
]



def main():
    device = ebl.BiologicDevice(BIOLOGIC_ADDRESS, populate_info=False)
    try:
        device.connect()
        sequence = gl.create_sequence(
            device, SETPOINTS, DURATIONS, LOWER_LIMITS,
            UPPER_LIMITS, HARDWARE_PARAMETERS, CHANNELS,
        )
        gcpl = ebp.GCPL(device, sequence, CHANNELS)
        gl.apply_channel_configurations(device, CHANNEL_CONFIGURATIONS)
        gcpl.run(read_interval=READ_INTERVAL)
    except BaseException:
        try:
            device.stop_channels(CHANNELS)
        except Exception:
            logging.exception("Failed to stop GCPL channels during cleanup.")
        raise
    finally:
        if device.is_connected():
            device.disconnect()

    dataframe = gl.save_gcpl_data(gcpl.rows, CSV_PATH)
    gl.plot_gcpl_data(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()
