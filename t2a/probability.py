"""Probability / distribution calculator — the GoFast optional step: binomial
sample sizing and normal approximation.
"""

from __future__ import annotations

from typing import Any

import altair as alt
import numpy as np
import pandas as pd
from scipy import stats as sps


def binomial_min_n(p: float, target: int, max_risk: float, cap: int = 100_000) -> dict[str, Any]:
    """Smallest n so that P(X >= target) >= 1 - max_risk, X ~ Binomial(n, p).

    Mirrors the promo-code question: how many to send so the plan is met with
    only ``max_risk`` probability of failure.
    """
    need = 1 - max_risk
    for n in range(target, cap + 1):
        # P(X >= target) = 1 - CDF(target-1)
        if 1 - sps.binom.cdf(target - 1, n, p) >= need:
            return {"n": n, "p": p, "target": target, "max_risk": max_risk,
                    "achieved": float(1 - sps.binom.cdf(target - 1, n, p))}
    return {"n": None, "p": p, "target": target, "max_risk": max_risk, "achieved": None}


def binomial_chart(n: int, p: float) -> alt.Chart:
    ks = np.arange(0, n + 1)
    pmf = sps.binom.pmf(ks, n, p)
    d = pd.DataFrame({"k": ks, "pmf": pmf})
    # trim the tail for readability
    lo, hi = sps.binom.ppf(0.001, n, p), sps.binom.ppf(0.999, n, p)
    d = d[(d["k"] >= lo) & (d["k"] <= hi)]
    return alt.Chart(d).mark_bar().encode(
        x=alt.X("k:Q", title="число успехов"), y=alt.Y("pmf:Q", title="вероятность"),
    ).properties(height=260)


def normal_approx(n: int, p: float, x: float, direction: str = "<=") -> dict[str, Any]:
    """Normal approximation to Binomial(n, p): P(X <= x) or P(X >= x)."""
    mu, sigma = n * p, np.sqrt(n * p * (1 - p))
    if direction == "<=":
        prob = float(sps.norm.cdf(x, mu, sigma))
    else:
        prob = float(sps.norm.sf(x, mu, sigma))
    return {"mu": mu, "sigma": sigma, "x": x, "direction": direction, "prob": prob}
