function fmt(v: unknown): string {
  if (v === null || v === undefined) return "—";
  if (typeof v === "number") return Number.isInteger(v) ? v.toLocaleString("ru-RU") : v.toLocaleString("ru-RU", { maximumFractionDigits: 2 });
  return String(v);
}

export function DataTable({
  columns,
  rows,
  max = 100,
}: {
  columns: string[];
  rows: Record<string, unknown>[];
  max?: number;
}) {
  const shown = rows.slice(0, max);
  return (
    <div className="overflow-x-auto rounded-xl border border-border bg-surface">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((c) => (
              <th key={c} className="px-3 py-2 text-left font-medium text-muted whitespace-nowrap">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {shown.map((row, i) => (
            <tr key={i} className="border-b border-border/60 last:border-0 hover:bg-bg/60">
              {columns.map((c) => (
                <td key={c} className="px-3 py-1.5 whitespace-nowrap tnum text-text">
                  {fmt(row[c])}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {rows.length > max && (
        <div className="px-3 py-2 text-xs text-muted">
          Показано {max} из {rows.length.toLocaleString("ru-RU")} строк
        </div>
      )}
    </div>
  );
}
