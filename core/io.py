from pathlib import Path
import pandas as pd

OUT_DIR = Path(__file__).parent.parent / "data" / "allsvenskan_data"
SOLUTIONS_DIR = Path(__file__).parent.parent / "solutions"

def save_parquet(df: pd.DataFrame, filename: str, directory: Path = OUT_DIR, verbose: bool = True):
    directory.mkdir(exist_ok=True, parents=True)
    path = directory / filename
    df.to_parquet(path)
    if verbose:
        print(f"Saved {path}")


def load_parquet(filename: str, directory: Path = OUT_DIR, verbose: bool = False) -> pd.DataFrame:
    path = directory / filename
    df = pd.read_parquet(path)
    if verbose:
        print(f"Loaded {path}")
    return df


def save_solution(picks: pd.DataFrame, through_gw: int, chips: pd.DataFrame | None = None,) -> None:
    if chips is None:
        chips = pd.DataFrame({"gw": pd.Series(dtype="int64"), "chip": pd.Series(dtype="string")})

    save_parquet(picks, f"picks_through_{through_gw:02d}.parquet", SOLUTIONS_DIR)
    save_parquet(chips, f"chips_through_{through_gw:02d}.parquet", SOLUTIONS_DIR)


def load_solution(through_gw: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    picks = load_parquet(f"picks_through_{through_gw:02d}.parquet", SOLUTIONS_DIR)
    chips = load_parquet(f"chips_through_{through_gw:02d}.parquet", SOLUTIONS_DIR)
    return picks, chips
