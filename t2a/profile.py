"""Profiling a loaded table.

No DB schema means no ready-made schema-linking context, so we build it ourselves:
types, cardinality, missingness, sample rows, numeric stats and top categorical
values. For small files the whole profile fits in the prompt — retrieval-based
schema linking is unnecessary at this scale. The same profile also drives chart
selection and the classical insight miners.
"""

from __future__ import annotations

from typing import Any

import duckdb
import pandas as pd

NUMERIC_TYPES = (
    "TINYINT", "SMALLINT", "INTEGER", "BIGINT", "HUGEINT",
    "UTINYINT", "USMALLINT", "UINTEGER", "UBIGINT",
    "FLOAT", "DOUBLE", "DECIMAL", "REAL", "NUMERIC",
)
TEMPORAL_TYPES = ("DATE", "TIMESTAMP", "TIME", "DATETIME")


def _is_numeric(dtype: str) -> bool:
    return any(dtype.upper().startswith(t) for t in NUMERIC_TYPES)


def _is_temporal(dtype: str) -> bool:
    return any(dtype.upper().startswith(t) for t in TEMPORAL_TYPES)


def profile(
    con: duckdb.DuckDBPyConnection,
    table: str = "data",
    sample_rows: int = 5,
    top_k: int = 5,
) -> dict[str, Any]:
    """Return a structured profile of ``table``."""
    cols = con.execute(f'PRAGMA table_info("{table}")').fetchall()
    nrows = con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]

    columns: list[dict[str, Any]] = []
    for c in cols:
        name, dtype = c[1], c[2]
        nonnull = con.execute(f'SELECT COUNT("{name}") FROM "{table}"').fetchone()[0]
        distinct = con.execute(f'SELECT COUNT(DISTINCT "{name}") FROM "{table}"').fetchone()[0]
        info: dict[str, Any] = {
            "name": name,
            "type": dtype,
            "role": _role(dtype),
            "distinct": distinct,
            "missing_pct": round(100 * (nrows - nonnull) / nrows, 1) if nrows else 0.0,
        }
        if _is_numeric(dtype):
            mn, mx, avg = con.execute(
                f'SELECT MIN("{name}"), MAX("{name}"), AVG("{name}") FROM "{table}"'
            ).fetchone()
            info.update(min=mn, max=mx, mean=avg)
        elif not _is_temporal(dtype):
            tops = con.execute(
                f'SELECT "{name}" AS v, COUNT(*) AS c FROM "{table}" '
                f'WHERE "{name}" IS NOT NULL GROUP BY 1 ORDER BY c DESC LIMIT ?',
                [top_k],
            ).fetchall()
            info["top"] = [(v, c) for v, c in tops]
        columns.append(info)

    sample = con.execute(f'SELECT * FROM "{table}" LIMIT ?', [sample_rows]).df()
    return {"table": table, "nrows": nrows, "columns": columns, "sample": sample}


def _role(dtype: str) -> str:
    if _is_numeric(dtype):
        return "numeric"
    if _is_temporal(dtype):
        return "temporal"
    return "categorical"


def roles(prof: dict[str, Any]) -> dict[str, list[str]]:
    """Group column names by role for chart selection / insight mining."""
    out: dict[str, list[str]] = {"numeric": [], "temporal": [], "categorical": []}
    for c in prof["columns"]:
        out[c["role"]].append(c["name"])
    return out


def schema_text(prof: dict[str, Any], sample_rows: int = 3) -> str:
    """Compact, prompt-ready schema description (RU)."""
    lines = [f'Таблица "{prof["table"]}" — {prof["nrows"]} строк. Колонки:']
    for c in prof["columns"]:
        parts = [f'"{c["name"]}" ({c["type"]})']
        if "mean" in c:
            parts.append(f'диапазон {_fmt(c["min"])}…{_fmt(c["max"])}, среднее {_fmt(c["mean"])}')
        elif c.get("top"):
            vals = ", ".join(str(v) for v, _ in c["top"][:4])
            parts.append(f"примеры: {vals}")
        if c["missing_pct"]:
            parts.append(f'пропусков {c["missing_pct"]}%')
        lines.append("- " + "; ".join(parts))

    head = prof["sample"].head(sample_rows)
    if not head.empty:
        lines.append("\nПервые строки:")
        lines.append(head.to_string(index=False))
    return "\n".join(lines)


def _fmt(v: Any) -> str:
    if isinstance(v, float):
        return f"{v:.2f}".rstrip("0").rstrip(".")
    return str(v)
