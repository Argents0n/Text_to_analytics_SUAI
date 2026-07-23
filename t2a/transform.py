"""Feature engineering — computed columns, mirroring the derived columns the user
built by hand (price per m², date parts, floor-type binning, m→km).

Each function returns a copy of the DataFrame with one new column, so the UI can
chain transforms without mutating session state.
"""

from __future__ import annotations

import pandas as pd

DATE_PARTS = ("year", "month", "day", "weekday", "hour", "date")
OPS = ("+", "-", "*", "/")


def add_arithmetic(df: pd.DataFrame, a: str, op: str, b: str, name: str) -> pd.DataFrame:
    out = df.copy()
    x, y = pd.to_numeric(out[a], errors="coerce"), pd.to_numeric(out[b], errors="coerce")
    out[name] = {"+": x + y, "-": x - y, "*": x * y, "/": x / y}[op].round(4)
    return out


def add_datepart(df: pd.DataFrame, col: str, part: str, name: str) -> pd.DataFrame:
    out = df.copy()
    dt = pd.to_datetime(out[col], errors="coerce")
    out[name] = {
        "year": dt.dt.year, "month": dt.dt.month, "day": dt.dt.day,
        "weekday": dt.dt.weekday, "hour": dt.dt.hour, "date": dt.dt.date,
    }[part]
    return out


def add_bin(df: pd.DataFrame, col: str, bins: int, name: str, quantile: bool = False) -> pd.DataFrame:
    out = df.copy()
    x = pd.to_numeric(out[col], errors="coerce")
    out[name] = (pd.qcut(x, q=bins, duplicates="drop") if quantile else pd.cut(x, bins=bins)).astype(str)
    return out


def convert_unit(df: pd.DataFrame, col: str, factor: float, name: str) -> pd.DataFrame:
    out = df.copy()
    out[name] = (pd.to_numeric(out[col], errors="coerce") * factor).round(4)
    return out
