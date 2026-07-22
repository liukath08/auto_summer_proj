import json
import logging
from pathlib import Path

import easy_biologic as ebl
import easy_biologic.base_programs as ebp
from easy_biologic.lib import ec_lib as ecl


logging.basicConfig(level=logging.DEBUG)

CHANNELS = [0]
SAVE_PATH = Path("data/ca-limit2.csv")


def parse_parameters(line):
    """Parse all CALimit parameters from one line of JSON."""
    try:
        params = json.loads(line)
    except json.JSONDecodeError as err:
        raise ValueError(f"Invalid JSON input: {err.msg}") from err

    if not isinstance(params, dict):
        raise ValueError("The input must be a JSON object.")

    missing = [name for name in ("voltages", "durations") if name not in params]
    if missing:
        raise ValueError("Missing required parameter(s): " + ", ".join(missing))

    if len(params["voltages"]) != len(params["durations"]):
        raise ValueError("voltages and durations must have the same length.")

    if "current_range" in params and isinstance(params["current_range"], str):
        try:
            params["current_range"] = ecl.IRange[params["current_range"]]
        except KeyError as err:
            raise ValueError(
                f"Unknown current_range: {params['current_range']}"
            ) from err

    if "exit_condition" in params and isinstance(params["exit_condition"], str):
        try:
            params["exit_condition"] = ecl.ExitCondition[
                params["exit_condition"].upper()
            ]
        except KeyError as err:
            raise ValueError(
                f"Unknown exit_condition: {params['exit_condition']}"
            ) from err

    limits = []
    for limit in params.get("limits", []):
        if not isinstance(limit, dict):
            raise ValueError("Each limit must be a JSON object.")

        try:
            variable = ecl.LimitVariable[str(limit["variable"]).upper()]
            comparison = ecl.LimitComparison[str(limit["comparison"]).upper()]
            logic = ecl.LimitLogic[str(limit.get("logic", "OR")).upper()]
            value = float(limit["value"])
        except KeyError as err:
            raise ValueError(f"Invalid or missing limit field: {err}") from err

        limits.append(ebp.configure_limit(variable, comparison, logic, value))

    if len(limits) > 3:
        raise ValueError("CALimit supports at most three limits.")

    params["limits"] = limits
    return params


print("Enter all CALimit parameters on one line as JSON.")
print(
    'Example: {"voltages":[0,1],"durations":[2,2],'
    '"time_interval":1,"current_interval":0.001,'
    '"limits":[{"variable":"I","comparison":"GT",'
    '"logic":"OR","value":0.001}],"exit_condition":"STOP"}'
)

params = parse_parameters(input("CALimit parameters: "))

SAVE_PATH.parent.mkdir(parents=True, exist_ok=True)
device = ebl.BiologicDevice("USB0")
program = ebp.CALimit(device, params, channels=CHANNELS)

program.run()
program.save_data(str(SAVE_PATH), by_channel=False)

print(f"Saved CALimit data to {SAVE_PATH}")
