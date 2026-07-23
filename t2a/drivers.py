"""Driver analysis: given a numeric target, rank other columns by how strongly
they relate to it.

Numeric features -> |Pearson r|; categorical features -> correlation ratio η
(sqrt of between-group variance share), which lands on the same 0..1 scale, so
mixed feature types rank together. This is the automated version of the user's
real-estate EDA ("which parameters influence price").
"""

from __future__ import annotations

from dataclasses import dataclass

import altair as alt
import numpy as np
import pandas as pd
from pandas.api import types as ptypes
from scipy import stats as sps

MAX_CARD = 50   # skip id-like categoricals
MIN_N = 20


@dataclass
class Driver:
    feature: str
    kind: str          # "numeric" | "categorical"
    strength: float    # 0..1
    detail: str
    chart: alt.Chart | None = None


def correlation_ratio(categories: pd.Series, values: pd.Series) -> float:
    """η — share of variance in ``values`` explained by group membership."""
    d = pd.DataFrame({"c": categories.astype(str), "y": pd.to_numeric(values, errors="coerce")}).dropna()
    if d.empty:
        return 0.0
    grand = d["y"].mean()
    ss_total = float(((d["y"] - grand) ** 2).sum())
    if ss_total == 0:
        return 0.0
    ss_between = float(sum(len(g) * (g["y"].mean() - grand) ** 2 for _, g in d.groupby("c")))
    return float(np.sqrt(ss_between / ss_total))


def analyze_drivers(
    df: pd.DataFrame,
    target: str,
    features: list[str] | None = None,
    top_k: int = 15,
) -> list[Driver]:
    if not ptypes.is_numeric_dtype(df[target]):
        raise ValueError("Таргет должен быть числовым.")
    features = features or [c for c in df.columns if c != target]

    drivers: list[Driver] = []
    for f in features:
        if f == target:
            continue
        s = df[f]
        if ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s):
            d = df[[f, target]].dropna()
            if len(d) < MIN_N or d[f].nunique() < 2:
                continue
            r, _ = sps.pearsonr(d[f], d[target])
            drivers.append(Driver(
                f, "numeric", abs(float(r)), f"r={r:.2f}",
                alt.Chart(d.sample(min(len(d), 2000), random_state=0))
                .mark_circle(opacity=0.4)
                .encode(x=alt.X(f"{f}:Q", title=f), y=alt.Y(f"{target}:Q", title=target)),
            ))
        else:
            card = s.nunique()
            if not (2 <= card <= MAX_CARD):
                continue
            eta = correlation_ratio(s, df[target])
            means = (
                df.groupby(s.astype(str))[target].mean().reset_index()
                .rename(columns={s.name: f, target: "mean"}).sort_values("mean", ascending=False)
            )
            drivers.append(Driver(
                f, "categorical", eta, f"η={eta:.2f}",
                alt.Chart(means).mark_bar().encode(
                    x=alt.X("mean:Q", title=f"среднее {target}"),
                    y=alt.Y(f"{f}:N", sort="-x", title=f),
                ),
            ))

    drivers.sort(key=lambda d: d.strength, reverse=True)
    return drivers[:top_k]
