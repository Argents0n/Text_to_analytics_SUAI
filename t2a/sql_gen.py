"""Natural-language question -> DuckDB SQL.

Prompt carries the compact schema (from ``profile.schema_text``). On a retry the
previous SQL and the engine's error are fed back so the model can self-correct.
Output is cleaned of markdown fences / stray prose before it reaches the guard.
"""

from __future__ import annotations

import re

from .llm import LLM

SYSTEM = (
    "Ты — эксперт по анализу данных и DuckDB SQL. По схеме таблицы напиши ОДИН "
    "SELECT-запрос (диалект DuckDB), отвечающий на вопрос пользователя.\n"
    "Правила:\n"
    "- только SELECT, без INSERT/UPDATE/DELETE/DDL;\n"
    "- имена таблиц и колонок всегда в двойных кавычках (в данных возможна кириллица);\n"
    "- агрегации и группировки — где уместно; сортируй результат осмысленно;\n"
    "- верни ТОЛЬКО SQL, без пояснений и без markdown."
)

_FENCE = re.compile(r"```(?:sql)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)


def clean_sql(raw: str) -> str:
    """Strip markdown fences / leading 'sql' labels; keep the first statement."""
    m = _FENCE.search(raw)
    text = m.group(1) if m else raw
    text = text.strip()
    if text.lower().startswith("sql"):
        text = text[3:].lstrip(":").strip()
    # Keep up to the first statement terminator to avoid trailing prose.
    if ";" in text:
        text = text.split(";", 1)[0]
    return text.strip()


def generate_sql(
    llm: LLM,
    schema_text: str,
    question: str,
    error: str | None = None,
    prev_sql: str | None = None,
) -> str:
    user = f"{schema_text}\n\nВопрос: {question}"
    if error and prev_sql:
        user += (
            f"\n\nПредыдущий SQL:\n{prev_sql}\n"
            f"Ошибка при выполнении: {error}\n"
            "Исправь запрос."
        )
    return clean_sql(llm.complete(SYSTEM, user))
