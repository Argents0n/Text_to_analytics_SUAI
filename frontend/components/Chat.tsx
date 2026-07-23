"use client";

import { useState } from "react";
import { api, ChatResponse } from "@/lib/api";
import { DataTable } from "./DataTable";
import { VegaChart } from "./VegaChart";
import { Card, ErrorBox, SectionHeader, Spinner } from "./ui";

const EXAMPLES = ["выручка по категориям", "динамика выручки по месяцам", "топ-5 клиентов по сумме"];

export function Chat({ id, provider, model }: { id: string; provider: string; model: string }) {
  const [q, setQ] = useState("");
  const [loading, setLoading] = useState(false);
  const [res, setRes] = useState<ChatResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function ask(question: string) {
    if (!question.trim()) return;
    setLoading(true);
    setErr(null);
    try {
      setRes(await api.chat(id, question, provider, model));
    } catch (e) {
      setErr((e as Error).message);
      setRes(null);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <SectionHeader title="Чат" desc="Вопрос на русском → SQL → таблица и график." />

      <Card>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            ask(q);
          }}
          className="flex gap-2"
        >
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="напр. выручка по категориям"
            className="flex-1 rounded-lg border border-border bg-surface px-3 py-2 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-weak"
          />
          <button
            type="submit"
            disabled={loading}
            className="rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-ink disabled:opacity-50"
          >
            Спросить
          </button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          {EXAMPLES.map((ex) => (
            <button
              key={ex}
              onClick={() => {
                setQ(ex);
                ask(ex);
              }}
              className="rounded-full border border-border px-3 py-1 text-xs text-muted hover:border-accent hover:text-accent"
            >
              {ex}
            </button>
          ))}
        </div>
      </Card>

      <div className="mt-4">
        {loading && <Spinner label="Генерирую SQL…" />}
        {err && <ErrorBox>{err}</ErrorBox>}
        {res && !loading && (
          <div className="space-y-4">
            {res.answer && <p className="text-[15px] text-ink">{res.answer}</p>}
            {res.chart && (
              <Card>
                <VegaChart spec={res.chart} />
              </Card>
            )}
            <DataTable columns={res.columns} rows={res.rows} />
            <details className="text-sm">
              <summary className="cursor-pointer text-muted hover:text-text">
                SQL · попыток: {res.attempts}
              </summary>
              <pre className="mt-2 overflow-x-auto rounded-lg border border-border bg-surface p-3 text-xs tnum">
                {res.sql}
              </pre>
            </details>
          </div>
        )}
      </div>
    </div>
  );
}
