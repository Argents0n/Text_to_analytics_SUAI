"""Hypothesis tests and bootstrap — the tests the user ran in the GoFast stats
project, plus the bootstrap CIs from the oil project.

one-sample vs a threshold, paired (before/after), two-sample (independent),
two-proportion, and a bootstrap CI for any statistic. Each returns the test
name, statistic, p-value and a plain significance verdict.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from scipy import stats as sps
from statsmodels.stats.proportion import proportions_ztest

ALT = ("two-sided", "less", "greater")


def _clean(x) -> np.ndarray:
    a = pd.to_numeric(pd.Series(x), errors="coerce").to_numpy()
    return a[~np.isnan(a)]


def _verdict(p: float, alpha: float = 0.05) -> bool:
    return p < alpha


def one_sample(x, popmean: float, alternative: str = "two-sided") -> dict[str, Any]:
    """H0: mean(x) == popmean. Student's one-sample t-test."""
    a = _clean(x)
    stat, p = sps.ttest_1samp(a, popmean, alternative=alternative)
    return {"test": "one-sample t-test", "n": a.size, "mean": float(a.mean()),
            "popmean": popmean, "stat": float(stat), "p": float(p),
            "alternative": alternative, "significant": _verdict(p)}


def paired(a, b, alternative: str = "two-sided") -> dict[str, Any]:
    """H0: mean(a) == mean(b) for paired/dependent samples (before/after)."""
    d = pd.DataFrame({"a": pd.to_numeric(pd.Series(a), errors="coerce"),
                      "b": pd.to_numeric(pd.Series(b), errors="coerce")}).dropna()
    stat, p = sps.ttest_rel(d["a"], d["b"], alternative=alternative)
    return {"test": "paired t-test", "n": len(d),
            "mean_diff": float((d["a"] - d["b"]).mean()),
            "stat": float(stat), "p": float(p),
            "alternative": alternative, "significant": _verdict(p)}


def two_sample(a, b, parametric: bool = False, alternative: str = "two-sided") -> dict[str, Any]:
    """Independent two-sample: Welch t-test (parametric) or Mann-Whitney U."""
    x, y = _clean(a), _clean(b)
    if parametric:
        stat, p = sps.ttest_ind(x, y, equal_var=False, alternative=alternative)
        test = "Welch t-test"
    else:
        stat, p = sps.mannwhitneyu(x, y, alternative=alternative)
        test = "Mann-Whitney U"
    return {"test": test, "n1": x.size, "n2": y.size,
            "median1": float(np.median(x)), "median2": float(np.median(y)),
            "stat": float(stat), "p": float(p),
            "alternative": alternative, "significant": _verdict(p)}


def two_proportion(succ1: int, n1: int, succ2: int, n2: int, alternative: str = "two-sided") -> dict[str, Any]:
    """Two-proportion z-test (e.g. conversion A vs B)."""
    stat, p = proportions_ztest([succ1, succ2], [n1, n2], alternative=alternative)
    return {"test": "two-proportion z-test",
            "p1": succ1 / n1 if n1 else 0.0, "p2": succ2 / n2 if n2 else 0.0,
            "stat": float(stat), "p": float(p),
            "alternative": alternative, "significant": _verdict(p)}


def bootstrap_ci(x, stat: str = "mean", n_boot: int = 2000, ci: float = 0.95, seed: int = 0) -> dict[str, Any]:
    """Percentile bootstrap CI for mean/median/std."""
    a = _clean(x)
    if a.size < 2:
        raise ValueError("Мало данных для бутстрапа.")
    func = {"mean": np.mean, "median": np.median, "std": np.std}[stat]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, a.size, size=(n_boot, a.size))
    boots = func(a[idx], axis=1)
    lo, hi = np.percentile(boots, [(1 - ci) / 2 * 100, (1 + ci) / 2 * 100])
    return {"stat": stat, "point": float(func(a)), "ci": ci,
            "low": float(lo), "high": float(hi), "n": a.size, "n_boot": n_boot}
