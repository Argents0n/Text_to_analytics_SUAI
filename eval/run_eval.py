"""Execution-accuracy eval: does the model's SQL produce the reference result?

Truth is the *result* of each gold SQL, not its text — so alias/column-order/
formatting differences don't matter (BIRD/Spider-style execution match). Run
``--dry`` to sanity-check the comparator and gold SQL without calling the LLM
(gold is used as its own prediction, expect 100%).
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import yaml
from dotenv import load_dotenv

from t2a.execute import ExecError, answer_sql
from t2a.llm import LLM
from t2a.profile import profile, schema_text
from t2a.sources import load_file
from t2a.sql_guard import guard

ROOT = Path(__file__).resolve().parents[1]


def _sig(df: pd.DataFrame) -> list[tuple[str, ...]]:
    """Order-insensitive signature of a result set (rounds floats, sorts)."""
    d = df.copy()
    for c in d.columns:
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].round(2)
    rows = [tuple(sorted(str(v) for v in row)) for row in d.itertuples(index=False)]
    return sorted(rows)


def results_match(gold: pd.DataFrame, pred: pd.DataFrame) -> bool:
    return _sig(gold) == _sig(pred)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold", default=str(Path(__file__).parent / "gold.yaml"))
    ap.add_argument("--dry", action="store_true", help="use gold SQL as prediction (no LLM)")
    args = ap.parse_args()

    load_dotenv()
    spec = yaml.safe_load(Path(args.gold).read_text(encoding="utf-8"))
    con, table = load_file(ROOT / spec["dataset"])
    schema = schema_text(profile(con, table))
    llm = None if args.dry else LLM()

    items = spec["items"]
    passed = 0
    for i, item in enumerate(items, 1):
        q, gold_sql = item["question"], item["sql"]
        gold_df = con.execute(gold_sql).df()
        try:
            if args.dry:
                pred_df = con.execute(guard(gold_sql)).df()
            else:
                pred_df = answer_sql(con, llm, schema, q).df
            ok = results_match(gold_df, pred_df)
        except (ExecError, Exception) as e:  # noqa: BLE001 — a failed case is just wrong
            ok = False
            print(f"  [{i:2}] ERROR: {str(e)[:80]}")
        passed += ok
        print(f"  [{i:2}] {'OK ' if ok else 'FAIL'}  {q}")

    total = len(items)
    print(f"\nExecution accuracy: {passed}/{total} = {passed / total:.1%}")


if __name__ == "__main__":
    main()
