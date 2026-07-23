"use client";

import { useState } from "react";
import { api, Dataset } from "@/lib/api";
import { Check, cols, NumField, RunButton, Select, TablePicker } from "./controls";
import { DataTable } from "./DataTable";
import { VegaChart } from "./VegaChart";
import { Card, ErrorBox, Kpi, SectionHeader, Spinner } from "./ui";

export type PanelProps = { ds: Dataset; provider: string; model: string };

const STATS_LABELS: Record<string, string> = {
  group: "Сравнение групп",
  chi2: "Связь категорий (χ²)",
  normality: "Тест нормальности",
  correlation: "Корреляции",
};
const AB_LABELS: Record<string, string> = {
  one_sample: "Среднее vs порог",
  paired: "Парный тест (до/после)",
  bootstrap: "Bootstrap: доверит. интервал",
  prob: "Сколько нужно наблюдений",
};
const PIVOT_LABELS: Record<string, string> = { pivot: "Сводная таблица", binned: "Связь по бинам" };
const KIND_LABELS: Record<string, string> = {
  bar: "Столбцы",
  line: "Линия",
  area: "Область",
  scatter: "Точки",
  hist: "Гистограмма",
  box: "Ящик с усами",
  pie: "Круговая",
};

/** Dashed placeholder shown before a section is run — tells the user what they'll get. */
function EmptyHint({ show, children }: { show: boolean; children: React.ReactNode }) {
  if (!show) return null;
  return (
    <div className="mt-4 rounded-xl border border-dashed border-border bg-surface/60 p-8 text-center text-sm text-muted">
      {children}
    </div>
  );
}

function fmtVal(v: unknown): string {
  if (typeof v === "boolean") return v ? "да" : "нет";
  if (typeof v === "number") {
    if (v !== 0 && Math.abs(v) < 0.001) return v.toExponential(2);
    return Number.isInteger(v) ? v.toLocaleString("ru-RU") : v.toLocaleString("ru-RU", { maximumFractionDigits: 3 });
  }
  if (v && typeof v === "object") return "";
  return String(v);
}

const HIDE = new Set(["test", "significant", "contingency", "group_medians", "alternative"]);

function StatResult({ r }: { r: Record<string, unknown> }) {
  const sig = r.significant as boolean | undefined;
  return (
    <Card>
      <div className="flex items-center gap-3">
        <span className="font-semibold text-ink">{String(r.test ?? "Результат")}</span>
        {sig !== undefined && (
          <span
            className={`rounded-full px-2 py-0.5 text-xs font-medium ${
              sig ? "bg-red-50 text-red-700" : "bg-emerald-50 text-emerald-700"
            }`}
          >
            {sig ? "значимо (p<0.05)" : "незначимо"}
          </span>
        )}
      </div>
      <dl className="mt-3 grid gap-x-8 gap-y-1 text-sm sm:grid-cols-2">
        {Object.entries(r)
          .filter(([k, v]) => !HIDE.has(k) && (typeof v !== "object" || v === null))
          .map(([k, v]) => (
            <div key={k} className="flex justify-between border-b border-border/50 py-1">
              <span className="text-muted">{k}</span>
              <span className="tnum text-ink">{fmtVal(v)}</span>
            </div>
          ))}
      </dl>
      {!!r.group_medians && typeof r.group_medians === "object" && (
        <div className="mt-3 text-sm">
          <div className="mb-1 text-muted">Медианы по группам</div>
          {Object.entries(r.group_medians as Record<string, number>).map(([g, m]) => (
            <div key={g} className="flex justify-between border-b border-border/50 py-0.5">
              <span>{g}</span>
              <span className="tnum">{fmtVal(m)}</span>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

function usePanel<T>() {
  const [data, setData] = useState<T | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  async function run(fn: () => Promise<T>) {
    setBusy(true);
    setErr(null);
    try {
      setData(await fn());
    } catch (e) {
      setErr((e as Error).message);
      setData(null);
    } finally {
      setBusy(false);
    }
  }
  return { data, busy, err, run };
}

// ---------- Auto-report ----------
export function Report({ ds, provider, model }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const p = usePanel<Awaited<ReturnType<typeof api.report>>>();
  return (
    <div>
      <SectionHeader title="Авто-отчёт" desc="Находки классическими методами + формулировка LLM." />
      <div className="flex items-end gap-3">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <RunButton busy={p.busy} onClick={() => p.run(() => api.report(ds.id, { table, provider, model }))}>
          Построить отчёт
        </RunButton>
      </div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data && (
        <div className="mt-4 space-y-4">
          <Card>
            <div className="whitespace-pre-wrap text-sm text-ink">{p.data.narrative}</div>
          </Card>
          {p.data.findings.map((f, i) => (
            <Card key={i}>
              <div className="text-sm text-ink">
                <span className="font-semibold text-accent-ink">[{f.kind}]</span> {f.text}
              </div>
              {f.chart && <div className="mt-3"><VegaChart spec={f.chart} /></div>}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

// ---------- Cleaning ----------
export function Cleaning({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const p = usePanel<Awaited<ReturnType<typeof api.cleaning>>>();
  const d = p.data;
  return (
    <div>
      <SectionHeader title="Очистка данных" desc="Дубли, неявные дубли, аномалии, пропуски, типы." />
      <div className="flex items-end gap-3">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <RunButton busy={p.busy} onClick={() => p.run(() => api.cleaning(ds.id, table))}>
          Проверить
        </RunButton>
      </div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {d && (
        <div className="mt-4 space-y-5">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            <Kpi label="Строк" value={d.n_rows.toLocaleString("ru-RU")} />
            <Kpi label="Дубликаты строк" value={d.duplicate_rows} />
            <Kpi label="Проблемных" value={d.missing.length + d.anomalies.length + d.implicit_dups.length + d.dtype_suggestions.length} />
          </div>
          {d.missing.length > 0 && <Sub title="Пропуски"><DataTable columns={Object.keys(d.missing[0])} rows={d.missing} /></Sub>}
          {d.anomalies.length > 0 && <Sub title="Аномалии (IQR)"><DataTable columns={Object.keys(d.anomalies[0])} rows={d.anomalies} /></Sub>}
          {d.dtype_suggestions.length > 0 && <Sub title="Типы данных"><DataTable columns={Object.keys(d.dtype_suggestions[0])} rows={d.dtype_suggestions} /></Sub>}
          {d.implicit_dups.length > 0 && (
            <Sub title="Неявные дубликаты категорий">
              {d.implicit_dups.map((g) => (
                <div key={g.column} className="mb-2">
                  <div className="text-sm font-medium text-ink">{g.column}</div>
                  {g.groups.map((grp, i) => (
                    <div key={i} className="text-sm text-text">{grp.join(" ≈ ")}</div>
                  ))}
                </div>
              ))}
            </Sub>
          )}
        </div>
      )}
    </div>
  );
}

function Sub({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div>
      <h3 className="mb-2 text-lg font-semibold">{title}</h3>
      {children}
    </div>
  );
}

// ---------- Drivers ----------
export function Drivers({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const c = cols(ds, table);
  const [target, setTarget] = useState(c.numeric[0] ?? "");
  const p = usePanel<Awaited<ReturnType<typeof api.drivers>>>();
  return (
    <div>
      <SectionHeader title="Драйверы" desc="Что сильнее всего связано с выбранным показателем." />
      <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-4">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <Select label="Таргет (число)" value={target} onChange={setTarget} options={c.numeric} />
        <div><RunButton busy={p.busy} onClick={() => p.run(() => api.drivers(ds.id, { table, target }))}>Найти драйверы</RunButton></div>
      </div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data && (
        <div className="mt-4 space-y-3">
          {p.data.drivers.map((d) => (
            <Card key={d.feature}>
              <div className="text-sm text-ink">
                <span className="font-semibold">{d.feature}</span> · {d.kind} · сила{" "}
                <span className="tnum">{d.strength.toFixed(2)}</span> ({d.detail})
              </div>
              {d.chart && <div className="mt-3"><VegaChart spec={d.chart} /></div>}
            </Card>
          ))}
          {p.data.drivers.length === 0 && <Card>Значимых драйверов не найдено.</Card>}
        </div>
      )}
    </div>
  );
}

// ---------- Stats ----------
export function Stats({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const c = cols(ds, table);
  const [kind, setKind] = useState("group");
  const [num, setNum] = useState(c.numeric[0] ?? "");
  const [cat, setCat] = useState(c.categorical[0] ?? "");
  const [cat1, setCat1] = useState(c.categorical[0] ?? "");
  const [cat2, setCat2] = useState(c.categorical[1] ?? c.categorical[0] ?? "");
  const [method, setMethod] = useState("pearson");
  const [parametric, setParametric] = useState(false);
  const p = usePanel<Awaited<ReturnType<typeof api.stats>>>();

  function run() {
    const body: Record<string, unknown> = { table, kind };
    if (kind === "group") Object.assign(body, { num, cat, parametric });
    if (kind === "chi2") Object.assign(body, { cat1, cat2 });
    if (kind === "normality") Object.assign(body, { num });
    if (kind === "correlation") Object.assign(body, { method });
    p.run(() => api.stats(ds.id, body));
  }

  return (
    <div>
      <SectionHeader title="Статистика" desc="Сравнение групп, связь категорий, нормальность, корреляции." />
      <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-4">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <Select label="Анализ" value={kind} onChange={setKind} options={["group", "chi2", "normality", "correlation"]} labels={STATS_LABELS} />
        {kind === "group" && <><Select label="Число" value={num} onChange={setNum} options={c.numeric} /><Select label="Группа" value={cat} onChange={setCat} options={c.categorical} /></>}
        {kind === "chi2" && <><Select label="Категория 1" value={cat1} onChange={setCat1} options={c.categorical} /><Select label="Категория 2" value={cat2} onChange={setCat2} options={c.categorical} /></>}
        {kind === "normality" && <Select label="Число" value={num} onChange={setNum} options={c.numeric} />}
        {kind === "correlation" && <Select label="Метод" value={method} onChange={setMethod} options={["pearson", "spearman"]} />}
        <div className="flex items-center gap-3">
          {kind === "group" && <Check label="Параметрич." checked={parametric} onChange={setParametric} />}
          <RunButton busy={p.busy} onClick={run}>Посчитать</RunButton>
        </div>
      </div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data && (
        <div className="mt-4 space-y-4">
          {p.data.result && <StatResult r={p.data.result} />}
          {p.data.chart && <Card><VegaChart spec={p.data.chart} />{p.data.top_corr && <p className="mt-2 text-sm text-muted">Топ: {p.data.top_corr.slice(0, 5).map((t) => `${t.a}↔${t.b} ${t.r.toFixed(2)}`).join(", ")}</p>}</Card>}
          {p.data.result?.contingency !== undefined && Array.isArray(p.data.result.contingency) && (
            <Sub title="Таблица сопряжённости"><DataTable columns={Object.keys((p.data.result.contingency as Record<string, unknown>[])[0] ?? {})} rows={p.data.result.contingency as Record<string, unknown>[]} /></Sub>
          )}
        </div>
      )}
    </div>
  );
}

// ---------- A/B ----------
export function AbTest({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const c = cols(ds, table);
  const [kind, setKind] = useState("one_sample");
  const [col, setCol] = useState(c.numeric[0] ?? "");
  const [popmean, setPopmean] = useState(0);
  const [a, setA] = useState(c.numeric[0] ?? "");
  const [b, setB] = useState(c.numeric[1] ?? c.numeric[0] ?? "");
  const [metric, setMetric] = useState(c.numeric[0] ?? "");
  const [groupCol, setGroupCol] = useState(c.categorical[0] ?? "");
  const [prob, setProb] = useState({ p: 0.1, target: 100, max_risk: 0.05 });
  const p = usePanel<Awaited<ReturnType<typeof api.abtest>>>();

  function run() {
    if (kind === "prob") {
      p.run(() => api.probability({ kind: "binomial_min_n", ...prob }));
      return;
    }
    const body: Record<string, unknown> = { table, kind };
    if (kind === "one_sample") Object.assign(body, { col, popmean });
    if (kind === "paired") Object.assign(body, { a, b });
    if (kind === "two_sample") Object.assign(body, { metric, group_col: groupCol, g1: "", g2: "" });
    if (kind === "bootstrap") Object.assign(body, { col, stat: "mean" });
    p.run(() => api.abtest(ds.id, body));
  }

  return (
    <div>
      <SectionHeader title="A/B и гипотезы" desc="Стат-тесты, bootstrap, распределения." />
      <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-4">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <Select label="Тест" value={kind} onChange={setKind} options={["one_sample", "paired", "bootstrap", "prob"]} labels={AB_LABELS} />
        {kind === "one_sample" && <><Select label="Колонка" value={col} onChange={setCol} options={c.numeric} /><NumField label="Порог" value={popmean} onChange={setPopmean} /></>}
        {kind === "paired" && <><Select label="До" value={a} onChange={setA} options={c.numeric} /><Select label="После" value={b} onChange={setB} options={c.numeric} /></>}
        {kind === "bootstrap" && <Select label="Колонка" value={col} onChange={setCol} options={c.numeric} />}
        {kind === "prob" && <><NumField label="p" value={prob.p} step={0.01} onChange={(v) => setProb({ ...prob, p: v })} /><NumField label="Успехов" value={prob.target} onChange={(v) => setProb({ ...prob, target: v })} /><NumField label="Риск" value={prob.max_risk} step={0.01} onChange={(v) => setProb({ ...prob, max_risk: v })} /></>}
        <div><RunButton busy={p.busy} onClick={run}>Посчитать</RunButton></div>
      </div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data && (
        <div className="mt-4 space-y-4">
          {p.data.result && <StatResult r={p.data.result} />}
          {p.data.chart && <Card><VegaChart spec={p.data.chart} /></Card>}
        </div>
      )}
    </div>
  );
}

// ---------- Time-series ----------
const ANALYSIS = [["decompose", "Декомпозиция"], ["rolling", "Скользящие"], ["acf", "Автокорреляция"], ["forecast", "Прогноз"]];
export function TimeSeries({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const c = cols(ds, table);
  const dateCols = c.temporal.length ? c.temporal : c.all;
  const [dateCol, setDateCol] = useState(dateCols[0] ?? "");
  const [valueCol, setValueCol] = useState(c.numeric[0] ?? "");
  const [freq, setFreq] = useState("день");
  const [analysisLabel, setAnalysisLabel] = useState("Декомпозиция");
  const p = usePanel<Awaited<ReturnType<typeof api.timeseries>>>();

  function run() {
    const analysis = ANALYSIS.find((x) => x[1] === analysisLabel)?.[0] ?? "decompose";
    p.run(() => api.timeseries(ds.id, { table, date_col: dateCol, value_col: valueCol, freq, agg: "sum", analysis }));
  }

  return (
    <div>
      <SectionHeader title="Временные ряды" desc="Ресемплинг, декомпозиция, автокорреляция, прогноз." />
      <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-5">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <Select label="Дата" value={dateCol} onChange={setDateCol} options={dateCols} />
        <Select label="Значение" value={valueCol} onChange={setValueCol} options={c.numeric} />
        <Select label="Частота" value={freq} onChange={setFreq} options={["час", "день", "неделя", "месяц"]} />
        <Select label="Анализ" value={analysisLabel} onChange={setAnalysisLabel} options={ANALYSIS.map((x) => x[1])} />
      </div>
      <div className="mt-3"><RunButton busy={p.busy} onClick={run}>Построить</RunButton></div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data && (
        <div className="mt-4 space-y-4">
          {p.data.line && <Card><VegaChart spec={p.data.line} /></Card>}
          {p.data.chart && <Card><VegaChart spec={p.data.chart} /></Card>}
        </div>
      )}
    </div>
  );
}

// ---------- Pivot ----------
export function Pivot({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const c = cols(ds, table);
  const [mode, setMode] = useState("pivot");
  const [index, setIndex] = useState(c.categorical[0] ?? "");
  const [values, setValues] = useState(c.numeric[0] ?? "");
  const [aggfunc, setAggfunc] = useState("mean");
  const [x, setX] = useState(c.numeric[0] ?? "");
  const [y, setY] = useState(c.numeric[1] ?? c.numeric[0] ?? "");
  const [bins, setBins] = useState(10);
  const p = usePanel<Awaited<ReturnType<typeof api.pivot>>>();

  function run() {
    const body: Record<string, unknown> =
      mode === "pivot"
        ? { table, mode, index, values, aggfunc }
        : { table, mode: "binned", x, y, bins, agg: "mean" };
    p.run(() => api.pivot(ds.id, body));
  }

  return (
    <div>
      <SectionHeader title="Сводные" desc="Сводные таблицы и связь по бинам." />
      <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-5">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <Select label="Режим" value={mode} onChange={setMode} options={["pivot", "binned"]} labels={PIVOT_LABELS} />
        {mode === "pivot" && <><Select label="Строки" value={index} onChange={setIndex} options={c.categorical} /><Select label="Значение" value={values} onChange={setValues} options={c.numeric} /><Select label="Агрегат" value={aggfunc} onChange={setAggfunc} options={["mean", "sum", "count", "median", "min", "max"]} /></>}
        {mode === "binned" && <><Select label="X" value={x} onChange={setX} options={c.numeric} /><Select label="Y" value={y} onChange={setY} options={c.numeric} /><NumField label="Бинов" value={bins} onChange={setBins} /></>}
      </div>
      <div className="mt-3"><RunButton busy={p.busy} onClick={run}>Построить</RunButton></div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data && (
        <div className="mt-4 space-y-4">
          {p.data.chart && <Card><VegaChart spec={p.data.chart} /></Card>}
          {p.data.rows && p.data.rows.length > 0 && <DataTable columns={Object.keys(p.data.rows[0])} rows={p.data.rows} />}
        </div>
      )}
    </div>
  );
}

// ---------- Cohort ----------
const PERIODS = [["месяц", "month"], ["неделя", "week"], ["день", "day"]];
export function Cohort({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const c = cols(ds, table);
  const [idCol, setIdCol] = useState(c.categorical[0] ?? "");
  const [dateCol, setDateCol] = useState((c.temporal[0] ?? c.all[0]) ?? "");
  const [periodLabel, setPeriodLabel] = useState("месяц");
  const p = usePanel<Awaited<ReturnType<typeof api.cohort>>>();

  function run() {
    const period = PERIODS.find((x) => x[0] === periodLabel)?.[1] ?? "month";
    p.run(() => api.cohort(ds.id, { table, id_col: idCol, date_col: dateCol, period, metric: "retention" }));
  }

  return (
    <div>
      <SectionHeader title="Когорты" desc="Удержание по периоду первой активности." />
      <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-4">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <Select label="Идентификатор" value={idCol} onChange={setIdCol} options={c.categorical} />
        <Select label="Дата" value={dateCol} onChange={setDateCol} options={c.all} />
        <Select label="Период" value={periodLabel} onChange={setPeriodLabel} options={["месяц", "неделя", "день"]} />
      </div>
      <div className="mt-3"><RunButton busy={p.busy} onClick={run}>Построить когорты</RunButton></div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data && (
        <div className="mt-4 space-y-4">
          {p.data.chart && <Card><VegaChart spec={p.data.chart} /></Card>}
          {p.data.rows && p.data.rows.length > 0 && <DataTable columns={Object.keys(p.data.rows[0])} rows={p.data.rows} max={30} />}
        </div>
      )}
    </div>
  );
}

// ---------- Explorer ----------
export function Explorer({ ds }: PanelProps) {
  const [table, setTable] = useState(ds.tables[0].name);
  const c = cols(ds, table);
  const none = "—";
  const [kind, setKind] = useState("bar");
  const [x, setX] = useState(c.all[0] ?? "");
  const [y, setY] = useState(c.numeric[0] ?? "");
  const [color, setColor] = useState(none);
  const [agg, setAgg] = useState("sum");
  const p = usePanel<Awaited<ReturnType<typeof api.explorer>>>();

  function run() {
    p.run(() =>
      api.explorer(ds.id, {
        table,
        kind,
        x: x === none ? null : x,
        y: y === none ? null : y,
        color: color === none ? null : color,
        agg,
      }),
    );
  }

  return (
    <div>
      <SectionHeader title="Конструктор" desc="Собери график вручную." />
      <div className="grid grid-cols-2 items-end gap-3 sm:grid-cols-6">
        <TablePicker ds={ds} table={table} setTable={setTable} />
        <Select label="Тип" value={kind} onChange={setKind} options={["bar", "line", "area", "scatter", "hist", "box", "pie"]} labels={KIND_LABELS} />
        <Select label="X" value={x} onChange={setX} options={[none, ...c.all]} />
        <Select label="Y" value={y} onChange={setY} options={[none, ...c.all]} />
        <Select label="Цвет" value={color} onChange={setColor} options={[none, ...c.all]} />
        <Select label="Агрегат" value={agg} onChange={setAgg} options={["none", "sum", "mean", "median", "count", "min", "max"]} />
      </div>
      <div className="mt-3"><RunButton busy={p.busy} onClick={run}>Построить</RunButton></div>
      {p.err && <div className="mt-4"><ErrorBox>{p.err}</ErrorBox></div>}
      {p.data?.chart && <div className="mt-4"><Card><VegaChart spec={p.data.chart} /></Card></div>}
    </div>
  );
}
