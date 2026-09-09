"""
The standard sample set and the bootstrap, in one place.

Six analysis scripts each carried their own copy of this preamble: two
`load_ohlc()` calls with the filenames and timezones written out longhand, a
resample lambda, and a SAMPLES dict. Besides being six copies of one thing,
those hardcoded relative paths only worked when the script was run from the
repository root, and they bypassed the bar-resolution check in
`paths.dataset()` - the check that exists because an M1 file silently
resampled to 5m disables the intrabar stop-vs-target ordering the results
depend on.

Anything that needs the two measured periods should import from here.
"""
from __future__ import annotations

import numpy as np

from paths import dataset

# Trading timeframe in minutes, for the scripts that need to configure an
# engine per sample rather than just read bars.
TF_MINUTES = {"2M Jan": 2, "3M Jan": 3, "5M Jan": 5, "5M Jun-Aug": 5}


def resample(m1, rule):
    """M1 bars up to a coarser timeframe. Left-labelled, left-closed."""
    o = m1.resample(rule, label="left", closed="left").agg(
        {"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"})
    return o.dropna()


def samples():
    """
    `{name: (trading bars, M1 bars)}` for the two periods every claim is held to.

    The M1 frame is the second element because intrabar resolution needs it to
    decide which of stop and target was touched first. It is **None** for the
    summer sample, which has no M1 export - callers that need intrabar ordering
    have to handle that rather than assume it away.
    """
    m1 = dataset("m1")
    return {"2M Jan": (resample(m1, "2min"), m1),
            "3M Jan": (resample(m1, "3min"), m1),
            "5M Jan": (resample(m1, "5min"), m1),
            "5M Jun-Aug": (dataset("m5_summer"), None)}


def boot(r, n=10000, seed=0):
    """Percentile bootstrap of the mean. Returns `(lo, hi, P(mean <= 0))`."""
    r = np.asarray(r, float)
    if len(r) < 5:
        return np.nan, np.nan, np.nan
    m = np.random.default_rng(seed).choice(r, (n, len(r)), replace=True).mean(1)
    return np.percentile(m, 2.5), np.percentile(m, 97.5), (m <= 0).mean()
