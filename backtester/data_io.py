"""
Flexible OHLC loader — accepts the formats you can actually export.

Handles:
  * TradingView  "Export chart data"      time,open,high,low,close,Volume
  * MT5          Symbols > Bars > Export  <DATE>\t<TIME>\t<OPEN>...
  * MT4          History Center export    2026.02.03,07:00,3300.1,...
  * Generic CSV with any reasonable column naming
Resamples to 5 minutes if the source is finer (e.g. 1-minute data).
"""
from __future__ import annotations
import io
import re
import numpy as np
import pandas as pd

_ALIASES = {
    "time": "time", "date": "time", "datetime": "time", "timestamp": "time",
    "<date>": "date_part", "<time>": "time_part",
    "open": "open", "<open>": "open", "o": "open",
    "high": "high", "<high>": "high", "h": "high",
    "low": "low", "<low>": "low", "l": "low",
    "close": "close", "<close>": "close", "c": "close", "price": "close",
    "volume": "volume", "<vol>": "volume", "<tickvol>": "volume", "vol": "volume",
    "<spread>": "spread", "spread": "spread",
}


def _preclean(path: str) -> str:
    """
    Some exports are scraped chart tables rather than broker files: tabs mixed
    into a comma-separated header, thousands separators inside quoted numbers,
    reverse chronological order and a null glyph. Normalise those to plain CSV.
    """
    with open(path, "r", errors="replace") as f:
        txt = f.read()
    first = txt.split("\n", 1)[0]
    if "\t" in first and "," in first:
        txt = txt.replace("\t", "")
        txt = txt.replace("\u2205", "")                 # null glyph
        txt = txt.replace("\u2212", "-")                # unicode minus
        out = path + ".clean.csv"
        with open(out, "w") as f:
            f.write(txt)
        return out
    return path


def _sniff(path: str) -> str:
    with open(path, "r", errors="replace") as f:
        head = f.read(4096)
    if "\t" in head.split("\n")[0]:
        return "\t"
    if head.count(";") > head.count(","):
        return ";"
    return ","


def load_ohlc(path: str, tz: str = "UTC", assume_tz: str | None = None,
               resample_5m: bool = True) -> pd.DataFrame:
    """
    Load an OHLC file into a tz-aware 5-minute DataFrame [open, high, low, close, volume].

    assume_tz : timezone the file's timestamps are stated in.
                MT4/MT5 exports are in BROKER SERVER time (Vantage = UTC+2/+3,
                i.e. 'Etc/GMT-2' / 'Etc/GMT-3'). TradingView exports are UTC.
                Get this wrong and the session filter shifts by hours.
    """
    path = _preclean(path)
    sep = _sniff(path)
    raw = pd.read_csv(path, sep=sep, engine="python")

    # Scraped chart tables often carry more data columns than header names (extra
    # unnamed indicator series). pandas silently turns the surplus into an index,
    # so re-read positionally: col0 = timestamp, cols 1-4 = O/H/L/C.
    with open(path, "r", errors="replace") as _f:
        _head = [next(_f) for _ in range(2)]
    if len(_head[1].split(sep)) > len(_head[0].split(sep)):
        raw = pd.read_csv(path, sep=sep, engine="python", header=None, skiprows=1)
        keep = ["time", "open", "high", "low", "close"]
        raw = raw.iloc[:, :5]
        raw.columns = keep

    # headerless MT4 export?
    if not any(str(c).strip().lower().strip("<>") in
               ("time", "date", "datetime", "timestamp", "open", "o") for c in raw.columns):
        raw = pd.read_csv(path, sep=sep, engine="python", header=None)
        ncol = raw.shape[1]
        names = ["date_part", "time_part", "open", "high", "low", "close", "volume"][:ncol]
        raw.columns = names + [f"x{i}" for i in range(ncol - len(names))]
    else:
        raw.columns = [_ALIASES.get(str(c).strip().lower(), str(c).strip().lower())
                       for c in raw.columns]
        raw = raw.loc[:, ~raw.columns.duplicated(keep="first")]

    df = pd.DataFrame()
    if "date_part" in raw.columns and "time_part" in raw.columns:
        ts = raw["date_part"].astype(str).str.replace(".", "-", regex=False) + " " + raw["time_part"].astype(str)
        df["time"] = pd.to_datetime(ts, errors="coerce", format="mixed")
    elif "time" in raw.columns:
        col = raw["time"]
        if pd.api.types.is_numeric_dtype(col):
            unit = "s" if col.max() < 1e11 else "ms"
            df["time"] = pd.to_datetime(col, unit=unit, utc=True)
        else:
            cleaned = (col.astype(str)
                          .str.replace(r"^[A-Za-z]{3}\s+", "", regex=True)   # drop weekday name
                          .str.replace("'", "", regex=False)
                          .str.replace(r"\s+", " ", regex=True)
                          .str.strip())
            df["time"] = pd.to_datetime(cleaned, errors="coerce", format="%d %b %y %H:%M")
            if df["time"].isna().mean() > 0.5:
                df["time"] = pd.to_datetime(col.astype(str).str.replace(".", "-", regex=False),
                                            errors="coerce", format="mixed", utc=False)
    else:
        raise ValueError(f"No recognisable time column in {path}. Columns: {list(raw.columns)}")

    for c in ("open", "high", "low", "close"):
        if c not in raw.columns:
            raise ValueError(f"Missing '{c}' column in {path}. Columns: {list(raw.columns)}")
        df[c] = pd.to_numeric(
            raw[c].astype(str).str.replace(",", "", regex=False).str.strip(), errors="coerce")
    df["volume"] = pd.to_numeric(raw.get("volume", pd.Series(0, index=raw.index)), errors="coerce").fillna(0.0)
    if "spread" in raw.columns:
        # MT5 ships spread in POINTS; for a 2-decimal gold symbol 1 point = 0.01 USD.
        df["spread"] = pd.to_numeric(raw["spread"], errors="coerce").fillna(0.0) * 0.01

    df = df.dropna(subset=["time", "open", "high", "low", "close"]).sort_values("time")
    df = df.set_index("time")

    if df.index.tz is None:
        src_tz = assume_tz or "UTC"
        df.index = df.index.tz_localize(src_tz, ambiguous="NaT", nonexistent="shift_forward")
        df = df[~df.index.isna()]
    df.index = df.index.tz_convert("UTC")
    df = df[~df.index.duplicated(keep="last")]

    # sanity: OHLC must be internally consistent
    bad = (df.high < df.low) | (df.high < df.open) | (df.high < df.close) | \
          (df.low > df.open) | (df.low > df.close)
    if bad.any():
        df = df[~bad]

    # resample up to 5m if finer
    step = df.index.to_series().diff().dt.total_seconds().median()
    if resample_5m and step and step < 290:
        agg = {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}
        if "spread" in df.columns:
            agg["spread"] = "mean"
        df = df.resample("5min").agg(agg).dropna()
    return df


def describe(df: pd.DataFrame) -> str:
    step = df.index.to_series().diff().dt.total_seconds().median()
    return (f"{len(df):,} bars | {df.index[0]} -> {df.index[-1]} | "
            f"median step {step:.0f}s | price {df.close.min():.2f}-{df.close.max():.2f}")
