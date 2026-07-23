"use client";

import { useRef, useState } from "react";
import { api, Dataset } from "@/lib/api";
import { Chat } from "@/components/Chat";
import { DataTable } from "@/components/DataTable";
import { Eda } from "@/components/Eda";
import { MergeControl } from "@/components/MergeControl";
import { SectionKey } from "@/components/nav";
import {
  AbTest,
  Cleaning,
  Cohort,
  Drivers,
  Explorer,
  Pivot,
  Report,
  Stats,
  TimeSeries,
} from "@/components/panels";
import { QuickStart } from "@/components/QuickStart";
import { Sidebar } from "@/components/Sidebar";
import { ErrorBox } from "@/components/ui";

export default function Home() {
  const [ds, setDs] = useState<Dataset | null>(null);
  const [active, setActive] = useState<SectionKey>("chat");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [provider, setProvider] = useState("openrouter");
  const [model, setModel] = useState("openrouter/free");
  const [showQuickStart, setShowQuickStart] = useState(true);
  const addRef = useRef<HTMLInputElement>(null);

  async function run(fn: () => Promise<Dataset>, resetActive = false) {
    setBusy(true);
    setErr(null);
    try {
      setDs(await fn());
      if (resetActive) setActive("chat");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  /** First file creates the dataset, the rest are added as extra tables. */
  async function uploadFiles(files: File[]) {
    setBusy(true);
    setErr(null);
    try {
      let next = await api.upload(files[0]);
      for (const f of files.slice(1)) next = await api.addTable(next.id, f);
      setDs(next);
      setActive("chat");
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex">
      <Sidebar
        active={active}
        onSelect={setActive}
        onDemo={() => run(api.demo, true)}
        onUpload={uploadFiles}
        busy={busy}
        provider={provider}
        model={model}
        onProvider={setProvider}
        onModel={setModel}
      />

      <main className="min-w-0 flex-1 px-8 py-7">
        <div className="mx-auto max-w-[1200px]">
          {!ds ? (
            <div className="mx-auto mt-[14vh] max-w-xl text-center">
              <h1 className="text-3xl font-bold text-ink">Аналитика данных на русском</h1>
              <p className="mt-3 text-muted">
                Загрузите один или несколько связанных файлов (CSV, XLSX, Parquet, JSON) слева —
                или нажмите «Демо-данные», чтобы посмотреть на примере продаж и клиентов.
              </p>
              <button
                onClick={() => run(api.demo, true)}
                disabled={busy}
                className="mt-6 rounded-lg bg-accent px-6 py-2.5 text-sm font-semibold text-white hover:bg-accent-ink disabled:opacity-50"
              >
                {busy ? "Загрузка…" : "Попробовать на демо-данных"}
              </button>
              {err && (
                <div className="mt-4 text-left">
                  <ErrorBox>{err}</ErrorBox>
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="mb-6 flex flex-wrap items-center gap-2 rounded-xl border border-border bg-surface px-4 py-3">
                {ds.tables.map((t) => (
                  <span
                    key={t.name}
                    className="inline-flex items-center gap-1.5 rounded-lg bg-bg px-2.5 py-1 text-sm"
                  >
                    <span className="font-semibold text-ink">{t.name}</span>
                    <span className="text-muted">{t.nrows.toLocaleString("ru-RU")}</span>
                  </span>
                ))}
                <button
                  onClick={() => addRef.current?.click()}
                  disabled={busy}
                  className="ml-auto rounded-lg border border-border px-2.5 py-1 text-sm text-muted hover:border-accent hover:text-accent disabled:opacity-50"
                >
                  + таблица
                </button>
                <input
                  ref={addRef}
                  type="file"
                  accept=".csv,.tsv,.parquet,.json,.jsonl,.ndjson,.xlsx,.xls"
                  className="hidden"
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f && ds) run(() => api.addTable(ds.id, f));
                    e.target.value = "";
                  }}
                />
                <MergeControl ds={ds} onMerged={setDs} />
              </div>

              {err && (
                <div className="mb-4">
                  <ErrorBox>{err}</ErrorBox>
                </div>
              )}

              {showQuickStart && (
                <QuickStart
                  multiTable={ds.tables.length > 1}
                  onDismiss={() => setShowQuickStart(false)}
                  onGo={(k) => {
                    setActive(k);
                    setShowQuickStart(false);
                  }}
                />
              )}

              {active === "chat" && <Chat id={ds.id} provider={provider} model={model} />}
              {active === "eda" && <Eda id={ds.id} tables={ds.tables.map((t) => t.name)} />}
              {active === "report" && <Report ds={ds} provider={provider} model={model} />}
              {active === "stats" && <Stats ds={ds} provider={provider} model={model} />}
              {active === "drivers" && <Drivers ds={ds} provider={provider} model={model} />}
              {active === "cleaning" && <Cleaning ds={ds} provider={provider} model={model} />}
              {active === "ab" && <AbTest ds={ds} provider={provider} model={model} />}
              {active === "ts" && <TimeSeries ds={ds} provider={provider} model={model} />}
              {active === "pivot" && <Pivot ds={ds} provider={provider} model={model} />}
              {active === "cohort" && <Cohort ds={ds} provider={provider} model={model} />}
              {active === "explorer" && <Explorer ds={ds} provider={provider} model={model} />}

              <details className="mt-8 text-sm">
                <summary className="cursor-pointer text-muted hover:text-text">
                  Таблицы и первые строки
                </summary>
                <div className="mt-3 space-y-5">
                  {ds.tables.map((t) => (
                    <div key={t.name}>
                      <div className="mb-2 text-sm font-medium text-ink">{t.name}</div>
                      <DataTable
                        columns={t.columns.map((c) => c.name)}
                        rows={t.sample}
                        max={10}
                      />
                    </div>
                  ))}
                </div>
              </details>
            </>
          )}
        </div>
      </main>
    </div>
  );
}
