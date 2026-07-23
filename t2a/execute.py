"""Execute generated SQL with a self-correcting retry loop.

generate -> guard -> run. On a guard or engine error the message is fed back to
the model (up to ``max_retries``), which is what lifts execution accuracy on
messy schemas. The final failure is surfaced, never silently swallowed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import duckdb
import pandas as pd

from .llm import LLM
from .sql_gen import generate_sql
from .sql_guard import GuardError, guard


@dataclass
class SqlResult:
    sql: str
    df: pd.DataFrame
    attempts: int
    trace: list[dict] = field(default_factory=list)


class ExecError(RuntimeError):
    def __init__(self, message: str, trace: list[dict]):
        super().__init__(message)
        self.trace = trace


def answer_sql(
    con: duckdb.DuckDBPyConnection,
    llm: LLM,
    schema_text: str,
    question: str,
    max_retries: int = 2,
) -> SqlResult:
    sql = generate_sql(llm, schema_text, question)
    trace: list[dict] = []
    last_err = ""

    for attempt in range(max_retries + 1):
        try:
            safe = guard(sql)
            df = con.execute(safe).df()
            trace.append({"attempt": attempt + 1, "sql": safe, "ok": True})
            return SqlResult(sql=safe, df=df, attempts=attempt + 1, trace=trace)
        except (GuardError, duckdb.Error) as e:
            last_err = str(e)
            trace.append({"attempt": attempt + 1, "sql": sql, "ok": False, "error": last_err})
            if attempt < max_retries:
                sql = generate_sql(llm, schema_text, question, error=last_err, prev_sql=sql)

    raise ExecError(f"Не удалось получить рабочий SQL за {max_retries + 1} попытки: {last_err}", trace)
