"""Manual, configurable chart builder — the 'dynamic' half of the tool.

The user picks mark type, x/y/color and an aggregation; this assembles an
interactive Altair spec (pan/zoom + tooltips). Kept separate from the rule-based
auto-selection in ``charts.py``: that one guesses, this one obeys.
"""

from __future__ import annotations

import altair as alt
import pandas as pd
from pandas.api import types as ptypes

KINDS = ("bar", "line", "area", "scatter", "hist", "box", "pie")
AGGS = ("none", "sum", "mean", "median", "count", "min", "max")
_ZOOMABLE = {"line", "area", "scatter"}


def field_type(df: pd.DataFrame, col: str) -> str:
    s = df[col]
    if ptypes.is_datetime64_any_dtype(s):
        return "temporal"
    if ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s):
        return "quantitative"
    return "nominal"


def _y(col: str, agg: str) -> alt.Y:
    if agg == "count":
        return alt.Y("count()", title="количество")
    if agg == "none":
        return alt.Y(f"{col}:Q", title=col)
    return alt.Y(f"{col}:Q", aggregate=agg, title=f"{agg}({col})")


def build_custom(
    df: pd.DataFrame,
    kind: str,
    x: str | None = None,
    y: str | None = None,
    color: str | None = None,
    agg: str = "sum",
    interactive: bool = True,
) -> alt.Chart:
    if kind not in KINDS:
        raise ValueError(f"kind ∈ {KINDS}")

    # raw-point marks embed every row — sample for large tables (aggregated marks
    # keep the full data so sums stay correct; Altair's row cap is lifted globally)
    if kind in ("scatter", "hist", "box") and len(df) > 5000:
        df = df.sample(5000, random_state=0)

    tooltip = [c for c in (x, y, color) if c]
    color_enc = alt.Color(f"{color}:{_short(field_type(df, color))}", title=color) if color else alt.Undefined

    if kind == "hist":
        if not x:
            raise ValueError("Для гистограммы нужна колонка X (числовая).")
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X(f"{x}:Q", bin=alt.Bin(maxbins=30), title=x),
            y=alt.Y("count()", title="частота"),
            color=color_enc,
        )
    elif kind == "box":
        if not (x and y):
            raise ValueError("Boxplot: X (группа) и Y (число).")
        chart = alt.Chart(df).mark_boxplot().encode(
            x=alt.X(f"{x}:N", title=x), y=alt.Y(f"{y}:Q", title=y), color=color_enc,
        )
    elif kind == "pie":
        if not (x and y):
            raise ValueError("Pie: X (категория) и Y (значение).")
        chart = alt.Chart(df).mark_arc().encode(
            theta=_y(y, agg), color=alt.Color(f"{x}:N", title=x),
            tooltip=tooltip,
        )
    elif kind == "scatter":
        if not (x and y):
            raise ValueError("Scatter: X и Y (числовые).")
        chart = alt.Chart(df).mark_circle(opacity=0.6).encode(
            x=alt.X(f"{x}:Q", title=x), y=alt.Y(f"{y}:Q", title=y),
            color=color_enc, tooltip=tooltip,
        )
    else:  # bar | line | area
        if not (x and y):
            raise ValueError(f"{kind}: нужны X и Y.")
        mark = {"bar": "mark_bar", "line": "mark_line", "area": "mark_area"}[kind]
        enc = dict(
            x=alt.X(f"{x}:{_short(field_type(df, x))}", title=x),
            y=_y(y, agg), color=color_enc, tooltip=tooltip,
        )
        chart = getattr(alt.Chart(df), mark)(point=(kind == "line")).encode(**enc)

    chart = chart.properties(height=360)
    if interactive and kind in _ZOOMABLE:
        chart = chart.interactive()
    return chart


def _short(ftype: str) -> str:
    return {"temporal": "T", "quantitative": "Q", "nominal": "N"}[ftype]
