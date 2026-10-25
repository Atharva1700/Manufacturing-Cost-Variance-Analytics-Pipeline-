# Manufacturing Cost Variance Analytics Pipeline

Loads production, standards and actual cost data into PostgreSQL, computes actual-versus-standard
variances by product, process step and week, and flags large deviations for investigation.

**The data is made up.** `simulate.py` plants two deviations on purpose so the flags have
something to find: P-B ETCH material price up 25% from week 5, and P-C ASSEMBLE labor hours 30
over standard from week 6. The planted cases are how the checks know the logic works. They say
nothing about any real plant.

## Variance definitions

Variances are actual minus standard, so a positive number is an overspend.

| Variance | Formula |
|---|---|
| Material price | actual cost − actual kg × standard price |
| Material usage | (actual kg − standard kg) × standard price, standard kg = units started × std kg/unit |
| Labor | actual labor cost − standard hours × standard rate, standard hours = units started × std hours/unit |
| Total | price + usage + labor |

Price and usage add up to the total material variance. The test checks that on every row.

## Flag rule

A product-step-week is flagged when the total variance is at least **10%** of standard cost and at
least **$500**. Both numbers live in the `thresholds` table, so changing the rule means one update,
not a code change.

## Results on the simulated data

Seven product-step-weeks are flagged, and all seven are the planted deviations:

| Product | Step | Weeks flagged | Total variance over the period |
|---|---|---|---|
| P-B | ETCH | Aug 31 to Sep 21 (4 weeks) | +$8,000 (+7.9%), almost all material price |
| P-C | ASSEMBLE | Sep 7 to Sep 21 (3 weeks) | +$6,606 (+7.6%), almost all labor |

The other ten product-steps stay within about ±1.4% over the whole period.

## Run

```bash
pip install -r requirements.txt
export PG_DSN="postgresql://postgres:postgres@localhost:5432/cost_variance"
python3 simulate.py
python3 -m pipeline.run data/        # loads, refreshes views, prints flagged rows
python3 -m pytest -q                 # 3 tests against PostgreSQL
```

The pipeline reloads the three feeds each time (`truncate`, then `COPY`), so re-running is safe.

## Files

| File | Purpose |
|---|---|
| `simulate.py` | Made-up standards, production and actuals, with the planted deviations |
| `sql/schema.sql` | Tables, thresholds, and the views `v_variance`, `v_flags`, `v_variance_by_product_step` |
| `pipeline/run.py` | Loads CSVs with `COPY`, applies the schema, prints flags |
| `tests/test_variance.py` | SQL variances match an independent Python calculation on all 96 rows; flags match the Python rule and include the planted cases |
| `.github/workflows/ci.yml` | Runs the pipeline and tests against a Postgres 16 service container |

## Verified and not verified

| Check | Result |
|---|---|
| SQL variances vs Python, all 96 product-step-weeks, to the cent | pass, against PostgreSQL 16 |
| Price + usage = material total | pass |
| Flags equal the Python rule; planted cases flagged; P-A not flagged | pass |
| GitHub Actions workflow | **Not run.** Written and syntax-reviewed only. |

## Limits

- Standards are fixed for the whole period. A real setup needs effective-dated standards, so a
  mid-period change does not look like a variance.
- Labor is one number per step. Splitting it into rate and efficiency variances needs timesheet
  detail, which this data does not have.
- Flags say where to look, not why. The cause still needs an investigation.
