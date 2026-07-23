"use client";

import { useState } from "react";
import { api, Dataset } from "@/lib/api";
import { Select } from "./controls";

export function MergeControl({ ds, onMerged }: { ds: Dataset; onMerged: (d: Dataset) => void }) {
  const [open, setOpen] = useState(false);
  const [left, setLeft] = useState(ds.tables[0].name);
  const [right, setRight] = useState(ds.tables[1]?.name ?? ds.tables[0].name);
  const [on, setOn] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  if (ds.tables.length < 2) return null;

  const lc = ds.tables.find((t) => t.name === left)?.columns.map((c) => c.name) ?? [];
  const rc = ds.tables.find((t) => t.name === right)?.columns.map((c) => c.name) ?? [];
  const shared = lc.filter((c) => rc.includes(c));
  const key = shared.includes(on) ? on : (shared[0] ?? "");

  async function merge() {
    setBusy(true);
    setErr(null);
    try {
      onMerged(await api.merge(ds.id, { left, right, on: key, how: "left" }));
      setOpen(false);
    } catch (e) {
      setErr((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen((o) => !o)}
        className="rounded-lg border border-border px-2.5 py-1 text-sm text-muted hover:border-accent hover:text-accent"
      >
        ⋈ объединить
      </button>
      {open && (
        <div className="mt-3 flex w-full flex-wrap items-end gap-3 rounded-xl border border-border bg-bg/50 p-3">
          <div className="w-40"><Select label="Левая" value={left} onChange={setLeft} options={ds.tables.map((t) => t.name)} /></div>
          <div className="w-40"><Select label="Правая" value={right} onChange={setRight} options={ds.tables.map((t) => t.name)} /></div>
          <div className="w-40"><Select label="Ключ (общая колонка)" value={key} onChange={setOn} options={shared.length ? shared : ["нет общих"]} /></div>
          <button
            onClick={merge}
            disabled={busy || shared.length === 0}
            className="rounded-lg bg-accent px-4 py-1.5 text-sm font-semibold text-white hover:bg-accent-ink disabled:opacity-50"
          >
            {busy ? "…" : "Объединить"}
          </button>
          {shared.length === 0 && <span className="text-sm text-muted">нет общих колонок</span>}
          {err && <span className="text-sm text-red-600">{err}</span>}
        </div>
      )}
    </>
  );
}
