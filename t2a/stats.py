"""Statistical analysis primitives — descriptive stats, normality, correlation,
group comparison and categorical association.

All classical (scipy/pandas), no LLM. Operate on a pandas DataFrame (pulled once
from DuckDB) plus explicit column lists, so every function is pure and unit-
testable. Tests pick sensible defaults: non-parametric by default (real data is
rarely normal), with an opt-in parametric switch.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import numpy as np
import pandas as pd
from scipy import stats as sps


def describe(df: pd.DataFrame, numeric: list[str]) -> pd.DataFrame:
    """Descriptive stats table for numeric columns (incl. skew/kurtosis/missing)."""
    rows = []
    n_total = len(df)
    for c in numeric:
        s = df[c].dropna()
        if s.empty:
            continue
        rows.append({
            "column": c,
            "count": int(s.size),
            "missing_%": round(100 * (n_total - s.size) / n_total, 1) if n_total else 0.0,
            "mean": s.mean(),
            "median": s.median(),
            "std": s.std(),
            "min": s.min(),
            "q25": s.quantile(0.25),
            "q75": s.quantile(0.75),
            "max": s.max(),
            "skew": sps.skew(s),
            "kurtosis": sps.kurtosis(s),
        })
    return pd.DataFrame(rows)


def normality(s: pd.Series) -> dict[str, Any] | None:
    """Shapiro-Wilk (n<=5000) or D'Agostino normality test."""
    s = pd.to_numeric(s, errors="coerce").dropna()
    n = int(s.size)
    if n < 8:
        return None
    if n <= 5000:
        stat, p = sps.shapiro(s)
        test = "Shapiro-Wilk"
    else:
        stat, p = sps.normaltest(s)
        test = "D'Agostino"
    return {"test": test, "stat": float(stat), "p": float(p), "normal": p > 0.05, "n": n}


def correlation_matrix(df: pd.DataFrame, numeric: list[str], method: str = "pearson") -> pd.DataFrame:
    return df[numeric].corr(method=method)


def corr_heatmap(corr: pd.DataFrame) -> alt.Chart:
    m = corr.reset_index(names="var1").melt("var1", var_name="var2", value_name="r")
    base = alt.Chart(m).encode(
        x=alt.X("var1:N", title=None),
        y=alt.Y("var2:N", title=None),
    )
    heat = base.mark_rect().encode(
        color=alt.Color("r:Q", scale=alt.Scale(scheme="blueorange", domain=[-1, 1])),
        tooltip=["var1", "var2", alt.Tooltip("r:Q", format=".2f")],
    )
    text = base.mark_text(baseline="middle").encode(
        text=alt.Text("r:Q", format=".2f"),
        color=alt.condition("abs(datum.r) > 0.5", alt.value("white"), alt.value("black")),
    )
    return heat + text


def top_correlations(corr: pd.DataFrame, k: int = 10) -> list[tuple[str, str, float]]:
    cols = list(corr.columns)
    pairs = [
        (cols[i], cols[j], float(corr.iloc[i, j]))
        for i in range(len(cols))
        for j in range(i + 1, len(cols))
        if not np.isnan(corr.iloc[i, j])
    ]
    pairs.sort(key=lambda t: abs(t[2]), reverse=True)
    return pairs[:k]


def compare_groups(
    df: pd.DataFrame,
    num_col: str,
    cat_col: str,
    parametric: bool = False,
    min_group: int = 3,
) -> dict[str, Any] | None:
    """Compare a numeric across groups of a categorical.

    2 groups -> Mann-Whitney U / Welch t-test; >2 -> Kruskal-Wallis / one-way ANOVA.
    """
    groups, labels = [], []
    for name, g in df.groupby(cat_col):
        vals = pd.to_numeric(g[num_col], errors="coerce").dropna().to_numpy()
        if len(vals) >= min_group:
            groups.append(vals)
            labels.append(str(name))
    k = len(groups)
    if k < 2:
        return None

    if k == 2:
        if parametric:
            stat, p = sps.ttest_ind(*groups, equal_var=False)
            test = "Welch t-test"
        else:
            stat, p = sps.mannwhitneyu(*groups, alternative="two-sided")
            test = "Mann-Whitney U"
    else:
        if parametric:
            stat, p = sps.f_oneway(*groups)
            test = "One-way ANOVA"
        else:
            stat, p = sps.kruskal(*groups)
            test = "Kruskal-Wallis"

    return {
        "test": test,
        "num_col": num_col,
        "cat_col": cat_col,
        "groups": k,
        "stat": float(stat),
        "p": float(p),
        "significant": p < 0.05,
        "group_medians": {lab: float(np.median(g)) for lab, g in zip(labels, groups)},
    }


def chi_square(df: pd.DataFrame, cat1: str, cat2: str) -> dict[str, Any] | None:
    """Chi-square test of independence + Cramér's V effect size."""
    ct = pd.crosstab(df[cat1], df[cat2])
    if ct.shape[0] < 2 or ct.shape[1] < 2:
        return None
    chi2, p, dof, _ = sps.chi2_contingency(ct)
    n = ct.to_numpy().sum()
    min_dim = min(ct.shape) - 1
    cramers_v = float(np.sqrt(chi2 / (n * min_dim))) if n and min_dim else 0.0
    return {
        "cat1": cat1,
        "cat2": cat2,
        "chi2": float(chi2),
        "p": float(p),
        "dof": int(dof),
        "cramers_v": cramers_v,
        "significant": p < 0.05,
        "contingency": ct,
    }
