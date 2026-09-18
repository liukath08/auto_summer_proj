"""Run open-circuit voltage using the shared parameters."""

from pathlib import Path

if __package__:
    from . import technique_library as tl
else:
    import technique_library as tl


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "OCV"
CSV_PATH = DATA_DIR / "ocv_results.csv"
FIG_PATH = DATA_DIR / "ocv_results.png"


def main():
    program = tl.run_ocv()
    dataframe = tl.save_ocv_data(program, CSV_PATH)
    tl.plot_ocv(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()
