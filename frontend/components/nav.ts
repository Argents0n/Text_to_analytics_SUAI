export type SectionKey =
  | "chat"
  | "eda"
  | "report"
  | "stats"
  | "drivers"
  | "cleaning"
  | "ab"
  | "ts"
  | "pivot"
  | "cohort"
  | "explorer";

export const NAV: { key: SectionKey; label: string; ready: boolean }[] = [
  { key: "chat", label: "Чат", ready: true },
  { key: "eda", label: "Разведка (EDA)", ready: true },
  { key: "report", label: "Авто-отчёт", ready: true },
  { key: "stats", label: "Статистика", ready: true },
  { key: "drivers", label: "Драйверы", ready: true },
  { key: "cleaning", label: "Очистка данных", ready: true },
  { key: "ab", label: "A/B и гипотезы", ready: true },
  { key: "ts", label: "Временные ряды", ready: true },
  { key: "pivot", label: "Сводные", ready: true },
  { key: "cohort", label: "Когорты", ready: true },
  { key: "explorer", label: "Конструктор", ready: true },
];
