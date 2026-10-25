"""Made-up production, standards and actual cost data for three products over eight weeks.

Two deviations are planted on purpose so the flags have something to find:
  * P-B, ETCH: material price up 25% from week 5 on (price variance).
  * P-C, ASSEMBLE: labor hours run 30% over standard from week 6 on (labor variance).
Fixed seed. Not real plant data.
"""

import csv
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 21
WEEKS = [date(2026, 8, 3) + timedelta(weeks=i) for i in range(8)]
PRODUCTS = ["P-A", "P-B", "P-C"]
STEPS = ["CUT", "ETCH", "ASSEMBLE", "TEST"]

# product, step, std kg/unit, std price/kg, std labor hours/unit, std labor rate/hour
STANDARDS = [
    ("P-A", "CUT", 0.80, 12.00, 0.10, 38.0),
    ("P-A", "ETCH", 0.50, 30.00, 0.25, 42.0),
    ("P-A", "ASSEMBLE", 0.20, 18.00, 0.40, 36.0),
    ("P-A", "TEST", 0.05, 8.00, 0.15, 34.0),
    ("P-B", "CUT", 1.10, 11.50, 0.12, 38.0),
    ("P-B", "ETCH", 0.60, 29.00, 0.30, 42.0),
    ("P-B", "ASSEMBLE", 0.25, 17.50, 0.45, 36.0),
    ("P-B", "TEST", 0.06, 8.00, 0.18, 34.0),
    ("P-C", "CUT", 0.95, 12.50, 0.11, 38.0),
    ("P-C", "ETCH", 0.55, 30.50, 0.28, 42.0),
    ("P-C", "ASSEMBLE", 0.30, 18.50, 0.50, 36.0),
    ("P-C", "TEST", 0.07, 8.50, 0.20, 34.0),
]


def simulate(out_dir, seed=SEED):
    rng = random.Random(seed)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with (out_dir / "standards.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["product", "step", "std_kg_per_unit", "std_price_per_kg",
                    "std_hours_per_unit", "std_labor_rate"])
        w.writerows(STANDARDS)

    production, actuals = [], []
    for product, step, kg, price, hrs, rate in STANDARDS:
        for week_no, week in enumerate(WEEKS, start=1):
            started = rng.randint(380, 520)
            good = int(started * rng.uniform(0.94, 0.99))
            production.append([product, step, week.isoformat(), started, good])

            price_actual = price * (1 + rng.gauss(0, 0.01))
            if product == "P-B" and step == "ETCH" and week_no >= 5:
                price_actual *= 1.25
            kg_actual = kg * started * (1 + rng.gauss(0, 0.02))
            hours_actual = hrs * started * (1 + rng.gauss(0, 0.02))
            if product == "P-C" and step == "ASSEMBLE" and week_no >= 6:
                hours_actual *= 1.30
            labor_cost = hours_actual * rate * (1 + rng.gauss(0, 0.01))
            actuals.append([product, step, week.isoformat(), round(kg_actual, 2),
                            round(kg_actual * price_actual, 2), round(hours_actual, 2),
                            round(labor_cost, 2)])

    for name, header, rows in [
        ("production.csv", ["product", "step", "week_start", "units_started", "units_good"], production),
        ("actuals.csv", ["product", "step", "week_start", "material_kg", "material_cost",
                         "labor_hours", "labor_cost"], actuals),
    ]:
        with (out_dir / name).open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(header)
            w.writerows(rows)
    return out_dir


if __name__ == "__main__":
    out = simulate(Path(__file__).parent / "data")
    print(f"wrote 3 files to {out}")
