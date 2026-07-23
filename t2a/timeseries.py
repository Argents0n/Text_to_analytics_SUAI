"""Time-series analysis — the analytical half of the user's taxi-orders project.

Resample to a frequency, decompose into trend/seasonal/residual, rolling stats,
autocorrelation, and a light forecast (seasonal-naive or Holt-Winters). The
heavy ML forecasting from the course is intentionally out of scope; these are
the classical, light-compute pieces.
"""

from __future__ import annotations

import altair as alt
import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import ExponentialSmoothing
from statsmodels.tsa.seasonal import seasonal_decompose
from statsmodels.tsa.stattools import acf

FREQS = {"час": "h", "день": "D", "неделя": "W", "месяц": "MS"}
_DEFAULT_PERIOD = {"h": 24, "D": 7, "W": 52, "MS": 12}


def resample_series(df: pd.DataFrame, date_col: str, value_col: str, freq: str = "D", agg: str = "sum") -> pd.Series:
    s = df[[date_col, value_col]].copy()
    s[date_col] = pd.to_datetime(s[date_col], errors="coerce")
    s = s.dropna(subset=[date_col])
    ser = s.set_index(date_col)[value_col].resample(freq).agg(agg)
    return ser


def default_period(freq: str) -> int:
    return _DEFAULT_PERIOD.get(freq, 12)


def line(ser: pd.Series, title: str) -> alt.Chart:
    d = ser.reset_index()
    d.columns = ["date", "value"]
    return alt.Chart(d).mark_line().encode(
        x=alt.X("date:T", title=None), y=alt.Y("value:Q", title=title)
    ).properties(height=180)


def decompose(ser: pd.Series, period: int, model: str = "additive") -> tuple[pd.DataFrame, alt.Chart]:
    ser = ser.interpolate().dropna()
    res = seasonal_decompose(ser, model=model, period=period)
    parts = pd.DataFrame({
        "date": ser.index,
        "observed": res.observed.to_numpy(),
        "trend": res.trend.to_numpy(),
        "seasonal": res.seasonal.to_numpy(),
        "resid": res.resid.to_numpy(),
    })
    long = parts.melt("date", var_name="component", value_name="value")
    order = ["observed", "trend", "seasonal", "resid"]
    chart = alt.Chart(long).mark_line().encode(
        x=alt.X("date:T", title=None),
        y=alt.Y("value:Q", title=None),
        facet=alt.Facet("component:N", columns=1, sort=order, title=None),
    ).resolve_scale(y="independent").properties(height=110, width="container")
    return parts, chart


def rolling(ser: pd.Series, window: int) -> alt.Chart:
    d = pd.DataFrame({
        "date": ser.index,
        "value": ser.to_numpy(),
        "rolling_mean": ser.rolling(window).mean().to_numpy(),
        "rolling_std": ser.rolling(window).std().to_numpy(),
    })
    long = d.melt("date", var_name="series", value_name="value")
    return alt.Chart(long).mark_line().encode(
        x=alt.X("date:T", title=None), y=alt.Y("value:Q", title=None),
        color=alt.Color("series:N", title=None),
    ).properties(height=220)


def acf_chart(ser: pd.Series, nlags: int = 40) -> alt.Chart:
    ser = ser.interpolate().dropna()
    nlags = min(nlags, len(ser) // 2 - 1)
    values = acf(ser, nlags=nlags, fft=True)
    d = pd.DataFrame({"lag": range(len(values)), "acf": values})
    conf = 1.96 / np.sqrt(len(ser))
    bars = alt.Chart(d).mark_bar().encode(
        x=alt.X("lag:O", title="лаг"), y=alt.Y("acf:Q", title="ACF"),
    )
    band = alt.Chart(pd.DataFrame({"y": [conf, -conf]})).mark_rule(
        strokeDash=[4, 4], color="red"
    ).encode(y="y:Q")
    return (bars + band).properties(height=220)


def forecast(ser: pd.Series, periods: int, method: str = "seasonal_naive", period: int = 7) -> tuple[pd.Series, alt.Chart]:
    ser = ser.interpolate().dropna()
    idx = pd.date_range(ser.index[-1], periods=periods + 1, freq=ser.index.freq or pd.infer_freq(ser.index))[1:]
    if method == "holt-winters":
        model = ExponentialSmoothing(ser, trend="add", seasonal="add", seasonal_periods=period).fit()
        pred = pd.Series(model.forecast(periods).to_numpy(), index=idx)
    else:  # seasonal-naive: repeat the last full season
        last = ser.to_numpy()[-period:]
        pred = pd.Series([last[i % period] for i in range(periods)], index=idx)

    hist = pd.DataFrame({"date": ser.index, "value": ser.to_numpy(), "kind": "факт"})
    fc = pd.DataFrame({"date": pred.index, "value": pred.to_numpy(), "kind": "прогноз"})
    chart = alt.Chart(pd.concat([hist, fc])).mark_line().encode(
        x=alt.X("date:T", title=None), y=alt.Y("value:Q", title=None),
        color=alt.Color("kind:N", title=None),
    ).properties(height=240)
    return pred, chart
