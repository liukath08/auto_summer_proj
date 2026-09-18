"""Run galvanostatic cycling using the shared parameters."""

from pathlib import Path

if __package__:
    from . import technique_library as tl
else:
    import technique_library as tl


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "GCPL"
CSV_PATH = DATA_DIR / "081826_1150_GPCL_3C02_CETOGRND_.csv"
FIG_PATH = DATA_DIR / "081826_1150_GPCL_3C02_CETOGRND_.png"


def main():
    program = tl.run_gcpl()
    dataframe = tl.save_gcpl_data(program.rows, CSV_PATH)
    tl.plot_gcpl_data(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()
