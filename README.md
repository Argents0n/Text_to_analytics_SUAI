# Text-to-Analytics

Задай вопрос к CSV/XLSX на русском — получи SQL, график и авто-инсайты.
Лёгкая self-hosted версия «агента-аналитика» (в духе ChatGPT Advanced Data Analysis),
работающая на локальной (Ollama) или бесплатной (OpenRouter) модели.

## Что умеет

- **Chat** — вопрос на русском → SQL → выполнение → авто-подбор графика → ответ.
- **Auto-report** — профиль → классические инсайты (корреляции, выбросы, тренды,
  различия групп) + графики + текстовый разбор.
- **EDA** — полный разведочный анализ: обзор, описательная статистика, распределения,
  корреляционная матрица + хитмап.
- **Stats** — сравнение групп (t-test/Mann-Whitney/ANOVA/Kruskal), связь категорий
  (χ² + Cramér's V), тест нормальности (Shapiro/D'Agostino), корреляции (Pearson/Spearman).
- **Drivers** — что влияет на таргет: числовые по |корреляции|, категориальные по η.
- **Cleaning** — дубли, неявные (fuzzy) дубли категорий, аномалии (IQR), пропуски + стратегии, несоответствие типов.
- **A/B** — гипотезы (одновыборочный vs порог, парный, двухвыборочный, доли), bootstrap-ДИ; калькулятор распределений (биномиальное/нормальное).
- **Time-series** — ресемплинг, декомпозиция (тренд/сезон/остаток), скользящие, автокорреляция, прогноз (seasonal-naive / Holt-Winters).
- **Pivot** — сводные таблицы и binned-relationship (Y по бинам X).
- **Cohort** — когортный анализ (retention / выручка) по периоду первой активности.
- **Explorer** — ручной конструктор графиков + feature engineering (вычисляемые колонки), интерактив (zoom/tooltip).

Ядро: любой источник → таблица → DuckDB → аналитический движок. Вся статистика и
аналитика — классическая (scipy/pandas), LLM участвует только в Chat и в формулировке
выводов авто-отчёта.

## Стек

Python · Streamlit · DuckDB · sqlglot (SQL-guard) · Altair/Vega-Lite · numpy/scipy.
LLM: OpenRouter (default) или Ollama (local fallback).

## Запуск

```bash
uv sync
cp .env.example .env   # вписать OPENROUTER_API_KEY
uv run streamlit run app.py
```

## Eval

```bash
uv run python eval/run_eval.py
```

Метрика — execution accuracy (совпадение результата запроса с эталоном), как в BIRD/Spider.
