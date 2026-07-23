"""Design system — one place for the whole visual language.

De-stocked Streamlit: hides native chrome, applies an Inter/JetBrains-Mono type
system, a restrained slate + indigo palette, a card-based layout and a custom
sidebar navigation. Also themes every Altair chart so the app reads as one
product. Cosmetic only — never blocks the app.
"""

from __future__ import annotations

import altair as alt

ACCENT = "#4F46E5"
INK = "#0F172A"
TEXT = "#334155"
MUTED = "#64748B"
BORDER = "#E7E8EE"
GRID = "#EEF0F4"
CATEGORY = ["#4F46E5", "#0EA5E9", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#14B8A6", "#64748B"]

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

:root{
  --accent:#4F46E5; --accent-weak:#EEF0FF; --accent-ink:#4338CA;
  --ink:#0F172A; --text:#334155; --muted:#64748B;
  --bg:#F7F8FA; --surface:#FFFFFF; --border:#E7E8EE; --radius:12px;
}

/* hide native Streamlit chrome */
#MainMenu, header[data-testid="stHeader"], [data-testid="stToolbar"],
[data-testid="stDecoration"], footer { display:none !important; visibility:hidden; }

.stApp { background:var(--bg); }
html, body, .stApp, [data-testid="stAppViewContainer"], input, textarea, button, select {
  font-family:'Inter', system-ui, -apple-system, sans-serif; color:var(--text);
}
code, pre, [data-testid="stMetricValue"], [data-testid="stDataFrame"], .stDataFrame {
  font-family:'JetBrains Mono', ui-monospace, monospace; font-variant-numeric:tabular-nums;
}
.block-container{ padding:2rem 2.5rem 4rem; max-width:1400px; }

h1,h2,h3,h4{ color:var(--ink); letter-spacing:-.015em; }
h1{ font-weight:700; } h2,h3{ font-weight:600; }

/* ---- sidebar ---- */
[data-testid="stSidebar"]{ background:var(--surface); border-right:1px solid var(--border); }
[data-testid="stSidebar"] .block-container{ padding-top:1.25rem; }
.brand{ display:flex; align-items:center; gap:10px; padding:2px 4px 14px; }
.brand-name{ font-weight:700; color:var(--ink); font-size:1.02rem; line-height:1.1; letter-spacing:-.02em; }
.brand-tag{ font-size:.72rem; color:var(--muted); margin-top:2px; }
.nav-label{ font-size:.7rem; font-weight:600; text-transform:uppercase; letter-spacing:.08em;
  color:var(--muted); margin:14px 4px 6px; }

/* radio -> nav rows (robust: target data-testid, not hashed classes) */
[data-testid="stSidebar"] [role="radiogroup"]{ gap:1px; }
[data-testid="stSidebar"] [data-testid="stRadioOption"]{
  width:100%; padding:8px 10px; margin:0; border-radius:8px; cursor:pointer;
  transition:background .12s;
}
[data-testid="stSidebar"] [data-testid="stRadioOption"]:hover{ background:#F3F4F8; }
/* hide the radio circle: first child of the row that holds the text */
[data-testid="stSidebar"] [data-testid="stRadioOption"] div:has(> [data-testid="stMarkdownContainer"]) > div:first-child{ display:none; }
[data-testid="stSidebar"] [data-testid="stRadioOption"] p{ font-size:.92rem; font-weight:500; color:var(--text); margin:0; }
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"]{ background:var(--accent-weak); }
[data-testid="stSidebar"] [data-testid="stRadioOption"][data-selected="true"] p{ color:var(--accent-ink); font-weight:600; }

/* ---- buttons ---- */
.stButton>button{ border-radius:8px; font-weight:600; border:1px solid var(--border);
  background:var(--surface); color:var(--text); transition:all .12s; }
.stButton>button:hover{ border-color:var(--accent); color:var(--accent); }
.stButton>button[kind="primary"]{ background:var(--accent); border-color:var(--accent); color:#fff; }
.stButton>button[kind="primary"]:hover{ background:var(--accent-ink); border-color:var(--accent-ink); color:#fff; }
.stButton>button:focus-visible{ outline:2px solid var(--accent); outline-offset:2px; }

/* ---- inputs ---- */
[data-baseweb="input"], [data-baseweb="select"]>div, [data-baseweb="textarea"]{
  border-radius:8px !important; border-color:var(--border) !important; }
[data-baseweb="input"]:focus-within, [data-baseweb="select"]>div:focus-within{
  border-color:var(--accent) !important; box-shadow:0 0 0 3px var(--accent-weak) !important; }

/* ---- metric cards ---- */
[data-testid="stMetric"]{ background:var(--surface); border:1px solid var(--border);
  border-radius:var(--radius); padding:14px 18px; box-shadow:0 1px 2px rgba(15,23,42,.04); }
[data-testid="stMetricLabel"] p{ color:var(--muted); font-weight:500; font-size:.8rem;
  text-transform:uppercase; letter-spacing:.04em; }
[data-testid="stMetricValue"]{ color:var(--ink); font-weight:600; }

/* ---- containers / expanders / dataframe ---- */
[data-testid="stExpander"], [data-testid="stForm"]{ border:1px solid var(--border);
  border-radius:var(--radius); background:var(--surface); }
[data-testid="stDataFrame"]{ border:1px solid var(--border); border-radius:var(--radius); }

/* custom section header + context bar + empty state */
.t2a-section{ margin:2px 0 14px; }
.t2a-section h2{ font-size:1.35rem; margin:0; }
.t2a-section p{ color:var(--muted); font-size:.9rem; margin:4px 0 0; }
.ctx{ display:flex; align-items:baseline; gap:10px; padding:10px 14px; margin-bottom:14px;
  background:var(--surface); border:1px solid var(--border); border-radius:10px; }
.ctx b{ color:var(--ink); font-weight:600; } .ctx span{ color:var(--muted); font-size:.85rem; }
.empty{ max-width:520px; margin:12vh auto 0; text-align:center; }
.empty h1{ font-size:1.8rem; margin:0 0 8px; } .empty p{ color:var(--muted); }

@media (prefers-reduced-motion: reduce){ *{ transition:none !important; animation:none !important; } }
</style>
"""


def _altair_theme() -> dict:
    return {
        "config": {
            "font": "Inter, sans-serif",
            "background": "transparent",
            "view": {"stroke": "transparent"},
            "title": {"color": INK, "fontSize": 14, "fontWeight": 600, "anchor": "start"},
            "axis": {
                "labelColor": MUTED, "titleColor": TEXT, "gridColor": GRID,
                "domain": False, "tickColor": GRID,
                "labelFontSize": 11, "titleFontSize": 12, "labelFont": "Inter", "titleFont": "Inter",
            },
            "legend": {"labelColor": MUTED, "titleColor": TEXT, "labelFontSize": 11, "titleFontSize": 12},
            "range": {"category": CATEGORY, "heatmap": {"scheme": "purpleblue"}, "ramp": {"scheme": "purpleblue"}},
            "bar": {"fill": ACCENT}, "line": {"color": ACCENT, "strokeWidth": 2},
            "point": {"fill": ACCENT, "filled": True}, "rule": {"color": "#94A3B8"},
        }
    }


def enable_altair() -> None:
    """Register + enable the Altair theme so chart specs carry our styling.

    Safe to call from the Streamlit app or the FastAPI backend (which serializes
    charts to Vega-Lite via ``chart.to_dict()``).
    """
    try:
        alt.themes.register("t2a", _altair_theme)
        alt.themes.enable("t2a")
        # charts embed their data inline; lift Altair's 5000-row guard so specs
        # over large tables don't raise (we sample raw-point charts elsewhere).
        alt.data_transformers.disable_max_rows()
    except Exception:  # noqa: BLE001 — theming is cosmetic, never block
        pass


def apply(st) -> None:
    """Register the Altair theme and inject CSS. Call once, right after set_page_config."""
    enable_altair()
    st.markdown(_CSS, unsafe_allow_html=True)


BRAND_HTML = """
<div class="brand">
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none">
    <rect x="2" y="13" width="4.2" height="9" rx="1.2" fill="#A5B4FC"/>
    <rect x="9.9" y="7" width="4.2" height="15" rx="1.2" fill="#6366F1"/>
    <rect x="17.8" y="3" width="4.2" height="19" rx="1.2" fill="#4338CA"/>
  </svg>
  <div><div class="brand-name">Text-to-Analytics</div><div class="brand-tag">аналитика данных на русском</div></div>
</div>
"""
