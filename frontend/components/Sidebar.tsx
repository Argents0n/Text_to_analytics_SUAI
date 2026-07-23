"use client";

import { useRef } from "react";
import { NAV, SectionKey } from "./nav";

/** Minimal 1.5px line icons (Lucide-style) — one per section, no emoji. */
function NavIcon({ k }: { k: SectionKey }) {
  const p = {
    chat: <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />,
    eda: (
      <>
        <circle cx="11" cy="11" r="7" />
        <path d="M21 21l-4.3-4.3" />
      </>
    ),
    report: (
      <>
        <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z" />
        <path d="M14 3v6h6M8 13h8M8 17h5" />
      </>
    ),
    stats: <path d="M22 12h-4l-3 8L9 4l-3 8H2" />,
    drivers: (
      <>
        <circle cx="12" cy="12" r="9" />
        <circle cx="12" cy="12" r="4" />
      </>
    ),
    cleaning: <path d="M22 3H2l8 9.46V19l4 2v-8.54z" />,
    ab: (
      <>
        <path d="M9 3v6l-5 9a2 2 0 0 0 2 3h12a2 2 0 0 0 2-3l-5-9V3" />
        <path d="M9 3h6M6.5 15h11" />
      </>
    ),
    ts: (
      <>
        <path d="M22 7l-8 8-4-4-8 8" />
        <path d="M17 7h5v5" />
      </>
    ),
    pivot: <path d="M3 4h18v16H3zM3 10h18M3 15h18M9 4v16" />,
    cohort: (
      <>
        <circle cx="9" cy="8" r="3.5" />
        <path d="M2 20v-1.5A4.5 4.5 0 0 1 6.5 14h5A4.5 4.5 0 0 1 16 18.5V20M17 14.2a4.5 4.5 0 0 1 5 4.3V20" />
      </>
    ),
    explorer: <path d="M4 21v-6M4 11V3M12 21v-9M12 8V3M20 21v-4M20 13V3M1 15h6M9 8h6M17 17h6" />,
  }[k];
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
      aria-hidden
    >
      {p}
    </svg>
  );
}

function Logo() {
  return (
    <svg width="26" height="26" viewBox="0 0 24 24" fill="none" aria-hidden>
      <rect x="2" y="13" width="4.2" height="9" rx="1.2" fill="#A5B4FC" />
      <rect x="9.9" y="7" width="4.2" height="15" rx="1.2" fill="#6366F1" />
      <rect x="17.8" y="3" width="4.2" height="19" rx="1.2" fill="#4338CA" />
    </svg>
  );
}

export function Sidebar({
  active,
  onSelect,
  onDemo,
  onUpload,
  busy,
  provider,
  model,
  onProvider,
  onModel,
}: {
  active: SectionKey;
  onSelect: (k: SectionKey) => void;
  onDemo: () => void;
  onUpload: (files: File[]) => void;
  busy: boolean;
  provider: string;
  model: string;
  onProvider: (v: string) => void;
  onModel: (v: string) => void;
}) {
  const fileRef = useRef<HTMLInputElement>(null);

  return (
    <aside className="w-64 shrink-0 border-r border-border bg-surface flex flex-col h-dvh sticky top-0">
      <div className="flex items-center gap-2.5 px-4 pt-5 pb-4">
        <Logo />
        <div>
          <div className="font-bold text-ink text-[15px] leading-tight tracking-tight">Text-to-Analytics</div>
          <div className="text-[11px] text-muted mt-0.5">аналитика данных на русском</div>
        </div>
      </div>

      <nav className="px-3 flex-1 overflow-y-auto">
        <div className="px-2 pt-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
          Разделы
        </div>
        {NAV.map((item) => {
          const on = item.key === active;
          return (
            <button
              key={item.key}
              onClick={() => onSelect(item.key)}
              className={`group flex w-full items-center justify-between rounded-lg px-3 py-2 text-sm transition-colors ${
                on
                  ? "bg-accent-weak text-accent-ink font-semibold"
                  : "text-text hover:bg-bg font-medium"
              }`}
            >
              <span className="flex items-center gap-2.5">
                <span className={on ? "text-accent" : "text-muted"}>
                  <NavIcon k={item.key} />
                </span>
                {item.label}
              </span>
            </button>
          );
        })}
      </nav>

      <div className="px-3 pb-4 border-t border-border pt-3">
        <div className="px-2 pb-1.5 text-[11px] font-semibold uppercase tracking-wider text-muted">
          Данные
        </div>
        <button
          onClick={onDemo}
          disabled={busy}
          className="w-full rounded-lg bg-accent text-white text-sm font-semibold py-2 hover:bg-accent-ink disabled:opacity-50 transition-colors"
        >
          {busy ? "Загрузка…" : "Демо-данные"}
        </button>
        <button
          onClick={() => fileRef.current?.click()}
          disabled={busy}
          className="mt-2 w-full rounded-lg border border-border text-sm font-medium py-2 hover:border-accent hover:text-accent disabled:opacity-50 transition-colors"
        >
          Загрузить файлы
        </button>
        <p className="mt-1.5 px-1 text-[11px] text-muted">Можно выбрать несколько связанных файлов сразу</p>
        <input
          ref={fileRef}
          type="file"
          multiple
          accept=".csv,.tsv,.parquet,.json,.jsonl,.ndjson,.xlsx,.xls"
          className="hidden"
          onChange={(e) => {
            const files = e.target.files ? Array.from(e.target.files) : [];
            if (files.length) onUpload(files);
            e.target.value = "";
          }}
        />

        <details className="mt-3 text-sm">
          <summary className="cursor-pointer text-muted hover:text-text px-2">Настройки модели</summary>
          <div className="mt-2 space-y-2 px-1">
            <select
              value={provider}
              onChange={(e) => onProvider(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-2 py-1.5 text-sm"
            >
              <option value="openrouter">openrouter</option>
              <option value="ollama">ollama</option>
            </select>
            <input
              value={model}
              onChange={(e) => onModel(e.target.value)}
              className="w-full rounded-lg border border-border bg-surface px-2 py-1.5 text-sm"
              placeholder="модель"
            />
            <p className="text-[11px] text-muted">Ключ OpenRouter — в backend/.env</p>
          </div>
        </details>
      </div>
    </aside>
  );
}
