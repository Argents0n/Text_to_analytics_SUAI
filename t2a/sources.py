"""Data source adapters: any tabular file -> a DuckDB table.

Core abstraction of the whole tool: whatever the source, we land it as a DuckDB
table so the analytics engine (SQL, profiling, insights, charts) stays
source-agnostic. DuckDB reads CSV/Parquet/JSON natively; xlsx goes through
pandas/openpyxl. Original column names are kept (they carry meaning that helps
the model) — downstream SQL must double-quote identifiers.
"""

from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd

TABLE = "data"

SUPPORTED = {".csv", ".tsv", ".parquet", ".json", ".jsonl", ".ndjson", ".xlsx", ".xls"}


def load_file(
    path: str | Path,
    con: duckdb.DuckDBPyConnection | None = None,
    table: str = TABLE,
) -> tuple[duckdb.DuckDBPyConnection, str]:
    """Load a file into ``table`` on a DuckDB connection. Returns (con, table)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"Неподдерживаемый формат: {ext}. Поддержаны: {sorted(SUPPORTED)}")

    if con is None:
        con = duckdb.connect(database=":memory:")
    con.execute(f'DROP TABLE IF EXISTS "{table}"')

    if ext in (".csv", ".tsv"):
        _load_csv(con, path, table, sep="\t" if ext == ".tsv" else None)
    elif ext == ".parquet":
        con.execute(f'CREATE TABLE "{table}" AS SELECT * FROM read_parquet(?)', [str(path)])
    elif ext in (".json", ".jsonl", ".ndjson"):
        con.execute(f'CREATE TABLE "{table}" AS SELECT * FROM read_json_auto(?)', [str(path)])
    elif ext in (".xlsx", ".xls"):
        df = pd.read_excel(path)  # openpyxl engine
        _register_df(con, df, table)

    return con, table


def _load_csv(con, path: Path, table: str, sep: str | None) -> None:
    """DuckDB sniffs type/sep/encoding; fall back to pandas for exotic encodings (cp1251)."""
    try:
        if sep:
            con.execute(
                f'CREATE TABLE "{table}" AS SELECT * FROM read_csv_auto(?, sep=?, sample_size=-1)',
                [str(path), sep],
            )
        else:
            con.execute(
                f'CREATE TABLE "{table}" AS SELECT * FROM read_csv_auto(?, sample_size=-1)',
                [str(path)],
            )
    except duckdb.Error:
        # DuckDB CSV reader only knows utf-8/utf-16/latin-1; RU exports are often cp1251.
        df = None
        for enc in ("utf-8", "cp1251", "latin-1"):
            try:
                df = pd.read_csv(
                    path, sep=sep, encoding=enc, engine="python" if sep is None else "c"
                )
                break
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        if df is None:
            raise
        _register_df(con, df, table)


def _register_df(con, df: pd.DataFrame, table: str) -> None:
    df.columns = [str(c).strip() for c in df.columns]
    con.register("_t2a_tmp", df)
    try:
        con.execute(f'CREATE TABLE "{table}" AS SELECT * FROM _t2a_tmp')
    finally:
        con.unregister("_t2a_tmp")
