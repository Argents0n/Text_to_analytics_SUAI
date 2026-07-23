"""SQL guard: only a single read-only SELECT reaches the engine.

Parses the model's SQL with sqlglot and rejects anything that is not one
read-only query — no DDL/DML, no PRAGMA/COPY/ATTACH/SET. A LIMIT is injected
when absent so a stray ``SELECT *`` can't stream a huge table into the UI.
Defence in depth: the DuckDB connection is also opened read-only.
"""

from __future__ import annotations

import sqlglot
from sqlglot import exp

DIALECT = "duckdb"

# Statement types that must never execute.
_FORBIDDEN = (
    exp.Insert, exp.Update, exp.Delete, exp.Drop, exp.Create, exp.Alter,
    exp.Command, exp.Copy, exp.Set, exp.Merge, exp.TruncateTable,
)
_ALLOWED_TOP = (exp.Select, exp.Union, exp.Intersect, exp.Except, exp.Subquery, exp.With)


class GuardError(ValueError):
    pass


def guard(sql: str, max_limit: int = 1000) -> str:
    """Validate and normalize ``sql``; return a safe, LIMIT-bounded query."""
    if not sql or not sql.strip():
        raise GuardError("Пустой SQL.")

    try:
        statements = [s for s in sqlglot.parse(sql, dialect=DIALECT) if s is not None]
    except sqlglot.errors.ParseError as e:
        raise GuardError(f"Не удалось разобрать SQL: {e}") from e

    if len(statements) != 1:
        raise GuardError("Разрешён ровно один запрос.")

    stmt = statements[0]
    if not isinstance(stmt, _ALLOWED_TOP):
        raise GuardError(f"Разрешён только SELECT, получено: {type(stmt).__name__}.")

    for node in stmt.walk():
        if isinstance(node, _FORBIDDEN):
            raise GuardError(f"Запрещённая операция: {type(node).__name__}.")

    if isinstance(stmt, exp.Select) and not stmt.args.get("limit"):
        stmt = stmt.limit(max_limit)

    return stmt.sql(dialect=DIALECT)
