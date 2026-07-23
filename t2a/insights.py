"""Classical insight miners — the compute is here, not in the LLM.

Each miner produces ``Finding``s with the numbers already baked into ``text``;
the LLM later only rephrases them. Methods are deliberately plain (Pearson r,
IQR outliers, linear-fit trend, group means) with significance / sample-size
guards to avoid surfacing spurious patterns. Matches the light-compute goal.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import altair as alt
import duckdb
import numpy as np
import pandas as pd
from scipy import stats

from .profile import roles

MIN_N = 30            # too few rows -> don't trust correlations/trends
CORR_MIN = 0.3        # ignore weak correlations
CORR_ALPHA = 0.05     # significance threshold
OUTLIER_MIN_SHARE = 0.01
MAX_GROUP_CARD = 15   # only mine group differences on low-cardinality categoricals


@dataclass
class Finding:
    kind: str          # "correlation" | "trend" | "group" | "outliers" | "missing"
    text: str          # RU sentence with numbers baked in
    score: float       # ~0..1, for ranking across kinds
    chart: alt.Chart | None = None


def mine(con: duckdb.DuckDBPyConnection, table: str, prof: dict[str, Any], top_k: int = 8) -> list[Finding]:
    r = roles(prof)
    findings: list[Finding] = []
    findings += _missingness(prof)
    findings += _correlations(con, table, r["numeric"])
    findings += _outliers(con, table, r["numeric"])
    measure = _main_measure(con, table, r["numeric"])
    if measure:
        findings += _trend(con, table, r["temporal"], measure)
        findings += _group_diffs(con, table, r["categorical"], measure)
    findings.sort(key=lambda f: f.score, reverse=True)
    return findings[:top_k]


def _fmt(v: float) -> str:
    return f"{v:,.0f}".replace(",", " ") if abs(v) >= 100 else f"{v:.2f}"


def _main_measure(con, table, numeric: list[str]) -> str | None:
    """Pick the numeric column with the most relative variation (likely a real metric)."""
    best, best_cv = None, -1.0
    for col in numeric:
        mean, std = con.execute(
            f'SELECT AVG("{col}"), STDDEV_SAMP("{col}") FROM "{table}"'
        ).fetchone()
        if mean and std and mean != 0:
            cv = abs(std / mean)
            if cv > best_cv:
                best, best_cv = col, cv
    return best


def _missingness(prof: dict[str, Any]) -> list[Finding]:
    out = []
    for c in prof["columns"]:
        if c["missing_pct"] >= 5:
            out.append(Finding(
                "missing",
                f'В колонке «{c["name"]}» пропущено {c["missing_pct"]}% значений.',
                score=min(c["missing_pct"] / 100, 0.6),
            ))
    return out


def _correlations(con, table, numeric: list[str]) -> list[Finding]:
    out = []
    for i in range(len(numeric)):
        for j in range(i + 1, len(numeric)):
            a, b = numeric[i], numeric[j]
            df = con.execute(
                f'SELECT "{a}" AS a, "{b}" AS b FROM "{table}" '
                f'WHERE "{a}" IS NOT NULL AND "{b}" IS NOT NULL'
            ).df()
            if len(df) < MIN_N or df["a"].nunique() < 2 or df["b"].nunique() < 2:
                continue
            r, p = stats.pearsonr(df["a"], df["b"])
            if abs(r) >= CORR_MIN and p < CORR_ALPHA:
                direction = "положительная" if r > 0 else "отрицательная"
                sample = df.sample(min(len(df), 2000), random_state=0)
                chart = alt.Chart(sample).mark_circle(opacity=0.5).encode(
                    x=alt.X("a:Q", title=a), y=alt.Y("b:Q", title=b)
                )
                out.append(Finding(
                    "correlation",
                    f'{direction.capitalize()} связь между «{a}» и «{b}» (r={r:.2f}).',
                    score=abs(r), chart=chart,
                ))
    return out


def _outliers(con, table, numeric: list[str]) -> list[Finding]:
    out = []
    for col in numeric:
        s = con.execute(f'SELECT "{col}" FROM "{table}" WHERE "{col}" IS NOT NULL').df()[col]
        if len(s) < MIN_N:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr == 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((s < lo) | (s > hi)).sum())
        share = n_out / len(s)
        if share >= OUTLIER_MIN_SHARE:
            chart = alt.Chart(pd.DataFrame({col: s})).mark_bar().encode(
                x=alt.X(f"{col}:Q", bin=alt.Bin(maxbins=30), title=col),
                y=alt.Y("count()", title="частота"),
            )
            out.append(Finding(
                "outliers",
                f'В «{col}» {n_out} выбросов ({share * 100:.1f}%), вне диапазона '
                f'{_fmt(lo)}…{_fmt(hi)}.',
                score=min(share, 0.5), chart=chart,
            ))
    return out


def _trend(con, table, temporal: list[str], measure: str) -> list[Finding]:
    if not temporal:
        return []
    tcol = temporal[0]
    df = con.execute(
        f'SELECT date_trunc(\'month\', "{tcol}") AS period, SUM("{measure}") AS val '
        f'FROM "{table}" WHERE "{tcol}" IS NOT NULL GROUP BY 1 ORDER BY 1'
    ).df()
    if len(df) < 3:
        return []
    x = np.arange(len(df))
    y = df["val"].to_numpy(dtype=float)
    slope, intercept, r, p, _ = stats.linregress(x, y)
    if p >= CORR_ALPHA or abs(r) < CORR_MIN:
        return []
    direction = "растёт" if slope > 0 else "снижается"
    chart = alt.Chart(df).mark_line(point=True).encode(
        x=alt.X("period:T", title=tcol), y=alt.Y("val:Q", title=measure)
    )
    return [Finding(
        "trend",
        f'«{measure}» {direction} во времени (R²={r ** 2:.2f}, по месяцам).',
        score=min(r ** 2, 0.95), chart=chart,
    )]


def _group_diffs(con, table, categorical: list[str], measure: str) -> list[Finding]:
    out = []
    for cat in categorical:
        card = con.execute(f'SELECT COUNT(DISTINCT "{cat}") FROM "{table}"').fetchone()[0]
        if not (2 <= card <= MAX_GROUP_CARD):
            continue
        df = con.execute(
            f'SELECT "{cat}" AS g, AVG("{measure}") AS avg_val FROM "{table}" '
            f'WHERE "{cat}" IS NOT NULL AND "{measure}" IS NOT NULL GROUP BY 1 ORDER BY avg_val DESC'
        ).df()
        if len(df) < 2:
            continue
        top, bottom = df.iloc[0], df.iloc[-1]
        if top["avg_val"] == 0:
            continue
        spread = (top["avg_val"] - bottom["avg_val"]) / abs(top["avg_val"])
        if spread < 0.15:
            continue
        chart = alt.Chart(df).mark_bar().encode(
            x=alt.X("avg_val:Q", title=f"среднее {measure}"),
            y=alt.Y("g:N", sort="-x", title=cat),
        )
        out.append(Finding(
            "group",
            f'По «{cat}» лидирует «{top["g"]}» (среднее {measure} {_fmt(top["avg_val"])}), '
            f'минимум — «{bottom["g"]}» ({_fmt(bottom["avg_val"])}).',
            score=min(spread, 0.9), chart=chart,
        ))
    return out
