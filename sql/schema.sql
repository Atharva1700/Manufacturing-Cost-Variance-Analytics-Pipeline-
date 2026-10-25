-- Cost variance schema. Re-runnable: staging tables are truncated by the loader.

create table if not exists standards (
    product text not null,
    step text not null,
    std_kg_per_unit numeric(10,4) not null,
    std_price_per_kg numeric(10,4) not null,
    std_hours_per_unit numeric(10,4) not null,
    std_labor_rate numeric(10,4) not null,
    primary key (product, step)
);

create table if not exists production (
    product text not null,
    step text not null,
    week_start date not null,
    units_started int not null,
    units_good int not null,
    primary key (product, step, week_start)
);

create table if not exists actuals (
    product text not null,
    step text not null,
    week_start date not null,
    material_kg numeric(14,2) not null,
    material_cost numeric(14,2) not null,
    labor_hours numeric(14,2) not null,
    labor_cost numeric(14,2) not null,
    primary key (product, step, week_start)
);

-- Flag thresholds. One row. Change the numbers here, not in code.
create table if not exists thresholds (
    id int primary key default 1 check (id = 1),
    min_pct numeric(6,4) not null,       -- |variance| as a share of standard cost
    min_usd numeric(14,2) not null       -- and at least this many dollars
);
insert into thresholds (id, min_pct, min_usd) values (1, 0.10, 500)
on conflict (id) do nothing;

-- One row per product, step and week. Variances are actual minus standard, so positive = overspend.
create or replace view v_variance as
with std as (
    select p.product, p.step, p.week_start, p.units_good,
           p.units_started * s.std_kg_per_unit     as std_kg,
           s.std_price_per_kg,
           p.units_started * s.std_hours_per_unit  as std_hours,
           s.std_labor_rate
    from production p
    join standards s using (product, step)
)
select std.product, std.step, std.week_start, std.units_good,
       std.std_kg * std.std_price_per_kg                              as std_material_cost,
       a.material_cost                                                as act_material_cost,
       a.material_cost - a.material_kg * std.std_price_per_kg          as material_price_var,
       (a.material_kg - std.std_kg) * std.std_price_per_kg             as material_usage_var,
       std.std_hours * std.std_labor_rate                             as std_labor_cost,
       a.labor_cost                                                   as act_labor_cost,
       a.labor_cost - std.std_hours * std.std_labor_rate              as labor_var,
       (a.material_cost - a.material_kg * std.std_price_per_kg)
         + (a.material_kg - std.std_kg) * std.std_price_per_kg
         + (a.labor_cost - std.std_hours * std.std_labor_rate)        as total_var,
       std.std_kg * std.std_price_per_kg + std.std_hours * std.std_labor_rate as std_total_cost
from std
join actuals a using (product, step, week_start);

-- Rows whose variance is large both as a share of standard cost and in dollars.
create or replace view v_flags as
select v.product, v.step, v.week_start, v.total_var,
       v.material_price_var, v.material_usage_var, v.labor_var,
       round(v.total_var / v.std_total_cost, 4) as var_pct
from v_variance v
cross join thresholds t
where abs(v.total_var / v.std_total_cost) >= t.min_pct
  and abs(v.total_var) >= t.min_usd;

-- Totals by product and step over the whole period.
create or replace view v_variance_by_product_step as
select product, step,
       sum(std_total_cost)     as std_total_cost,
       sum(total_var)          as total_var,
       sum(material_price_var) as material_price_var,
       sum(material_usage_var) as material_usage_var,
       sum(labor_var)          as labor_var,
       round(sum(total_var) / sum(std_total_cost), 4) as var_pct
from v_variance
group by product, step;
