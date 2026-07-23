"use client";

import { Dataset } from "@/lib/api";

export function cols(ds: Dataset, table: string) {
  const t = ds.tables.find((x) => x.name === table) ?? ds.tables[0];
  return {
    numeric: t.roles.numeric,
    categorical: t.roles.categorical,
    temporal: t.roles.temporal,
    all: t.columns.map((c) => c.name),
  };
}

export function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-muted">{label}</span>
      {children}
    </label>
  );
}

const inputCls =
  "w-full rounded-lg border border-border bg-surface px-2.5 py-1.5 text-sm outline-none focus:border-accent focus:ring-2 focus:ring-accent-weak";

export function Select({
  label,
  value,
  onChange,
  options,
  labels,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: string[];
  labels?: Record<string, string>;
}) {
  return (
    <Field label={label}>
      <select value={value} onChange={(e) => onChange(e.target.value)} className={inputCls}>
        {options.map((o) => (
          <option key={o} value={o}>
            {labels?.[o] ?? o}
          </option>
        ))}
      </select>
    </Field>
  );
}

/** Muted helper text under a form — what the section does / an example. */
export function Hint({ children }: { children: React.ReactNode }) {
  return <p className="mt-3 text-sm text-muted">{children}</p>;
}

export function NumField({
  label,
  value,
  onChange,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  step?: number;
}) {
  return (
    <Field label={label}>
      <input
        type="number"
        value={value}
        step={step}
        onChange={(e) => onChange(Number(e.target.value))}
        className={inputCls}
      />
    </Field>
  );
}

export function Check({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center gap-2 text-sm text-text">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {label}
    </label>
  );
}

export function RunButton({
  onClick,
  busy,
  children,
}: {
  onClick: () => void;
  busy?: boolean;
  children: React.ReactNode;
}) {
  return (
    <button
      onClick={onClick}
      disabled={busy}
      className="rounded-lg bg-accent px-5 py-2 text-sm font-semibold text-white hover:bg-accent-ink disabled:opacity-50"
    >
      {busy ? "Считаю…" : children}
    </button>
  );
}

export function TablePicker({
  ds,
  table,
  setTable,
}: {
  ds: Dataset;
  table: string;
  setTable: (t: string) => void;
}) {
  if (ds.tables.length < 2) return null;
  return (
    <div className="w-48">
      <Select label="Таблица" value={table} onChange={setTable} options={ds.tables.map((t) => t.name)} />
    </div>
  );
}
