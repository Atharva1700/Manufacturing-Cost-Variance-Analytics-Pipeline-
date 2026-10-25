"""Loads the three CSV feeds into PostgreSQL, refreshes the variance views, and prints flags.

Usage: PG_DSN="postgresql://postgres@localhost:5432/cost_variance" python -m pipeline.run data/
"""

import os
import sys
from pathlib import Path

import psycopg

SCHEMA_FILE = Path(__file__).resolve().parents[1] / "sql" / "schema.sql"

FEEDS = [
    ("standards", "standards.csv"),
    ("production", "production.csv"),
    ("actuals", "actuals.csv"),
]


def load(conn, data_dir):
    with conn.transaction():
        conn.execute(SCHEMA_FILE.read_text())
        for table, filename in FEEDS:
            conn.execute(f"truncate {table}")
            with (Path(data_dir) / filename).open() as f, \
                    conn.cursor().copy(f"copy {table} from stdin with csv header") as copy:
                for line in f:
                    copy.write(line)


def flags(conn):
    return conn.execute(
        "select product, step, week_start, total_var, var_pct, material_price_var, "
        "material_usage_var, labor_var from v_flags order by abs(total_var) desc").fetchall()


def main(argv):
    data_dir = argv[0]
    with psycopg.connect(os.environ["PG_DSN"]) as conn:
        load(conn, data_dir)
        rows = flags(conn)
        print(f"{len(rows)} product-step-weeks flagged")
        for product, step, week, total, pct, price, usage, labor in rows[:10]:
            print(f"  {product} {step:<9} {week}  total {float(total):>10,.0f}  "
                  f"{float(pct):>+7.1%}  price {float(price):>9,.0f}  usage {float(usage):>8,.0f}  "
                  f"labor {float(labor):>9,.0f}")


if __name__ == "__main__":
    main(sys.argv[1:])
