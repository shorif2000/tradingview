"""
Repo-relative paths and dataset loading.

Why this module exists: the analysis scripts were originally written in a sandbox
where everything lived in one flat directory at /home/claude, so they hardcoded
absolute paths and read pre-pickled DataFrames that are gitignored. In a fresh
checkout those paths do not exist and the scripts fail before doing any work.

Everything here resolves relative to the repository root, so a script works from
any working directory, and `dataset()` builds the DataFrames from the CSVs in
data/ instead of expecting pickles to already be there.
"""
from __future__ import annotations
import os
from pathlib import Path

import pandas as pd

# backtester/paths.py -> repo root is one level up
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PINE = ROOT / "pine"
VARIANTS = PINE / "variants"

# Reports are build artefacts, not source. Override with XAU_REPORT_DIR if you
# want them somewhere else (CI, a scratch disk, /tmp).
REPORTS = Path(os.environ.get("XAU_REPORT_DIR", ROOT / "reports"))

# Pickles are a CACHE, never a source of truth. They are gitignored because the
# pickle format is tied to the pandas version that wrote it; delete them freely.
CACHE = Path(os.environ.get("XAU_CACHE_DIR", ROOT / ".cache"))


def report_dir() -> Path:
    """Create the report directory on demand and return it."""
    REPORTS.mkdir(parents=True, exist_ok=True)
    return REPORTS


# ── datasets ────────────────────────────────────────────────────────────────
# name -> (csv filename, timezone of the file's timestamps, resample to 5m?)
#
# The timezone is not cosmetic. MT5 exports are in broker server time (Vantage
# is UTC+2 in winter); TradingView exports are UTC. Getting it wrong shifts every
# session filter by hours without raising anything. `Etc/GMT-2` means UTC+2 - the
# sign inversion is POSIX convention, not a typo.
#
# The resample flag is load-bearing for "m1". load_ohlc resamples to 5m by
# default, and the M1 file resampled to 5m is just a second copy of the M5 file -
# which would silently disable the intrabar stop-vs-target ordering the whole
# backtest depends on. A 2R system's result is decided by which of SL and TP is
# touched FIRST inside the bar, and only 1-minute data can answer that.
DATASETS = {
    "m5":        ("XAUUSD_M5_jan2026_mt5.csv",              "Etc/GMT-2", True),
    "m1":        ("XAUUSD_M1_jan2026_mt5.csv",              "Etc/GMT-2", False),
    "m5_summer": ("XAUUSD_M5_jun-aug2026_tradingview.csv",  "UTC",       True),
    "h1":        ("XAUUSD_H1_tradingview.csv",              "UTC",       False),
    "h4":        ("XAUUSD_H4_tradingview.csv",              "UTC",       False),
}

# Expected modal bar spacing, in minutes. Checked on every load so a loader
# change can never quietly hand back the wrong resolution again.
EXPECTED_STEP_MIN = {"m5": 5, "m1": 1, "m5_summer": 5, "h1": 60, "h4": 240}


def _check_step(name: str, df: pd.DataFrame) -> None:
    """Fail loudly if a dataset came back at the wrong bar resolution."""
    want = EXPECTED_STEP_MIN.get(name)
    if want is None or len(df) < 3:
        return
    got = df.index.to_series().diff().mode()[0].total_seconds() / 60.0
    if abs(got - want) > 1e-6:
        raise ValueError(
            f"dataset({name!r}) returned {got:g}-minute bars, expected {want}. "
            f"Check the resample flag in DATASETS - an M1 file silently "
            f"resampled to 5m disables intrabar stop/target ordering.")


def dataset(name: str, use_cache: bool = True) -> pd.DataFrame:
    """
    Load a named dataset from data/, caching the parsed frame under .cache/.

    Falls through to a fresh parse whenever the cache is missing or unreadable -
    a stale pickle from another pandas version should cost a few seconds of
    re-parsing, never a crash.
    """
    if name not in DATASETS:
        raise KeyError(f"unknown dataset {name!r}; known: {', '.join(DATASETS)}")

    fname, tz, resample = DATASETS[name]
    csv = DATA / fname
    if not csv.exists():
        raise FileNotFoundError(
            f"{csv} is missing. The repo ships the samples the results were "
            f"measured on; if you have removed them, pass your own CSV to "
            f"run_backtest.py --csv instead.")

    pkl = CACHE / f"{name}.pkl"
    if use_cache and pkl.exists():
        try:
            cached = pd.read_pickle(pkl)
            _check_step(name, cached)
            return cached
        except Exception:
            pass  # stale, wrong resolution, or another pandas - just rebuild

    from data_io import load_ohlc
    df = load_ohlc(str(csv), assume_tz=tz, resample_5m=resample)
    _check_step(name, df)

    if use_cache:
        try:
            CACHE.mkdir(parents=True, exist_ok=True)
            df.to_pickle(pkl)
        except Exception:
            pass  # caching is an optimisation; never let it fail a run

    return df
