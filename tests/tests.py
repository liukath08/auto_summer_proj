import csv
from pathlib import Path

import easy_biologic as ebl
import easy_biologic.base_programs as ebp


CHANNELS = [0]
OUTPUT_FILE = Path("data/ocv-ca-ca-ocv.csv")

device = ebl.BiologicDevice("USB0")

programs = [
    (
        "OCV 1",
        ebp.OCV(
            device,
            {"time": 5, "time_interval": 1},
            channels=CHANNELS,
        ),
    ),
    (
        "CA 1",
        ebp.CA(
            device,
            {"voltages": [1], "durations": [10], "time_interval": 1},
            channels=CHANNELS,
        ),
    ),
    (
        "CA 2",
        ebp.CA(
            device,
            {"voltages": [2], "durations": [10], "time_interval": 1},
            channels=CHANNELS,
        ),
    ),
    (
        "CA 3",
        ebp.CA(
            device,
            {"voltages": [-2], "durations": [10], "time_interval": 1},
            channels=CHANNELS,
        ),
    ),
    (
                    "CA 4",
                    ebp.CA(
                        device,
                        {"voltages": [1], "durations": [10], "time_interval": 1},
                        channels=CHANNELS,
                    ),
                ),
    (
        "OCV 2",
        ebp.OCV(
            device,
            {"time": 5, "time_interval": 1},
            channels=CHANNELS,
        ),
    ),
]

# Run the techniques in order and retain each program's results until all four
# have completed.
for _, program in programs:
    program.run()

# OCV and CA expose different data columns, so normalize both into one table
# instead of appending incompatible CSV layouts.
OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT_FILE.open("w", newline="") as output:
    writer = csv.writer(output)
    writer.writerow(
        ["technique", "channel", "time", "voltage", "current", "power", "cycle"]
    )

    for technique, program in programs:
        for channel, channel_data in program.data.items():
            for datum in channel_data:
                writer.writerow(
                    [
                        technique,
                        channel,
                        datum.time,
                        datum.voltage,
                        getattr(datum, "current", ""),
                        getattr(datum, "power", ""),
                        getattr(datum, "cycle", ""),
                    ]
                )

print(f"Saved all technique data to {OUTPUT_FILE}")
