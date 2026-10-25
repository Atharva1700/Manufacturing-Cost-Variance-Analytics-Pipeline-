"""Checks the SQL variances against a plain-Python calculation on the same CSV files.

Needs PG_DSN pointing at a PostgreSQL database. Skipped otherwise.
"""

import csv
import os
import sys
from pathlib import Path

import psycopg
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import simulate  # noqa: E402
from pipeline import run  # noqa: E402

DSN = os.environ.get("PG_DSN")
needs_pg = pytest.mark.skipif(not DSN, reason="set PG_DSN to run the PostgreSQL tests")


@pytest.fixture(scope="module")
def data_dir(tmp_path_factory):
    return simulate.simulate(tmp_path_factory.mktemp("cost") / "data")


def python_variances(data_dir):
    """Independent calculation of every product-step-week variance from the CSV files."""
    standards = {(r["product"], r["step"]): r for r in csv.DictReader(open(data_dir / "standards.csv"))}
    production = {(r["product"], r["step"], r["week_start"]): r
                  for r in csv.DictReader(open(data_dir / "production.csv"))}
    out = {}
    for a in csv.DictReader(open(data_dir / "actuals.csv")):
        key = (a["product"], a["step"], a["week_start"])
        s = standards[(a["product"], a["step"])]
        p = production[key]
        started = int(p["units_started"])
        std_kg = started * float(s["std_kg_per_unit"])
        std_price = float(s["std_price_per_kg"])
        std_hours = started * float(s["std_hours_per_unit"])
        rate = float(s["std_labor_rate"])
        act_kg, act_cost = float(a["material_kg"]), float(a["material_cost"])
        act_labor = float(a["labor_cost"])
        price_var = act_cost - act_kg * std_price
        usage_var = (act_kg - std_kg) * std_price
        labor_var = act_labor - std_hours * rate
        total = price_var + usage_var + labor_var
        std_total = std_kg * std_price + std_hours * rate
        out[key] = {"total": total, "pct": total / std_total, "labor": labor_var,
                    "price": price_var, "usage": usage_var}
    return out


@needs_pg
def test_sql_variances_match_python(data_dir):
    expected = python_variances(data_dir)
    with psycopg.connect(DSN) as conn:
        run.load(conn, data_dir)
        rows = conn.execute("select product, step, week_start::text, total_var, material_price_var, "
                            "material_usage_var, labor_var from v_variance").fetchall()
    assert len(rows) == len(expected) == 96
    for product, step, week, total, price, usage, labor in rows:
        e = expected[(product, step, week)]
        assert float(total) == pytest.approx(e["total"], abs=0.01)
        assert float(price) == pytest.approx(e["price"], abs=0.01)
        assert float(usage) == pytest.approx(e["usage"], abs=0.01)
        assert float(labor) == pytest.approx(e["labor"], abs=0.01)


@needs_pg
def test_price_and_usage_add_up_to_material_total(data_dir):
    with psycopg.connect(DSN) as conn:
        run.load(conn, data_dir)
        bad = conn.execute(
            "select count(*) from v_variance where abs((act_material_cost - std_material_cost) "
            "- (material_price_var + material_usage_var)) > 0.01").fetchone()[0]
    assert bad == 0


@needs_pg
def test_flags_match_python_rule_and_find_planted_deviations(data_dir):
    expected = python_variances(data_dir)
    rule = {k for k, e in expected.items() if abs(e["pct"]) >= 0.10 and abs(e["total"]) >= 500}
    with psycopg.connect(DSN) as conn:
        run.load(conn, data_dir)
        flagged = {(p, s, w) for p, s, w, *_ in conn.execute(
            "select product, step, week_start::text from v_flags").fetchall()}
    assert flagged == rule
    # Planted deviations: P-B ETCH from week 5, P-C ASSEMBLE from week 6.
    assert ("P-B", "ETCH", "2026-08-31") in flagged
    assert ("P-C", "ASSEMBLE", "2026-09-07") in flagged
    assert not any(p == "P-A" for p, _, _ in flagged)
