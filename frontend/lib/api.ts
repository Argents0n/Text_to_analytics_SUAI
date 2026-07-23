const BASE = process.env.NEXT_PUBLIC_API ?? "http://localhost:8000";

export type Column = {
  name: string;
  type: string;
  role: "numeric" | "categorical" | "temporal";
  missing_pct: number;
  distinct: number;
};

export type Table = {
  name: string;
  nrows: number;
  roles: { numeric: string[]; categorical: string[]; temporal: string[] };
  columns: Column[];
  sample: Record<string, unknown>[];
};

export type Dataset = { id: string; tables: Table[] };

export type ChatResponse = {
  sql: string;
  attempts: number;
  answer: string;
  columns: string[];
  rows: Record<string, unknown>[];
  chart: object | null;
  chart_kind: string;
};

export type EdaResponse = {
  table: string;
  overview: Record<string, number>;
  describe: Record<string, unknown>[];
  corr_chart: object | null;
  top_corr: { a: string; b: string; r: number }[];
  univariate: { name: string; chart: object }[];
};

async function handle<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const body = await res.json();
      msg = body.detail ?? JSON.stringify(body);
    } catch {
      /* keep statusText */
    }
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export type Finding = { kind: string; text: string; chart: object | null };
export type ReportResp = { table: string; narrative: string; findings: Finding[] };
export type CleaningResp = {
  table: string;
  n_rows: number;
  duplicate_rows: number;
  missing: Record<string, unknown>[];
  anomalies: Record<string, unknown>[];
  dtype_suggestions: Record<string, unknown>[];
  implicit_dups: { column: string; groups: string[][] }[];
};
export type Driver = { feature: string; kind: string; strength: number; detail: string; chart: object | null };
export type DriversResp = { table: string; drivers: Driver[] };
export type StatResp = { result?: Record<string, unknown>; chart?: object; top_corr?: { a: string; b: string; r: number }[] };
export type ChartResp = { chart: object; rows?: Record<string, unknown>[]; line?: object };

function form(file: File): FormData {
  const fd = new FormData();
  fd.append("file", file);
  return fd;
}

function post<T>(path: string, body: Record<string, unknown>): Promise<T> {
  return fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then((r) => handle<T>(r));
}

export const api = {
  demo: () =>
    fetch(`${BASE}/api/datasets/demo`, { method: "POST" }).then((r) => handle<Dataset>(r)),

  upload: (file: File) =>
    fetch(`${BASE}/api/datasets`, { method: "POST", body: form(file) }).then((r) =>
      handle<Dataset>(r),
    ),

  addTable: (id: string, file: File) =>
    fetch(`${BASE}/api/datasets/${id}/tables`, { method: "POST", body: form(file) }).then((r) =>
      handle<Dataset>(r),
    ),

  merge: (id: string, body: Record<string, unknown>) =>
    post<Dataset>(`/api/datasets/${id}/merge`, body),

  chat: (id: string, question: string, provider: string, model: string) =>
    fetch(`${BASE}/api/datasets/${id}/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, provider, model }),
    }).then((r) => handle<ChatResponse>(r)),

  eda: (id: string, table?: string) =>
    fetch(`${BASE}/api/datasets/${id}/eda${table ? `?table=${encodeURIComponent(table)}` : ""}`, {
      method: "POST",
    }).then((r) => handle<EdaResponse>(r)),

  report: (id: string, body: Record<string, unknown>) =>
    post<ReportResp>(`/api/datasets/${id}/report`, body),
  cleaning: (id: string, table: string) =>
    fetch(`${BASE}/api/datasets/${id}/cleaning?table=${encodeURIComponent(table)}`, {
      method: "POST",
    }).then((r) => handle<CleaningResp>(r)),
  drivers: (id: string, body: Record<string, unknown>) =>
    post<DriversResp>(`/api/datasets/${id}/drivers`, body),
  stats: (id: string, body: Record<string, unknown>) =>
    post<StatResp>(`/api/datasets/${id}/stats`, body),
  abtest: (id: string, body: Record<string, unknown>) =>
    post<StatResp>(`/api/datasets/${id}/abtest`, body),
  probability: (body: Record<string, unknown>) => post<StatResp>(`/api/probability`, body),
  timeseries: (id: string, body: Record<string, unknown>) =>
    post<ChartResp>(`/api/datasets/${id}/timeseries`, body),
  pivot: (id: string, body: Record<string, unknown>) =>
    post<ChartResp>(`/api/datasets/${id}/pivot`, body),
  cohort: (id: string, body: Record<string, unknown>) =>
    post<ChartResp>(`/api/datasets/${id}/cohort`, body),
  explorer: (id: string, body: Record<string, unknown>) =>
    post<ChartResp>(`/api/datasets/${id}/explorer`, body),
};
