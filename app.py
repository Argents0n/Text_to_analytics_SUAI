"""Streamlit entry point: upload tabular data, then explore it.

Tabs: Chat (NL->SQL), Auto-report (classical insights), EDA, Stats, Cohort,
Explorer (manual chart builder). Everything but Chat/narration is LLM-free.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from t2a import abtest, cleaning, drivers, probability
from t2a import pivot as pv
from t2a import stats as S
from t2a import timeseries as ts
from t2a import transform
from t2a.charts import choose_chart
from t2a.chart_builder import AGGS, KINDS, build_custom
from t2a.cohort import METRICS, PERIODS, cohort_analysis
from t2a.eda import build_eda
from t2a.execute import ExecError, answer_sql
from t2a.llm import LLM, LLMError
from t2a.narrate import summarize_result
from t2a.profile import profile, roles, schema_text
from t2a.report import build_report
from t2a.sources import SUPPORTED, load_file
from t2a.theme import BRAND_HTML
from t2a.theme import apply as apply_theme

NAV = [
    ("chat", "Чат", "Вопрос на русском → SQL → график и ответ."),
    ("report", "Авто-отчёт", "Профиль данных и находки классическими методами."),
    ("eda", "Разведка (EDA)", "Обзор, описательная статистика, распределения, корреляции."),
    ("stats", "Статистика", "Сравнение групп, связь категорий, нормальность."),
    ("drivers", "Драйверы", "Что сильнее всего влияет на выбранный показатель."),
    ("cleaning", "Очистка данных", "Дубли, аномалии, пропуски, типы."),
    ("ab", "A/B и гипотезы", "Статтесты, bootstrap, распределения."),
    ("ts", "Временные ряды", "Ресемплинг, декомпозиция, автокорреляция, прогноз."),
    ("pivot", "Сводные", "Сводные таблицы и связь по бинам."),
    ("cohort", "Когорты", "Удержание и выручка по периоду первой активности."),
    ("explorer", "Конструктор", "Ручной график и вычисляемые колонки."),
]
NAV_KEYS = [k for k, _, _ in NAV]
NAV_LABEL = {k: lbl for k, lbl, _ in NAV}
NAV_DESC = {k: desc for k, _, desc in NAV}


def section(title: str, desc: str | None = None) -> None:
    html = f"<div class='t2a-section'><h2>{title}</h2>"
    if desc:
        html += f"<p>{desc}</p>"
    st.markdown(html + "</div>", unsafe_allow_html=True)


def _df():
    return st.session_state.con.execute(
        f'SELECT * FROM "{st.session_state.table}"'
    ).df()

load_dotenv()

st.set_page_config(page_title="Text-to-Analytics", page_icon="📊", layout="wide")
apply_theme(st)


def _set_data(path: str, name: str) -> None:
    con, table = load_file(path)
    st.session_state.con = con
    st.session_state.table = table
    st.session_state.profile = profile(con, table)
    st.session_state.filename = name


def _ingest(uploaded) -> None:
    suffix = Path(uploaded.name).suffix.lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded.getbuffer())
        tmp_path = tmp.name
    _set_data(tmp_path, uploaded.name)


with st.sidebar:
    st.markdown(BRAND_HTML, unsafe_allow_html=True)

    st.markdown("<div class='nav-label'>Разделы</div>", unsafe_allow_html=True)
    page = st.radio(
        "Разделы", NAV_KEYS, format_func=lambda k: NAV_LABEL[k],
        label_visibility="collapsed", key="nav",
    )

    st.markdown("<div class='nav-label'>Данные</div>", unsafe_allow_html=True)
    _sample = Path(__file__).parent / "data" / "sample_sales_ru.csv"
    if _sample.exists() and st.button("Демо-данные", use_container_width=True):
        _set_data(str(_sample), "sample_sales_ru.csv")
        st.rerun()
    uploaded = st.file_uploader(
        "Загрузить файл", type=[e.lstrip(".") for e in sorted(SUPPORTED)],
        label_visibility="collapsed",
    )
    if uploaded is not None and st.button("Загрузить", type="primary", use_container_width=True):
        try:
            _ingest(uploaded)
            st.success(f"Загружено: {uploaded.name}")
        except Exception as e:  # noqa: BLE001 — surface any ingest failure to the UI
            st.error(f"Не удалось загрузить: {e}")

    with st.expander("Настройки модели"):
        provider = st.selectbox("Провайдер", ["openrouter", "ollama"], index=0)
        default_model = (
            os.getenv("T2A_MODEL", "openrouter/free")
            if provider == "openrouter"
            else os.getenv("OLLAMA_MODEL", "qwen2.5-coder:7b")
        )
        model = st.text_input("Модель", value=default_model)
        st.caption("OpenRouter: задай OPENROUTER_API_KEY в .env")

if "profile" not in st.session_state:
    st.markdown(
        "<div class='empty'><h1>Аналитика данных на русском</h1>"
        "<p>Загрузите CSV, XLSX, Parquet или JSON в левой панели — "
        "или нажмите «Демо-данные», чтобы посмотреть на примере продаж.</p></div>",
        unsafe_allow_html=True,
    )
    st.stop()

prof = st.session_state.profile
st.markdown(
    f"<div class='ctx'><b>{st.session_state.filename}</b>"
    f"<span>{prof['nrows']} строк · {len(prof['columns'])} колонок</span></div>",
    unsafe_allow_html=True,
)
with st.expander("Профиль и первые строки", expanded=False):
    st.dataframe(prof["sample"], width="stretch")
    st.code(schema_text(prof), language="markdown")

r = roles(prof)
num_cols, cat_cols = r["numeric"], r["categorical"]
temporal_cols, all_cols = r["temporal"], [c["name"] for c in prof["columns"]]

section(NAV_LABEL[page], NAV_DESC[page])

if page == "chat":
    with st.form("chat", clear_on_submit=False):
        question = st.text_input("Спроси данные на русском", placeholder="напр. траты по категориям")
        submitted = st.form_submit_button("Спросить", type="primary")
    if submitted and question:
        try:
            llm = LLM(provider=provider, model=model)
            with st.spinner("Генерирую SQL…"):
                res = answer_sql(st.session_state.con, llm, schema_text(prof), question)
            answer = summarize_result(llm, question, res.df)
            if answer:
                st.write(answer)
            choice = choose_chart(res.df)
            if choice.chart is not None:
                st.altair_chart(choice.chart, width="stretch")
            st.dataframe(res.df, width="stretch")
            with st.expander("SQL и детали"):
                st.code(res.sql, language="sql")
                st.caption(f"Попыток: {res.attempts} · график: {choice.kind} — {choice.reason}")
        except LLMError as e:
            st.error(f"LLM: {e}")
        except ExecError as e:
            st.error(str(e))
            st.json(e.trace)

if page == "report":
    st.caption("Профилирует данные, ищет закономерности классическими методами, "
               "LLM только формулирует выводы.")
    if st.button("Построить отчёт", type="primary"):
        try:
            llm = LLM(provider=provider, model=model)
        except LLMError:
            llm = None  # report still works offline with precomputed texts
        with st.spinner("Считаю инсайты…"):
            report = build_report(st.session_state.con, st.session_state.table, llm)
        st.markdown(report.narrative)
        st.divider()
        for f in report.findings:
            st.markdown(f"**[{f.kind}]** {f.text}")
            if f.chart is not None:
                st.altair_chart(f.chart, width="stretch")
        if not report.findings:
            st.info("Значимых закономерностей не найдено.")

if page == "eda":
    st.caption("Полный разведочный анализ: обзор, статистика, распределения, корреляции.")
    if st.button("Построить EDA", type="primary"):
        with st.spinner("Считаю…"):
            eda = build_eda(st.session_state.con, st.session_state.table)
        o = eda.overview
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Строк", o["rows"])
        c2.metric("Колонок", o["columns"])
        c3.metric("Пропуски", f'{o["missing_cells_%"]}%')
        c4.metric("Дубликаты", o["duplicate_rows"])
        st.caption(
            f'Числовых {o["numeric"]} · категориальных {o["categorical"]} · временных {o["temporal"]}'
        )
        st.subheader("Описательная статистика")
        st.dataframe(eda.describe, width="stretch")
        if eda.corr_chart is not None:
            st.subheader("Корреляции")
            st.altair_chart(eda.corr_chart, width="stretch")
            st.caption("Топ связей: " + ", ".join(
                f"{a}↔{b} r={v:.2f}" for a, b, v in eda.top_corr[:5]
            ))
        st.subheader("Распределения")
        for i in range(0, len(eda.univariate), 2):
            cols = st.columns(2)
            for col_box, (name, chart) in zip(cols, eda.univariate[i:i + 2]):
                col_box.markdown(f"**{name}**")
                col_box.altair_chart(chart, width="stretch")

if page == "stats":
    analysis = st.selectbox(
        "Анализ",
        ["Сравнение групп", "Связь категорий (χ²)", "Нормальность", "Корреляции"],
    )
    df = _df()
    if analysis == "Сравнение групп" and num_cols and cat_cols:
        col1, col2, col3 = st.columns(3)
        num = col1.selectbox("Числовая", num_cols)
        cat = col2.selectbox("Группа", cat_cols)
        parametric = col3.checkbox("Параметрический тест", value=False)
        res = S.compare_groups(df, num, cat, parametric=parametric)
        if res:
            verdict = "есть значимые различия" if res["significant"] else "различия незначимы"
            st.markdown(
                f'**{res["test"]}** ({res["groups"]} групп): stat={res["stat"]:.2f}, '
                f'p={res["p"]:.2e} → **{verdict}** (α=0.05)'
            )
            st.bar_chart(pd.Series(res["group_medians"], name="медиана"))
        else:
            st.info("Недостаточно групп для сравнения.")
    elif analysis == "Связь категорий (χ²)" and len(cat_cols) >= 2:
        col1, col2 = st.columns(2)
        c1v = col1.selectbox("Категория 1", cat_cols, index=0)
        c2v = col2.selectbox("Категория 2", cat_cols, index=1)
        res = S.chi_square(df, c1v, c2v)
        if res:
            verdict = "связаны" if res["significant"] else "независимы"
            st.markdown(
                f'**χ²**={res["chi2"]:.1f}, dof={res["dof"]}, p={res["p"]:.3f}, '
                f'Cramér\'s V={res["cramers_v"]:.3f} → категории **{verdict}**'
            )
            st.dataframe(res["contingency"], width="stretch")
    elif analysis == "Нормальность" and num_cols:
        num = st.selectbox("Числовая", num_cols)
        res = S.normality(df[num])
        if res:
            verdict = "похоже на нормальное" if res["normal"] else "не нормальное"
            st.markdown(
                f'**{res["test"]}** (n={res["n"]}): stat={res["stat"]:.3f}, '
                f'p={res["p"]:.2e} → распределение **{verdict}**'
            )
        st.altair_chart(
            build_custom(df, "hist", x=num), width="stretch"
        )
    elif analysis == "Корреляции" and len(num_cols) >= 2:
        method = st.radio("Метод", ["pearson", "spearman"], horizontal=True)
        corr = S.correlation_matrix(df, num_cols, method=method)
        st.altair_chart(S.corr_heatmap(corr), width="stretch")
        st.dataframe(corr.round(3), width="stretch")
    else:
        st.info("Для этого анализа не хватает колонок нужного типа.")

if page == "cohort":
    st.caption("Когорты по периоду первой активности и метрика во времени.")
    if not (cat_cols and st.session_state.profile):
        st.info("Нужна колонка-идентификатор и колонка с датой.")
    else:
        col1, col2, col3 = st.columns(3)
        id_col = col1.selectbox("Идентификатор", cat_cols)
        date_col = col2.selectbox("Дата", all_cols)
        period = col3.selectbox("Период", PERIODS, index=PERIODS.index("month"))
        col4, col5 = st.columns(2)
        metric = col4.selectbox("Метрика", METRICS)
        value_col = col5.selectbox("Значение", num_cols) if metric in ("sum", "avg") and num_cols else None
        if st.button("Построить когорты", type="primary"):
            try:
                res = cohort_analysis(
                    st.session_state.con, st.session_state.table,
                    id_col, date_col, value_col, period, metric,
                )
                st.altair_chart(res.chart, width="stretch")
                st.dataframe(res.display.round(1), width="stretch")
            except ValueError as e:
                st.error(str(e))

if page == "explorer":
    st.caption("Собери график вручную. Zoom/pan и подсказки — для line/area/scatter.")
    df = _df()
    with st.expander("➕ Вычисляемая колонка (feature engineering)"):
        op = st.selectbox("Операция", ["нет", "арифметика", "часть даты", "бины", "перевод единиц"])
        try:
            if op == "арифметика" and num_cols:
                c1, c2, c3, c4 = st.columns(4)
                a = c1.selectbox("A", num_cols, key="fe_a")
                o = c2.selectbox("Оп", transform.OPS, key="fe_op")
                b = c3.selectbox("B", num_cols, key="fe_b")
                nm = c4.text_input("Имя", "new_col", key="fe_n1")
                if nm:
                    df = transform.add_arithmetic(df, a, o, b, nm)
            elif op == "часть даты" and all_cols:
                c1, c2, c3 = st.columns(3)
                col = c1.selectbox("Дата", (temporal_cols or all_cols), key="fe_d")
                part = c2.selectbox("Часть", transform.DATE_PARTS, key="fe_p")
                nm = c3.text_input("Имя", "date_part", key="fe_n2")
                if nm:
                    df = transform.add_datepart(df, col, part, nm)
            elif op == "бины" and num_cols:
                c1, c2, c3, c4 = st.columns(4)
                col = c1.selectbox("Колонка", num_cols, key="fe_bc")
                nb = c2.number_input("Бинов", 2, 50, 4, key="fe_nb")
                q = c3.checkbox("Квантили", key="fe_q")
                nm = c4.text_input("Имя", "bin", key="fe_n3")
                if nm:
                    df = transform.add_bin(df, col, int(nb), nm, quantile=q)
            elif op == "перевод единиц" and num_cols:
                c1, c2, c3 = st.columns(3)
                col = c1.selectbox("Колонка", num_cols, key="fe_uc")
                f = c2.number_input("Множитель", value=1.0, key="fe_uf")
                nm = c3.text_input("Имя", "converted", key="fe_n4")
                if nm:
                    df = transform.convert_unit(df, col, f, nm)
        except Exception as e:  # noqa: BLE001 — surface transform failures inline
            st.warning(f"Не удалось добавить колонку: {e}")

    cols = list(df.columns)
    col1, col2, col3, col4, col5 = st.columns(5)
    kind = col1.selectbox("Тип", KINDS)
    x = col2.selectbox("X", [None] + cols)
    y = col3.selectbox("Y", [None] + cols)
    color = col4.selectbox("Цвет", [None] + cols)
    agg = col5.selectbox("Агрегат", AGGS)
    try:
        st.altair_chart(build_custom(df, kind, x=x, y=y, color=color, agg=agg), width="stretch")
    except ValueError as e:
        st.info(str(e))

if page == "drivers":
    st.caption("Что влияет на таргет: числовые — по |корреляции|, категориальные — по η.")
    if not num_cols:
        st.info("Нужна числовая колонка-таргет.")
    else:
        target = st.selectbox("Таргет (числовой)", num_cols)
        if st.button("Найти драйверы", type="primary"):
            df = _df()
            ranked = drivers.analyze_drivers(df, target)
            if not ranked:
                st.info("Не нашлось значимых драйверов.")
            for d in ranked:
                st.markdown(f"**{d.feature}** · {d.kind} · сила {d.strength:.2f} ({d.detail})")
                if d.chart is not None:
                    st.altair_chart(d.chart, width="stretch")

if page == "cleaning":
    st.caption("Дубли, неявные дубли, аномалии, пропуски, несоответствие типов.")
    if st.button("Проверить качество данных", type="primary"):
        rep = cleaning.clean_report(_df())
        c1, c2, c3 = st.columns(3)
        c1.metric("Строк", rep.n_rows)
        c2.metric("Дубликаты строк", rep.duplicate_rows)
        c3.metric("Проблемных колонок",
                  len(rep.missing) + len(rep.anomalies) + len(rep.implicit_dups) + len(rep.dtype_suggestions))
        if rep.missing:
            st.subheader("Пропуски")
            st.dataframe(pd.DataFrame(rep.missing), width="stretch")
        if rep.anomalies:
            st.subheader("Аномалии (IQR)")
            st.dataframe(pd.DataFrame(rep.anomalies), width="stretch")
        if rep.dtype_suggestions:
            st.subheader("Типы данных")
            st.dataframe(pd.DataFrame(rep.dtype_suggestions), width="stretch")
        if rep.implicit_dups:
            st.subheader("Неявные дубликаты категорий")
            for col, groups in rep.implicit_dups:
                st.markdown(f"**{col}**")
                for g in groups:
                    st.write(" ≈ ".join(g))

if page == "ab":
    mode = st.radio("Режим", ["Проверка гипотез", "Распределения"], horizontal=True, key="ab_mode")
    df = _df()
    if mode == "Проверка гипотез":
        test = st.selectbox("Тест", ["Одновыборочный (vs порог)", "Парный (до/после)",
                                     "Двухвыборочный (2 группы)", "Доли (A/B)"], key="ab_test")
        alt_h = st.selectbox("Гипотеза", ["two-sided", "less", "greater"], key="ab_alt")
        if test == "Одновыборочный (vs порог)" and num_cols:
            c1, c2 = st.columns(2)
            col = c1.selectbox("Колонка", num_cols, key="ab_os_col")
            thr = c2.number_input("Порог", value=float(round(df[col].mean(), 2)), key="ab_thr")
            res = abtest.one_sample(df[col], thr, alt_h)
            st.json({k: res[k] for k in ("test", "n", "mean", "stat", "p", "significant")})
        elif test == "Парный (до/после)" and len(num_cols) >= 2:
            c1, c2 = st.columns(2)
            a = c1.selectbox("До", num_cols, index=0, key="ab_a")
            b = c2.selectbox("После", num_cols, index=1, key="ab_b")
            res = abtest.paired(df[a], df[b], alt_h)
            st.json({k: res[k] for k in ("test", "n", "mean_diff", "stat", "p", "significant")})
        elif test == "Двухвыборочный (2 группы)" and num_cols and cat_cols:
            c1, c2 = st.columns(2)
            metric = c1.selectbox("Метрика", num_cols, key="ab_metric")
            gcol = c2.selectbox("Группа", cat_cols, key="ab_gcol")
            groups = [str(v) for v in df[gcol].dropna().unique()][:20]
            c3, c4, c5 = st.columns(3)
            g1 = c3.selectbox("Группа A", groups, index=0, key="ab_g1")
            g2 = c4.selectbox("Группа B", groups, index=min(1, len(groups) - 1), key="ab_g2")
            parametric = c5.checkbox("Параметрический", key="ab_param")
            a = df[df[gcol].astype(str) == g1][metric]
            b = df[df[gcol].astype(str) == g2][metric]
            res = abtest.two_sample(a, b, parametric, alt_h)
            st.json({k: res[k] for k in ("test", "n1", "n2", "median1", "median2", "p", "significant")})
        elif test == "Доли (A/B)":
            c1, c2, c3, c4 = st.columns(4)
            s1 = c1.number_input("Успехи A", 0, value=30, key="ab_s1")
            n1 = c2.number_input("Всего A", 1, value=100, key="ab_n1")
            s2 = c3.number_input("Успехи B", 0, value=40, key="ab_s2")
            n2 = c4.number_input("Всего B", 1, value=120, key="ab_n2")
            res = abtest.two_proportion(int(s1), int(n1), int(s2), int(n2), alt_h)
            st.json({k: res[k] for k in ("test", "p1", "p2", "stat", "p", "significant")})
        else:
            st.info("Для этого теста не хватает колонок нужного типа.")
        if num_cols:
            with st.expander("Bootstrap доверительный интервал"):
                c1, c2 = st.columns(2)
                bcol = c1.selectbox("Колонка", num_cols, key="boot_col")
                stat = c2.selectbox("Статистика", ["mean", "median", "std"], key="ab_boot_stat")
                res = abtest.bootstrap_ci(df[bcol], stat)
                st.write(f'{stat}={res["point"]:.2f}, 95% ДИ [{res["low"]:.2f}, {res["high"]:.2f}]')
    else:
        dist = st.radio("Распределение", ["Биномиальное: объём выборки", "Нормальная аппроксимация"], key="ab_dist")
        if dist == "Биномиальное: объём выборки":
            c1, c2, c3 = st.columns(3)
            p = c1.number_input("Вероятность успеха p", 0.0, 1.0, 0.1, key="ab_bin_p")
            target = c2.number_input("Нужно успехов", 1, value=100, key="ab_bin_t")
            risk = c3.number_input("Допустимый риск", 0.0, 1.0, 0.05, key="ab_bin_r")
            res = probability.binomial_min_n(p, int(target), risk)
            if res["n"]:
                st.success(f'Нужно n = {res["n"]} (достигается P={res["achieved"]:.3f})')
                st.altair_chart(probability.binomial_chart(res["n"], p), width="stretch")
            else:
                st.warning("Не достигается в разумных пределах.")
        else:
            c1, c2, c3, c4 = st.columns(4)
            n = c1.number_input("n", 1, value=1_000_000, key="ab_na_n")
            p = c2.number_input("p", 0.0, 1.0, 0.4, key="ab_na_p")
            x = c3.number_input("x", value=399500.0, key="ab_na_x")
            direction = c4.selectbox("Направление", ["<=", ">="], key="ab_na_dir")
            res = probability.normal_approx(int(n), p, x, direction)
            st.write(f'μ={res["mu"]:.1f}, σ={res["sigma"]:.1f} → P(X {direction} {x:g}) = {res["prob"]:.4f}')

if page == "ts":
    st.caption("Ресемплинг, декомпозиция, скользящие, автокорреляция, прогноз.")
    if not (temporal_cols or all_cols) or not num_cols:
        st.info("Нужна колонка с датой и числовая колонка.")
    else:
        c1, c2, c3, c4 = st.columns(4)
        date_col = c1.selectbox("Дата", (temporal_cols or all_cols), key="ts_date")
        value_col = c2.selectbox("Значение", num_cols, key="ts_value")
        freq_label = c3.selectbox("Частота", list(ts.FREQS), key="ts_freq")
        agg = c4.selectbox("Агрегат", ["sum", "mean", "count", "max", "min"], key="ts_agg")
        freq = ts.FREQS[freq_label]
        if st.button("Построить ряд", type="primary"):
            try:
                ser = ts.resample_series(_df(), date_col, value_col, freq, agg)
                st.session_state.ts = (ser, freq)
            except Exception as e:  # noqa: BLE001
                st.error(f"Не удалось построить ряд: {e}")
        if "ts" in st.session_state:
            ser, freq = st.session_state.ts
            period = ts.default_period(freq)
            st.altair_chart(ts.line(ser, value_col), width="stretch")
            sub = st.selectbox("Анализ", ["Декомпозиция", "Скользящие", "Автокорреляция", "Прогноз"], key="ts_sub")
            try:
                if sub == "Декомпозиция":
                    _, chart = ts.decompose(ser, period)
                    st.altair_chart(chart, width="stretch")
                elif sub == "Скользящие":
                    w = st.slider("Окно", 2, max(3, period * 2), period, key="ts_win")
                    st.altair_chart(ts.rolling(ser, w), width="stretch")
                elif sub == "Автокорреляция":
                    st.altair_chart(ts.acf_chart(ser), width="stretch")
                else:
                    c1, c2 = st.columns(2)
                    horizon = c1.slider("Горизонт", 1, period * 3, period, key="ts_hor")
                    method = c2.selectbox("Метод", ["seasonal_naive", "holt-winters"], key="ts_method")
                    _, chart = ts.forecast(ser, horizon, method, period)
                    st.altair_chart(chart, width="stretch")
            except Exception as e:  # noqa: BLE001
                st.warning(f"Недостаточно данных для анализа: {e}")

if page == "pivot":
    mode = st.radio("Режим", ["Сводная таблица", "Binned relationship"], horizontal=True, key="pv_mode")
    df = _df()
    if mode == "Сводная таблица" and cat_cols and num_cols:
        c1, c2, c3, c4 = st.columns(4)
        index = c1.selectbox("Строки", cat_cols, key="pv_index")
        values = c2.selectbox("Значение", num_cols, key="pv_values")
        columns = c3.selectbox("Столбцы (опц.)", [None] + cat_cols, key="pv_columns")
        aggfunc = c4.selectbox("Агрегат", pv.AGGS, key="pv_agg")
        table, chart = pv.pivot(df, index, values, columns, aggfunc)
        st.altair_chart(chart, width="stretch")
        st.dataframe(table, width="stretch")
    elif mode == "Binned relationship" and len(num_cols) >= 2:
        c1, c2, c3, c4 = st.columns(4)
        x = c1.selectbox("X (число)", num_cols, index=0, key="pv_x")
        y = c2.selectbox("Y (число)", num_cols, index=1, key="pv_y")
        bins = c3.slider("Бинов", 2, 30, 10, key="pv_bins")
        agg = c4.selectbox("Агрегат", pv.AGGS, index=0, key="pv_agg2")
        quantile = st.checkbox("Квантильные бины", key="pv_quant")
        table, chart = pv.binned_relationship(df, x, y, bins, agg, quantile)
        st.altair_chart(chart, width="stretch")
        st.dataframe(table, width="stretch")
    else:
        st.info("Не хватает колонок нужного типа.")
