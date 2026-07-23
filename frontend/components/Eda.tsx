"use client";

import { useEffect, useState } from "react";
import { api, EdaResponse } from "@/lib/api";
import { DataTable } from "./DataTable";
import { VegaChart } from "./VegaChart";
import { Card, ErrorBox, Kpi, SectionHeader, Spinner } from "./ui";

export function Eda({ id, tables }: { id: string; tables: string[] }) {
  const [table, setTable] = useState(tables[0]);
  const [data, setData] = useState<EdaResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    setData(null);
    setErr(null);
    api.eda(id, table).then(setData).catch((e) => setErr((e as Error).message));
  }, [id, table]);

  return (
    <div>
      <div className="mb-5 flex items-end justify-between gap-4">
        <SectionHeader title="Разведка (EDA)" desc="Обзор, статистика, распределения, корреляции." />
        {tables.length > 1 && (
          <select
            value={table}
            onChange={(e) => setTable(e.target.value)}
            className="mb-1 rounded-lg border border-border bg-surface px-3 py-1.5 text-sm"
          >
            {tables.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        )}
      </div>

      {err && <ErrorBox>{err}</ErrorBox>}
      {!data && !err && <Spinner label="Считаю…" />}

      {data && (
        <>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Kpi label="Строк" value={data.overview.rows.toLocaleString("ru-RU")} />
            <Kpi label="Колонок" value={data.overview.columns} />
            <Kpi label="Пропуски" value={`${data.overview["missing_cells_%"]}%`} />
            <Kpi label="Дубликаты" value={data.overview.duplicate_rows} />
          </div>
          <p className="mt-2 text-sm text-muted">
            Числовых {data.overview.numeric} · категориальных {data.overview.categorical} · временных{" "}
            {data.overview.temporal}
          </p>

          <h3 className="mt-7 mb-3 text-lg font-semibold">Описательная статистика</h3>
          <DataTable
            columns={data.describe.length ? Object.keys(data.describe[0]) : []}
            rows={data.describe}
          />

          {data.corr_chart && (
            <>
              <h3 className="mt-8 mb-3 text-lg font-semibold">Корреляции</h3>
              <Card>
                <VegaChart spec={data.corr_chart} />
                {data.top_corr.length > 0 && (
                  <p className="mt-2 text-sm text-muted">
                    Топ связей:{" "}
                    {data.top_corr
                      .slice(0, 5)
                      .map((t) => `${t.a}↔${t.b} r=${t.r.toFixed(2)}`)
                      .join(", ")}
                  </p>
                )}
              </Card>
            </>
          )}

          {data.univariate.length > 0 && (
            <>
              <h3 className="mt-8 mb-3 text-lg font-semibold">Распределения</h3>
              <div className="grid gap-4 md:grid-cols-2">
                {data.univariate.map((u) => (
                  <Card key={u.name}>
                    <div className="mb-1 text-sm font-medium text-ink">{u.name}</div>
                    <VegaChart spec={u.chart} />
                  </Card>
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
