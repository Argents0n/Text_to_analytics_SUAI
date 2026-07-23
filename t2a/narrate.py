"""LLM narration. The model only phrases precomputed numbers into Russian — it
never computes. Two entry points: a short answer for chat, and a findings
narrator for the auto-report.
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from .llm import LLM, LLMError

_CHAT_SYSTEM = (
    "Ты — аналитик. По вопросу и таблице результата дай короткий ответ на русском "
    "(1–2 предложения). Опирайся ТОЛЬКО на данные из таблицы, не выдумывай чисел. "
    "Без вступлений и markdown."
)

_REPORT_SYSTEM = (
    "Ты — аналитик. Тебе дан список уже посчитанных находок по датасету. "
    "Перескажи каждую находку одним понятным предложением на русском. "
    "НЕ меняй числа, НЕ добавляй новых выводов. Верни маркированный список."
)


def summarize_result(llm: LLM, question: str, df: pd.DataFrame, max_rows: int = 20) -> str:
    """One-line RU answer for chat. Best-effort: returns '' if the LLM fails."""
    table = df.head(max_rows).to_string(index=False)
    user = f"Вопрос: {question}\n\nРезультат:\n{table}"
    try:
        return llm.complete(_CHAT_SYSTEM, user).strip()
    except LLMError:
        return ""


def narrate_findings(llm: LLM, findings: list[Any]) -> str:
    """Turn precomputed findings (objects with .kind/.text) into a RU bullet list.

    Falls back to the raw precomputed text if the LLM is unavailable — the report
    still works offline, just less fluent.
    """
    if not findings:
        return "Значимых закономерностей не найдено."
    lines = [f"- [{f.kind}] {f.text}" for f in findings]
    user = "Находки:\n" + "\n".join(lines)
    try:
        return llm.complete(_REPORT_SYSTEM, user).strip()
    except LLMError:
        return "\n".join(lines)
