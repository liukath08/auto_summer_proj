"""Run limit-controlled chronopotentiometry using shared parameters."""

from pathlib import Path

if __package__:
    from . import technique_library as tl
else:
    import technique_library as tl


DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "CP_LIMIT"
CSV_PATH = DATA_DIR / "080626_1319CP_-1nA_1C17_CETOGRND_.csv"
FIG_PATH = DATA_DIR / "080626_1319CP_-1nA_1C17_CETOGRND_.png"


def main():
    program = tl.run_cp_limit()
    dataframe = tl.save_cp_limit_data(program, CSV_PATH)
    tl.plot_cp_limit(dataframe, FIG_PATH)


if __name__ == "__main__":
    main()
