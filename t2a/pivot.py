"""Pivot tables and binned-relationship analysis — the user's "mean price/m² by
locality" (pivot) and "price vs distance per km" (binned continuous) steps.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

AGGS = ("mean", "sum", "count", "median", "min", "max")


def pivot(df: pd.DataFrame, index: str, values: str, columns: str | None = None, aggfunc: str = "mean"):
    """Return (table, chart). 2D pivot -> heatmap; 1D -> sorted bar."""
    table = pd.pivot_table(df, index=index, columns=columns, values=values, aggfunc=aggfunc)
    if columns:
        m = table.reset_index().melt(index, var_name=columns, value_name="val")
        chart = alt.Chart(m).mark_rect().encode(
            x=alt.X(f"{columns}:N"), y=alt.Y(f"{index}:N"),
            color=alt.Color("val:Q", scale=alt.Scale(scheme="blues"), title=f"{aggfunc}({values})"),
            tooltip=[index, columns, alt.Tooltip("val:Q", format=".2f")],
        )
    else:
        d = table.reset_index()
        d.columns = [index, "val"]
        chart = alt.Chart(d).mark_bar().encode(
            x=alt.X("val:Q", title=f"{aggfunc}({values})"),
            y=alt.Y(f"{index}:N", sort="-x", title=index),
        )
    return table, chart


def binned_relationship(df: pd.DataFrame, x: str, y: str, bins: int = 10, agg: str = "mean", quantile: bool = False):
    """Bin continuous ``x``, aggregate ``y`` per bin. Returns (table, line chart)."""
    d = df[[x, y]].copy()
    d[x] = pd.to_numeric(d[x], errors="coerce")
    d[y] = pd.to_numeric(d[y], errors="coerce")
    d = d.dropna()
    d["bin"] = pd.qcut(d[x], q=bins, duplicates="drop") if quantile else pd.cut(d[x], bins=bins)
    grouped = d.groupby("bin", observed=True).agg(y_agg=(y, agg), x_mid=(x, "mean")).reset_index()
    chart = alt.Chart(grouped).mark_line(point=True).encode(
        x=alt.X("x_mid:Q", title=x), y=alt.Y("y_agg:Q", title=f"{agg}({y})"),
    ).properties(height=300)
    return grouped, chart
