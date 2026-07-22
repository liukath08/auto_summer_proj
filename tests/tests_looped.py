import csv
from pathlib import Path

import easy_biologic as ebl
import easy_biologic.base_programs as ebp


CHANNELS = [0]
NUMBER_OF_RUNS = 4
OUTPUT_FILE = Path("data/test-sequence-looped.csv")

device = ebl.BiologicDevice("USB0")


def create_programs():
    """Create a fresh set of programs for one complete test sequence."""
    return [
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


OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)

with OUTPUT_FILE.open("w", newline="") as output:
    writer = csv.writer(output)
    writer.writerow(
        [
            "run",
            "technique",
            "channel",
            "time",
            "voltage",
            "current",
            "power",
            "cycle",
        ]
    )

    for run_number in range(1, NUMBER_OF_RUNS + 1):
        print(f"Starting sequence {run_number} of {NUMBER_OF_RUNS}")

        for technique, program in create_programs():
            print(f"Sequence {run_number}: running {technique}")
            program.run()

            # Normalize OCV and CA data into the same CSV layout.
            for channel, channel_data in program.data.items():
                for datum in channel_data:
                    writer.writerow(
                        [
                            run_number,
                            technique,
                            channel,
                            datum.time,
                            datum.voltage,
                            getattr(datum, "current", ""),
                            getattr(datum, "power", ""),
                            getattr(datum, "cycle", ""),
                        ]
                    )

            output.flush()

        print(f"Finished sequence {run_number} of {NUMBER_OF_RUNS}")

print(f"Saved all four test sequences to {OUTPUT_FILE}")
