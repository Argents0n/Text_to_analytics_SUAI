"""Data-cleaning report: the issues the user handled by hand in the Practicum
preprocessing step, surfaced automatically.

Detects exact duplicates, implicit/fuzzy duplicate categories
("поселок Рябово" ≈ "пгт Рябово"), numeric anomalies (IQR), missing values with a
suggested fill strategy, and dtype mismatches (object that is really a date or a
number). Detection only — the UI decides whether to apply.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher

import pandas as pd
from pandas.api import types as ptypes

MAX_CARD_FUZZY = 500     # cap fuzzy comparison cost
SIM_THRESHOLD = 0.87


@dataclass
class CleaningReport:
    n_rows: int
    duplicate_rows: int
    implicit_dups: list[tuple[str, list[list[str]]]] = field(default_factory=list)   # (col, [ [variants], ... ])
    anomalies: list[dict] = field(default_factory=list)
    missing: list[dict] = field(default_factory=list)
    dtype_suggestions: list[dict] = field(default_factory=list)


def _normalize(v: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", "", str(v).lower())).strip()


def _implicit_dups(s: pd.Series) -> list[list[str]]:
    """Group categorical values that are the same after normalization or are fuzzily close."""
    values = [str(v) for v in s.dropna().unique()]
    if not (1 < len(values) <= MAX_CARD_FUZZY):
        return []

    # 1) exact-after-normalization groups
    buckets: dict[str, list[str]] = {}
    for v in values:
        buckets.setdefault(_normalize(v), []).append(v)
    groups = [g for g in buckets.values() if len(g) > 1]

    # 2) fuzzy groups among distinct normalized keys
    keys = [k for k, g in buckets.items() if len(g) == 1 and k]
    reps = [buckets[k][0] for k in keys]
    used = set()
    for i in range(len(keys)):
        if i in used:
            continue
        group = [reps[i]]
        for j in range(i + 1, len(keys)):
            if j in used:
                continue
            if SequenceMatcher(None, keys[i], keys[j]).ratio() >= SIM_THRESHOLD:
                group.append(reps[j])
                used.add(j)
        if len(group) > 1:
            used.add(i)
            groups.append(group)
    return groups


def _suggest_dtype(s: pd.Series) -> str | None:
    if not ptypes.is_object_dtype(s):
        return None
    sample = s.dropna().astype(str).head(200)
    if sample.empty:
        return None
    as_num = pd.to_numeric(sample.str.replace(",", ".", regex=False), errors="coerce")
    if as_num.notna().mean() > 0.9:
        return "numeric"
    as_dt = pd.to_datetime(sample, errors="coerce", dayfirst=True)
    if as_dt.notna().mean() > 0.9:
        return "datetime"
    return None


def _fill_strategy(s: pd.Series) -> str:
    if ptypes.is_numeric_dtype(s):
        skew = s.dropna().skew() if s.dropna().size > 2 else 0
        return "медиана" if abs(skew) > 1 else "среднее"
    return "мода / 'неизвестно'"


def clean_report(df: pd.DataFrame) -> CleaningReport:
    n = len(df)
    rep = CleaningReport(n_rows=n, duplicate_rows=int(df.duplicated().sum()))

    for col in df.columns:
        s = df[col]

        miss = int(s.isna().sum())
        if miss:
            rep.missing.append({
                "column": col,
                "n": miss,
                "pct": round(100 * miss / n, 1) if n else 0.0,
                "strategy": _fill_strategy(s),
            })

        if ptypes.is_numeric_dtype(s) and not ptypes.is_bool_dtype(s):
            x = s.dropna()
            if len(x) >= 20:
                q1, q3 = x.quantile(0.25), x.quantile(0.75)
                iqr = q3 - q1
                if iqr > 0:
                    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                    n_out = int(((x < lo) | (x > hi)).sum())
                    if n_out:
                        rep.anomalies.append({
                            "column": col, "n": n_out,
                            "pct": round(100 * n_out / len(x), 1),
                            "low": float(lo), "high": float(hi),
                        })
        else:
            groups = _implicit_dups(s)
            if groups:
                rep.implicit_dups.append((col, groups))

        suggested = _suggest_dtype(s)
        if suggested:
            rep.dtype_suggestions.append({"column": col, "current": str(s.dtype), "suggested": suggested})

    return rep
