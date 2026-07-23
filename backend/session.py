"""In-memory dataset store — a dataset is a workspace of one or more related
tables sharing a single DuckDB connection.

Multiple files (e.g. orders + customers) load as separate tables in the same
connection, so chat can JOIN across them. The connection isn't safe under
concurrent queries, so each dataset carries a lock.
"""

from __future__ import annotations

import re
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from t2a.profile import profile as build_profile
from t2a.sources import load_file

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SAMPLE_SALES = DATA_DIR / "sample_sales_ru.csv"
SAMPLE_CUSTOMERS = DATA_DIR / "sample_customers_ru.csv"

_STORE: dict[str, "Dataset"] = {}


@dataclass
class Dataset:
    id: str
    con: duckdb.DuckDBPyConnection
    tables: list[str] = field(default_factory=list)
    profiles: dict[str, dict[str, Any]] = field(default_factory=dict)
    lock: threading.Lock = field(default_factory=threading.Lock)


def _table_name(filename: str, taken: list[str]) -> str:
    stem = Path(filename).stem.lower()
    name = re.sub(r"[^\w]+", "_", stem).strip("_") or "table"
    if name[0].isdigit():
        name = "t_" + name
    base, i = name, 2
    while name in taken:
        name = f"{base}_{i}"
        i += 1
    return name


def _add(ds: Dataset, path: str, filename: str) -> str:
    name = _table_name(filename, ds.tables)
    load_file(path, con=ds.con, table=name)
    ds.tables.append(name)
    ds.profiles[name] = build_profile(ds.con, name)
    return name


def create(path: str, filename: str) -> Dataset:
    ds = Dataset(id=uuid.uuid4().hex[:12], con=duckdb.connect(database=":memory:"))
    _add(ds, path, filename)
    _STORE[ds.id] = ds
    return ds


def add_from_path(dataset_id: str, path: str, filename: str) -> Dataset:
    ds = get(dataset_id)
    _add(ds, path, filename)
    return ds


def create_from_bytes(data: bytes, filename: str) -> Dataset:
    return create(*_spill(data, filename), )


def add_from_bytes(dataset_id: str, data: bytes, filename: str) -> Dataset:
    path, name = _spill(data, filename)
    return add_from_path(dataset_id, path, name)


def _spill(data: bytes, filename: str) -> tuple[str, str]:
    suffix = Path(filename).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(data)
        return tmp.name, filename


def create_demo() -> Dataset:
    ds = create(str(SAMPLE_SALES), "sales.csv")
    if SAMPLE_CUSTOMERS.exists():
        _add(ds, str(SAMPLE_CUSTOMERS), "customers.csv")
    return ds


def merge_tables(ds: Dataset, left: str, right: str, on: str, how: str = "left") -> str:
    """Join two tables into a new one (added to the dataset) so any section can
    analyse the merged result. Right-side columns that clash with the left are
    dropped to avoid duplicate-column errors; the join key is kept once."""
    if left not in ds.tables or right not in ds.tables:
        raise ValueError("Нет такой таблицы.")
    lcols = [c["name"] for c in ds.profiles[left]["columns"]]
    rcols_all = [c["name"] for c in ds.profiles[right]["columns"]]
    if on not in lcols or on not in rcols_all:
        raise ValueError(f"Ключ «{on}» должен быть в обеих таблицах.")
    rcols = [c for c in rcols_all if c != on and c not in lcols]

    name = _table_name(f"{left}_{right}", ds.tables)
    join = "LEFT JOIN" if how == "left" else "JOIN"
    select = ", ".join([f'l."{c}"' for c in lcols] + [f'r."{c}"' for c in rcols])
    ds.con.execute(
        f'CREATE TABLE "{name}" AS SELECT {select} '
        f'FROM "{left}" l {join} "{right}" r ON l."{on}" = r."{on}"'
    )
    ds.tables.append(name)
    ds.profiles[name] = build_profile(ds.con, name)
    return name


def get(dataset_id: str) -> Dataset:
    return _STORE[dataset_id]
