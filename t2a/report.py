"""Auto-report orchestration: profile -> classical insights -> LLM narration.

The LLM step is optional — if it fails, the precomputed finding texts are used
verbatim, so a report is always produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import duckdb

from .insights import Finding, mine
from .llm import LLM
from .narrate import narrate_findings
from .profile import profile


@dataclass
class Report:
    profile: dict[str, Any]
    findings: list[Finding]
    narrative: str


def build_report(
    con: duckdb.DuckDBPyConnection,
    table: str,
    llm: LLM | None = None,
    top_k: int = 8,
) -> Report:
    prof = profile(con, table)
    findings = mine(con, table, prof, top_k=top_k)
    narrative = narrate_findings(llm, findings) if llm else _plain(findings)
    return Report(profile=prof, findings=findings, narrative=narrative)


def _plain(findings: list[Finding]) -> str:
    if not findings:
        return "Значимых закономерностей не найдено."
    return "\n".join(f"- {f.text}" for f in findings)
