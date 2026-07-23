"""Cohort analysis: group entities by their first-activity period, then track a
metric across period offsets.

Columns (id/date/value) are chosen by the user from the known schema, not free
text — but we still validate them against the table's columns and double-quote
identifiers before building SQL. Metric is retention (distinct ids), or sum/avg
of a value column.
"""

from __future__ import annotations

from dataclasses import dataclass

import altair as alt
import duckdb
import pandas as pd

PERIODS = ("day", "week", "month")
METRICS = ("retention", "sum", "avg")


@dataclass
class CohortResult:
    matrix: pd.DataFrame       # cohort (rows) x period offset (cols), raw values
    display: pd.DataFrame      # normalized to % for retention, else == matrix
    sizes: pd.Series           # cohort sizes (offset 0)
    metric: str
    chart: alt.Chart


def _columns(con, table) -> set[str]:
    return {row[1] for row in con.execute(f'PRAGMA table_info("{table}")').fetchall()}


def cohort_analysis(
    con: duckdb.DuckDBPyConnection,
    table: str,
    id_col: str,
    date_col: str,
    value_col: str | None = None,
    period: str = "month",
    metric: str = "retention",
    normalize: bool = True,
) -> CohortResult:
    if period not in PERIODS:
        raise ValueError(f"period ∈ {PERIODS}")
    if metric not in METRICS:
        raise ValueError(f"metric ∈ {METRICS}")
    if metric in ("sum", "avg") and not value_col:
        raise ValueError("Для sum/avg нужна колонка значения.")

    cols = _columns(con, table)
    for col in (id_col, date_col, value_col):
        if col and col not in cols:
            raise ValueError(f"Нет колонки «{col}» в таблице.")

    vsel = f', "{value_col}" AS v' if value_col else ""
    vjoin = ", b.v" if value_col else ""
    agg = {"retention": "COUNT(DISTINCT id)", "sum": "SUM(v)", "avg": "AVG(v)"}[metric]

    query = f"""
    WITH base AS (
        SELECT "{id_col}" AS id, date_trunc('{period}', "{date_col}") AS p {vsel}
        FROM "{table}"
        WHERE "{id_col}" IS NOT NULL AND "{date_col}" IS NOT NULL
    ),
    cohort AS (SELECT id, MIN(p) AS cohort_p FROM base GROUP BY id),
    joined AS (
        SELECT b.id, c.cohort_p, date_diff('{period}', c.cohort_p, b.p) AS idx {vjoin}
        FROM base b JOIN cohort c USING (id)
    )
    SELECT cohort_p, idx, {agg} AS val
    FROM joined GROUP BY 1, 2 ORDER BY 1, 2
    """
    long = con.execute(query).df()
    if long.empty:
        raise ValueError("Недостаточно данных для когорт.")

    long["cohort"] = pd.to_datetime(long["cohort_p"]).dt.strftime(_label_fmt(period))
    matrix = long.pivot(index="cohort", columns="idx", values="val").sort_index()
    sizes = matrix.get(0, matrix.iloc[:, 0]).rename("cohort_size")

    if metric == "retention" and normalize:
        display = matrix.div(sizes, axis=0) * 100
        legend = "% удержания"
        fmt = ".0f"
    else:
        display = matrix
        legend = {"retention": "клиентов", "sum": "сумма", "avg": "среднее"}[metric]
        fmt = ".0f"

    return CohortResult(matrix, display, sizes, metric, _heatmap(display, legend, fmt))


def _label_fmt(period: str) -> str:
    return {"day": "%Y-%m-%d", "week": "%Y-%m-%d", "month": "%Y-%m"}[period]


def _heatmap(display: pd.DataFrame, legend: str, fmt: str) -> alt.Chart:
    m = display.reset_index().melt("cohort", var_name="idx", value_name="val").dropna()
    base = alt.Chart(m).encode(
        x=alt.X("idx:O", title="период с начала"),
        y=alt.Y("cohort:O", title="когорта"),
    )
    heat = base.mark_rect().encode(
        color=alt.Color("val:Q", scale=alt.Scale(scheme="greens"), title=legend),
        tooltip=["cohort", "idx", alt.Tooltip("val:Q", format=".1f")],
    )
    text = base.mark_text(baseline="middle", fontSize=10).encode(
        text=alt.Text("val:Q", format=fmt),
    )
    return (heat + text).properties(height=alt.Step(28))
