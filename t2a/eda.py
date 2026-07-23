"""Full automated EDA: overview -> descriptive stats -> univariate charts ->
correlation. Pure/classical; returns a structured report the UI renders.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import altair as alt
import duckdb
import pandas as pd

from . import stats as S
from .profile import profile, roles

MAX_BAR_CATEGORIES = 20  # skip univariate bars for very high-cardinality columns


@dataclass
class EdaReport:
    overview: dict[str, Any]
    describe: pd.DataFrame
    univariate: list[tuple[str, alt.Chart]] = field(default_factory=list)
    corr: pd.DataFrame | None = None
    corr_chart: alt.Chart | None = None
    top_corr: list[tuple[str, str, float]] = field(default_factory=list)


def _hist(df: pd.DataFrame, col: str) -> alt.Chart:
    data = df[[col]].dropna()
    if len(data) > 5000:
        data = data.sample(5000, random_state=0)
    return alt.Chart(data).mark_bar().encode(
        x=alt.X(f"{col}:Q", bin=alt.Bin(maxbins=30), title=col),
        y=alt.Y("count()", title="частота"),
    ).properties(height=200)


def _bar_counts(df: pd.DataFrame, col: str) -> alt.Chart:
    vc = df[col].value_counts().head(MAX_BAR_CATEGORIES).reset_index()
    vc.columns = [col, "count"]
    return alt.Chart(vc).mark_bar().encode(
        x=alt.X("count:Q", title="количество"),
        y=alt.Y(f"{col}:N", sort="-x", title=col),
    ).properties(height=min(30 * len(vc) + 40, 400))


def build_eda(con: duckdb.DuckDBPyConnection, table: str) -> EdaReport:
    prof = profile(con, table)
    r = roles(prof)
    df = con.execute(f'SELECT * FROM "{table}"').df()

    total_cells = df.shape[0] * df.shape[1]
    overview = {
        "rows": df.shape[0],
        "columns": df.shape[1],
        "numeric": len(r["numeric"]),
        "categorical": len(r["categorical"]),
        "temporal": len(r["temporal"]),
        "missing_cells_%": round(100 * df.isna().sum().sum() / total_cells, 1) if total_cells else 0.0,
        "duplicate_rows": int(df.duplicated().sum()),
    }

    describe = S.describe(df, r["numeric"])

    univariate: list[tuple[str, alt.Chart]] = []
    for col in r["numeric"]:
        univariate.append((col, _hist(df, col)))
    for col in r["categorical"]:
        if 1 < df[col].nunique() <= MAX_BAR_CATEGORIES:
            univariate.append((col, _bar_counts(df, col)))

    report = EdaReport(overview=overview, describe=describe, univariate=univariate)

    if len(r["numeric"]) >= 2:
        corr = S.correlation_matrix(df, r["numeric"])
        report.corr = corr
        report.corr_chart = S.corr_heatmap(corr)
        report.top_corr = S.top_correlations(corr)

    return report
