"use client";

import { SectionKey } from "./nav";

const TILES: { key: SectionKey; title: string; desc: string }[] = [
  { key: "chat", title: "Спросить у данных", desc: "Вопрос на русском → SQL, таблица и график." },
  { key: "eda", title: "Быстрый обзор", desc: "Профиль, распределения, корреляции — в один клик." },
  { key: "drivers", title: "Что влияет на метрику", desc: "Выберите показатель — покажем драйверы." },
  { key: "ab", title: "Проверить гипотезу", desc: "Стат-тесты: сравнить группы, среднее vs порог." },
];

export function QuickStart({
  onGo,
  onDismiss,
  multiTable,
}: {
  onGo: (k: SectionKey) => void;
  onDismiss: () => void;
  multiTable: boolean;
}) {
  return (
    <div className="mb-6 rounded-xl border border-border bg-surface p-5">
      <div className="mb-3 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-ink">С чего начать</h2>
          <p className="mt-0.5 text-sm text-muted">
            Данные загружены. Выберите действие — или просто спросите что-нибудь в чате.
          </p>
        </div>
        <button
          onClick={onDismiss}
          className="shrink-0 rounded-lg border border-border px-2.5 py-1 text-xs text-muted hover:border-accent hover:text-accent"
        >
          Скрыть
        </button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {TILES.map((t) => (
          <button
            key={t.key}
            onClick={() => onGo(t.key)}
            className="group rounded-lg border border-border p-3 text-left transition-colors hover:border-accent hover:bg-accent-weak/40"
          >
            <div className="text-sm font-semibold text-ink group-hover:text-accent-ink">{t.title}</div>
            <div className="mt-1 text-xs leading-relaxed text-muted">{t.desc}</div>
          </button>
        ))}
      </div>

      {multiTable && (
        <p className="mt-3 rounded-lg bg-accent-weak/50 px-3 py-2 text-sm text-accent-ink">
          У вас несколько таблиц. Чат уже умеет их соединять сам. Чтобы анализировать
          объединённые данные и в других разделах — нажмите «⋈ объединить» выше и выберите
          общий ключ.
        </p>
      )}
    </div>
  );
}
