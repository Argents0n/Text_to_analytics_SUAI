"""Rule-based chart selection over a result DataFrame.

Vega-Lite (via Altair) is the target grammar: the mark is chosen from the shape
of the data — how many temporal / numeric / categorical columns the result has —
so rendering is deterministic and unit-testable without an LLM. Falls back to a
plain table when no chart fits.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import altair as alt
import pandas as pd
from pandas.api import types as ptypes

MAX_CATEGORIES = 30  # keep bar/pie readable; trim to top-N by value


@dataclass
class ChartChoice:
    kind: str  # "line" | "bar" | "scatter" | "hist" | "pie" | "table"
    chart: alt.Chart | None
    reason: str


def _roles(df: pd.DataFrame) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {"temporal": [], "numeric": [], "categorical": []}
    for col in df.columns:
        s = df[col]
        if ptypes.is_datetime64_any_dtype(s):
            out["temporal"].append(col)
        elif ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s):
            out["numeric"].append(col)
        else:
            out["categorical"].append(col)
    return out


def _enc_type(df: pd.DataFrame, col: str) -> str:
    s = df[col]
    if ptypes.is_datetime64_any_dtype(s):
        return "temporal"
    if ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s):
        return "quantitative"
    return "nominal"


def choose_chart(df: pd.DataFrame) -> ChartChoice:
    if df is None or df.empty:
        return ChartChoice("table", None, "Пустой результат.")
    if df.shape == (1, 1):
        return ChartChoice("table", None, "Одно значение — график не нужен.")

    r = _roles(df)
    t, n, c = r["temporal"], r["numeric"], r["categorical"]

    # time series: temporal x + numeric y (+ optional low-cardinality color)
    if t and n:
        x, y = t[0], n[0]
        color = c[0] if c and df[c[0]].nunique() <= 8 else None
        enc: dict[str, Any] = {"x": alt.X(f"{x}:T", title=x), "y": alt.Y(f"{y}:Q", title=y)}
        if color:
            enc["color"] = alt.Color(f"{color}:N", title=color)
        return ChartChoice("line", alt.Chart(df).mark_line(point=True).encode(**enc),
                           f"Временной ряд: {y} по {x}.")

    # category vs measure -> bar (top-N)
    if c and n:
        cat, y = c[0], n[0]
        data = df
        if df[cat].nunique() > MAX_CATEGORIES:
            data = df.nlargest(MAX_CATEGORIES, y)
        return ChartChoice(
            "bar",
            alt.Chart(data).mark_bar().encode(
                x=alt.X(f"{y}:Q", title=y),
                y=alt.Y(f"{cat}:N", sort="-x", title=cat),
            ),
            f"Сравнение {y} по «{cat}».",
        )

    # two numerics -> scatter
    if len(n) >= 2:
        x, y = n[0], n[1]
        return ChartChoice(
            "scatter",
            alt.Chart(df).mark_circle(opacity=0.6).encode(
                x=alt.X(f"{x}:Q", title=x), y=alt.Y(f"{y}:Q", title=y)
            ),
            f"Связь {x} и {y}.",
        )

    # single numeric -> histogram
    if len(n) == 1 and not c and not t:
        y = n[0]
        return ChartChoice(
            "hist",
            alt.Chart(df).mark_bar().encode(
                x=alt.X(f"{y}:Q", bin=alt.Bin(maxbins=30), title=y),
                y=alt.Y("count()", title="частота"),
            ),
            f"Распределение {y}.",
        )

    return ChartChoice("table", None, "Форма данных не ложится на стандартный график.")
