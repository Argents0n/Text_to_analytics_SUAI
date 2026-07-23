"""FastAPI app: thin HTTP layer over the t2a engine.

A dataset is one or more related tables in a shared DuckDB connection. Chat gets
the schema of *all* tables so the model can JOIN across them. Charts are returned
as Vega-Lite specs (``alt.Chart.to_dict()``) for react-vega. DataFrames are
serialized via pandas' JSON writer so numpy types, NaN and dates become valid JSON.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from t2a import abtest, cleaning, drivers, probability
from t2a import pivot as pv
from t2a import stats as S
from t2a import timeseries as ts
from t2a.chart_builder import build_custom
from t2a.charts import choose_chart
from t2a.cohort import cohort_analysis
from t2a.eda import build_eda
from t2a.execute import ExecError, answer_sql
from t2a.llm import LLM, LLMError
from t2a.narrate import summarize_result
from t2a.profile import roles, schema_text
from t2a.report import build_report
from t2a.theme import enable_altair

from . import session

load_dotenv()
enable_altair()

app = FastAPI(title="Text-to-Analytics API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    # unhandled 500s bypass CORSMiddleware -> browser shows "Load failed"; attach
    # the origin header and a readable message so the UI surfaces the real error.
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
        headers={"Access-Control-Allow-Origin": "http://localhost:3000"},
    )


def _records(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _native(obj):
    """Recursively convert numpy scalars (bool_, float64...) to JSON-native types."""
    if isinstance(obj, dict):
        return {k: _native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_native(v) for v in obj]
    if isinstance(obj, np.generic):
        return obj.item()
    return obj


def _table_payload(ds: session.Dataset, name: str) -> dict:
    prof = ds.profiles[name]
    return {
        "name": name,
        "nrows": prof["nrows"],
        "roles": roles(prof),
        "columns": [
            {"name": c["name"], "type": c["type"], "role": c["role"],
             "missing_pct": c["missing_pct"], "distinct": c["distinct"]}
            for c in prof["columns"]
        ],
        "sample": _records(prof["sample"]),
    }


def _dataset_payload(ds: session.Dataset) -> dict:
    return {"id": ds.id, "tables": [_table_payload(ds, t) for t in ds.tables]}


def _combined_schema(ds: session.Dataset) -> str:
    return "\n\n".join(schema_text(ds.profiles[t]) for t in ds.tables)


def _dataset(dataset_id: str) -> session.Dataset:
    try:
        return session.get(dataset_id)
    except KeyError:
        raise HTTPException(404, "Датасет не найден. Загрузите файл заново.")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/datasets")
async def upload(file: UploadFile = File(...)) -> dict:
    data = await file.read()
    try:
        ds = session.create_from_bytes(data, file.filename or "upload")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Не удалось загрузить: {e}")
    return _dataset_payload(ds)


@app.post("/api/datasets/{dataset_id}/tables")
async def add_table(dataset_id: str, file: UploadFile = File(...)) -> dict:
    ds = _dataset(dataset_id)
    data = await file.read()
    try:
        with ds.lock:
            session.add_from_bytes(dataset_id, data, file.filename or "upload")
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"Не удалось добавить таблицу: {e}")
    return _dataset_payload(ds)


@app.post("/api/datasets/demo")
def demo() -> dict:
    return _dataset_payload(session.create_demo())


class MergeReq(BaseModel):
    left: str
    right: str
    on: str
    how: str = "left"


@app.post("/api/datasets/{dataset_id}/merge")
def merge(dataset_id: str, req: MergeReq) -> dict:
    ds = _dataset(dataset_id)
    try:
        with ds.lock:
            session.merge_tables(ds, req.left, req.right, req.on, req.how)
    except Exception as e:  # noqa: BLE001 — join errors → readable 422
        raise HTTPException(422, f"Не удалось объединить: {e}")
    return _dataset_payload(ds)


@app.get("/api/datasets/{dataset_id}/profile")
def get_profile(dataset_id: str) -> dict:
    return _dataset_payload(_dataset(dataset_id))


class ChatRequest(BaseModel):
    question: str
    provider: str = "openrouter"
    model: str | None = None


@app.post("/api/datasets/{dataset_id}/chat")
def chat(dataset_id: str, req: ChatRequest) -> dict:
    ds = _dataset(dataset_id)
    llm = LLM(provider=req.provider, model=req.model)
    try:
        with ds.lock:
            res = answer_sql(ds.con, llm, _combined_schema(ds), req.question)
    except LLMError as e:
        raise HTTPException(502, f"LLM: {e}")
    except ExecError as e:
        raise HTTPException(422, str(e))
    choice = choose_chart(res.df)
    return {
        "sql": res.sql,
        "attempts": res.attempts,
        "answer": summarize_result(llm, req.question, res.df),
        "columns": list(res.df.columns),
        "rows": _records(res.df.head(500)),
        "chart": choice.chart.to_dict() if choice.chart is not None else None,
        "chart_kind": choice.kind,
    }


@app.post("/api/datasets/{dataset_id}/eda")
def eda(dataset_id: str, table: str | None = None) -> dict:
    ds = _dataset(dataset_id)
    target = table if table in ds.tables else ds.tables[0]
    with ds.lock:
        rep = build_eda(ds.con, target)
    return {
        "table": target,
        "overview": rep.overview,
        "describe": _records(rep.describe),
        "corr_chart": rep.corr_chart.to_dict() if rep.corr_chart is not None else None,
        "top_corr": [{"a": a, "b": b, "r": r} for a, b, r in rep.top_corr],
        "univariate": [{"name": name, "chart": ch.to_dict()} for name, ch in rep.univariate],
    }


# ---- remaining sections (thin wrappers over the t2a engine) ----

def _pick(ds: session.Dataset, table: str | None) -> str:
    return table if table in ds.tables else ds.tables[0]


def _df(ds: session.Dataset, table: str):
    return ds.con.execute(f'SELECT * FROM "{table}"').df()


class TableReq(BaseModel):
    table: str | None = None


class ReportReq(TableReq):
    provider: str = "openrouter"
    model: str | None = None


@app.post("/api/datasets/{dataset_id}/report")
def report(dataset_id: str, req: ReportReq) -> dict:
    ds = _dataset(dataset_id)
    table = _pick(ds, req.table)
    llm = LLM(provider=req.provider, model=req.model)
    with ds.lock:
        rep = build_report(ds.con, table, llm)
    return {
        "table": table,
        "narrative": rep.narrative,
        "findings": [
            {"kind": f.kind, "text": f.text,
             "chart": f.chart.to_dict() if f.chart is not None else None}
            for f in rep.findings
        ],
    }


@app.post("/api/datasets/{dataset_id}/cleaning")
def cleaning_report(dataset_id: str, table: str | None = None) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, table)
    with ds.lock:
        rep = cleaning.clean_report(_df(ds, t))
    return {
        "table": t,
        "n_rows": rep.n_rows,
        "duplicate_rows": rep.duplicate_rows,
        "missing": rep.missing,
        "anomalies": rep.anomalies,
        "dtype_suggestions": rep.dtype_suggestions,
        "implicit_dups": [{"column": c, "groups": g} for c, g in rep.implicit_dups],
    }


class DriversReq(TableReq):
    target: str


@app.post("/api/datasets/{dataset_id}/drivers")
def drivers_endpoint(dataset_id: str, req: DriversReq) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, req.table)
    with ds.lock:
        df = _df(ds, t)
    try:
        found = drivers.analyze_drivers(df, req.target)
    except ValueError as e:
        raise HTTPException(422, str(e))
    return {
        "table": t,
        "drivers": [
            {"feature": d.feature, "kind": d.kind, "strength": d.strength,
             "detail": d.detail, "chart": d.chart.to_dict() if d.chart is not None else None}
            for d in found
        ],
    }


class StatsReq(TableReq):
    kind: str
    num: str | None = None
    cat: str | None = None
    cat1: str | None = None
    cat2: str | None = None
    parametric: bool = False
    method: str = "pearson"


@app.post("/api/datasets/{dataset_id}/stats")
def stats_endpoint(dataset_id: str, req: StatsReq) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, req.table)
    with ds.lock:
        df = _df(ds, t)
    prof = ds.profiles[t]
    if req.kind == "group" and req.num and req.cat:
        return {"result": _native(S.compare_groups(df, req.num, req.cat, parametric=req.parametric))}
    if req.kind == "chi2" and req.cat1 and req.cat2:
        res = S.chi_square(df, req.cat1, req.cat2)
        if res:
            res = {**res, "contingency": _records(res["contingency"].reset_index())}
        return {"result": _native(res)}
    if req.kind == "normality" and req.num:
        return {"result": _native(S.normality(df[req.num]))}
    if req.kind == "correlation":
        numeric = roles(prof)["numeric"]
        corr = S.correlation_matrix(df, numeric, method=req.method)
        return {
            "chart": S.corr_heatmap(corr).to_dict(),
            "top_corr": [{"a": a, "b": b, "r": r} for a, b, r in S.top_correlations(corr)],
        }
    raise HTTPException(422, "Не хватает параметров для анализа.")


class AbReq(TableReq):
    kind: str
    col: str | None = None
    a: str | None = None
    b: str | None = None
    popmean: float | None = None
    metric: str | None = None
    group_col: str | None = None
    g1: str | None = None
    g2: str | None = None
    parametric: bool = False
    alternative: str = "two-sided"
    stat: str = "mean"
    s1: int | None = None
    n1: int | None = None
    s2: int | None = None
    n2: int | None = None


@app.post("/api/datasets/{dataset_id}/abtest")
def abtest_endpoint(dataset_id: str, req: AbReq) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, req.table)
    with ds.lock:
        df = _df(ds, t)
    try:
        if req.kind == "one_sample" and req.col and req.popmean is not None:
            return {"result": _native(abtest.one_sample(df[req.col], req.popmean, req.alternative))}
        if req.kind == "paired" and req.a and req.b:
            return {"result": _native(abtest.paired(df[req.a], df[req.b], req.alternative))}
        if req.kind == "two_sample" and req.metric and req.group_col and req.g1 and req.g2:
            a = df[df[req.group_col].astype(str) == req.g1][req.metric]
            b = df[df[req.group_col].astype(str) == req.g2][req.metric]
            return {"result": _native(abtest.two_sample(a, b, req.parametric, req.alternative))}
        if req.kind == "two_proportion" and None not in (req.s1, req.n1, req.s2, req.n2):
            return {"result": _native(abtest.two_proportion(req.s1, req.n1, req.s2, req.n2, req.alternative))}
        if req.kind == "bootstrap" and req.col:
            return {"result": _native(abtest.bootstrap_ci(df[req.col], req.stat))}
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))
    raise HTTPException(422, "Не хватает параметров теста.")


class ProbReq(BaseModel):
    kind: str
    p: float = 0.1
    target: int = 100
    max_risk: float = 0.05
    n: int = 1000
    x: float = 0.0
    direction: str = "<="


@app.post("/api/probability")
def probability_endpoint(req: ProbReq) -> dict:
    if req.kind == "binomial_min_n":
        res = probability.binomial_min_n(req.p, req.target, req.max_risk)
        chart = probability.binomial_chart(res["n"], req.p).to_dict() if res["n"] else None
        return {"result": res, "chart": chart}
    if req.kind == "normal_approx":
        return {"result": probability.normal_approx(req.n, req.p, req.x, req.direction)}
    raise HTTPException(422, "Неизвестный расчёт.")


class TsReq(TableReq):
    date_col: str
    value_col: str
    freq: str = "день"
    agg: str = "sum"
    analysis: str = "decompose"
    window: int = 7
    horizon: int = 7
    method: str = "seasonal_naive"


@app.post("/api/datasets/{dataset_id}/timeseries")
def timeseries_endpoint(dataset_id: str, req: TsReq) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, req.table)
    with ds.lock:
        df = _df(ds, t)
    freq = ts.FREQS.get(req.freq, req.freq)
    try:
        ser = ts.resample_series(df, req.date_col, req.value_col, freq, req.agg)
        period = ts.default_period(freq)
        out = {"table": t, "line": ts.line(ser, req.value_col).to_dict()}
        if req.analysis == "decompose":
            out["chart"] = ts.decompose(ser, period)[1].to_dict()
        elif req.analysis == "rolling":
            out["chart"] = ts.rolling(ser, req.window).to_dict()
        elif req.analysis == "acf":
            out["chart"] = ts.acf_chart(ser).to_dict()
        elif req.analysis == "forecast":
            out["chart"] = ts.forecast(ser, req.horizon, req.method, period)[1].to_dict()
        return out
    except Exception as e:  # noqa: BLE001 — bad column/too-short series → 422
        raise HTTPException(422, f"Не удалось построить ряд: {e}")


class PivotReq(TableReq):
    mode: str = "pivot"
    index: str | None = None
    values: str | None = None
    columns: str | None = None
    aggfunc: str = "mean"
    x: str | None = None
    y: str | None = None
    bins: int = 10
    agg: str = "mean"
    quantile: bool = False


@app.post("/api/datasets/{dataset_id}/pivot")
def pivot_endpoint(dataset_id: str, req: PivotReq) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, req.table)
    with ds.lock:
        df = _df(ds, t)
    try:
        if req.mode == "pivot" and req.index and req.values:
            table, chart = pv.pivot(df, req.index, req.values, req.columns, req.aggfunc)
            return {"rows": _records(table.reset_index()), "chart": chart.to_dict()}
        if req.mode == "binned" and req.x and req.y:
            grouped, chart = pv.binned_relationship(df, req.x, req.y, req.bins, req.agg, req.quantile)
            grouped = grouped.copy()
            grouped["bin"] = grouped["bin"].astype(str)
            return {"rows": _records(grouped), "chart": chart.to_dict()}
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))
    raise HTTPException(422, "Не хватает параметров.")


class CohortReq(TableReq):
    id_col: str
    date_col: str
    value_col: str | None = None
    period: str = "month"
    metric: str = "retention"


@app.post("/api/datasets/{dataset_id}/cohort")
def cohort_endpoint(dataset_id: str, req: CohortReq) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, req.table)
    try:
        with ds.lock:
            res = cohort_analysis(
                ds.con, t, req.id_col, req.date_col, req.value_col, req.period, req.metric
            )
    except ValueError as e:
        raise HTTPException(422, str(e))
    display = res.display.round(1)
    display.columns = [str(c) for c in display.columns]
    return {"chart": res.chart.to_dict(), "rows": _records(display.reset_index())}


class ExplorerReq(TableReq):
    kind: str
    x: str | None = None
    y: str | None = None
    color: str | None = None
    agg: str = "sum"


@app.post("/api/datasets/{dataset_id}/explorer")
def explorer_endpoint(dataset_id: str, req: ExplorerReq) -> dict:
    ds = _dataset(dataset_id)
    t = _pick(ds, req.table)
    with ds.lock:
        df = _df(ds, t)
    try:
        chart = build_custom(df, req.kind, x=req.x, y=req.y, color=req.color, agg=req.agg)
    except (ValueError, KeyError) as e:
        raise HTTPException(422, str(e))
    return {"chart": chart.to_dict()}
