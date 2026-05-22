"""Loader for the Environment Canada hourly weather CSVs.

Handles the column renames, datetime parsing, hour extraction, and missing-value
drop so producer.py and the training notebook share one source of truth.
"""
from pathlib import Path
from typing import Iterable

import pandas as pd

# Source column -> internal short name.
# Wind Spd (km/h) is excluded: Toronto City station 6158355 does not report wind.
COL_MAP = {
    "Temp (°C)": "temp",
    "Dew Point Temp (°C)": "dew_point",
    "Rel Hum (%)": "humidity",
    "Stn Press (kPa)": "pressure",
}
FEATURE_ORDER = ["temp", "dew_point", "humidity", "pressure", "hour"]
DATA_DIR = Path(__file__).resolve().parents[1] / "data"
CSV_GLOB = "en_climate_hourly_*.csv"


def _read_one(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    df = df.rename(columns=COL_MAP)
    df["ts"] = pd.to_datetime(df["Date/Time (LST)"])
    df["hour"] = df["ts"].dt.hour
    keep = ["ts", "hour", *COL_MAP.values()]
    # Coerce numeric columns; Environment Canada uses blank strings for missing values.
    for col in COL_MAP.values():
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df[keep]


def load_files(paths: Iterable[Path]) -> pd.DataFrame:
    """Concatenate the given CSVs, sort by timestamp, drop rows with missing features."""
    frames = [_read_one(p) for p in paths]
    df = pd.concat(frames, ignore_index=True)
    df = df.sort_values("ts").drop_duplicates(subset="ts").reset_index(drop=True)
    df = df.dropna(subset=list(COL_MAP.values())).reset_index(drop=True)
    return df


def load_all(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load every monthly CSV in `data/`."""
    paths = sorted(data_dir.glob(CSV_GLOB))
    if not paths:
        raise FileNotFoundError(f"No CSVs matching {CSV_GLOB} found in {data_dir}")
    return load_files(paths)


def load_latest(data_dir: Path = DATA_DIR) -> pd.DataFrame:
    """Load only the most recent monthly CSV (used by the producer for demo replay)."""
    paths = sorted(data_dir.glob(CSV_GLOB))
    if not paths:
        raise FileNotFoundError(f"No CSVs matching {CSV_GLOB} found in {data_dir}")
    return load_files([paths[-1]])
