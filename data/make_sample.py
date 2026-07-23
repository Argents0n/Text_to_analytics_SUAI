"""Generate a small RU sales CSV for demo and eval. Reproducible (fixed seed)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

RNG = np.random.default_rng(42)

CATEGORIES = ["Электроника", "Одежда", "Продукты", "Книги", "Спорт"]
REGIONS = ["Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань"]
CHANNELS = ["Онлайн", "Магазин"]

BASE_PRICE = {
    "Электроника": 25000, "Одежда": 3500, "Продукты": 800, "Книги": 600, "Спорт": 5000,
}


def main() -> None:
    dates = pd.date_range("2025-01-01", "2025-06-30", freq="D")
    # customers "join" early and churn over time -> gives a realistic cohort curve
    n_customers = 300
    join_month = RNG.integers(0, 6, size=n_customers)  # 0..5 = Jan..Jun
    activity = RNG.uniform(0.3, 1.0, size=n_customers)  # per-customer retention strength

    rows = []
    for _ in range(1500):
        date = RNG.choice(dates)
        month = pd.Timestamp(date).month - 1
        # pick a customer already "joined" by this month, weighted by activity
        eligible = np.where(join_month <= month)[0]
        if len(eligible) == 0:
            continue
        w = activity[eligible]
        cust = int(RNG.choice(eligible, p=w / w.sum()))
        cat = RNG.choice(CATEGORIES)
        region = RNG.choice(REGIONS, p=[0.4, 0.25, 0.12, 0.12, 0.11])
        channel = RNG.choice(CHANNELS, p=[0.6, 0.4])
        qty = int(RNG.integers(1, 6))
        # seasonal uplift toward summer + noise
        season = 1 + 0.3 * np.sin((pd.Timestamp(date).dayofyear / 365) * 2 * np.pi)
        price = BASE_PRICE[cat] * season * RNG.normal(1.0, 0.15)
        amount = round(max(price, 100) * qty, 2)
        rows.append(
            {
                "date": pd.Timestamp(date).date().isoformat(),
                "customer_id": f"C{cust:04d}",
                "category": cat,
                "region": region,
                "channel": channel,
                "qty": qty,
                "amount": amount,
            }
        )

    df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
    # inject a few missing amounts to make profiling/insights realistic
    miss_idx = RNG.choice(df.index, size=20, replace=False)
    df.loc[miss_idx, "amount"] = np.nan

    out = Path(__file__).parent / "sample_sales_ru.csv"
    df.to_csv(out, index=False)
    print(f"wrote {out} ({len(df)} rows)")

    # a related table to demonstrate joins: one row per customer_id
    ids = sorted(df["customer_id"].unique())
    segments = ["Новый", "Постоянный", "VIP"]
    signup = pd.date_range("2024-06-01", "2025-01-31", freq="D")
    customers = pd.DataFrame({
        "customer_id": ids,
        "city": RNG.choice(REGIONS, size=len(ids)),
        "segment": RNG.choice(segments, size=len(ids), p=[0.5, 0.35, 0.15]),
        "signup_date": [pd.Timestamp(RNG.choice(signup)).date().isoformat() for _ in ids],
    })
    cout = Path(__file__).parent / "sample_customers_ru.csv"
    customers.to_csv(cout, index=False)
    print(f"wrote {cout} ({len(customers)} rows)")


if __name__ == "__main__":
    main()
