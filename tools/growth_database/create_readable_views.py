#!/usr/bin/env python3
"""Create browser-friendly Datasette views for MBE growth data."""

from __future__ import annotations

import argparse
import sqlite3


READABLE_VIEW_SQL = """
drop view if exists growth_measurements_readable;
drop view if exists final_sb_step_summary;

create view growth_measurements_readable as
select
  m.run_id as "Run / Export ID",
  datetime(coalesce(g.window_start_at, r.window_start_at), '+' || m.time_seconds || ' seconds') as "Timestamp",
  time(coalesce(g.window_start_at, r.window_start_at), '+' || m.time_seconds || ' seconds') as "Clock Time",
  m.time_seconds as "Elapsed Seconds",
  round(m.gm1_subs_center_measured, 3) as "Substrate Temp Measured (C)",
  round(m.gm1_subs_center_setpoint, 3) as "Substrate Temp Setpoint (C)",
  printf('%.3e', m.growth_module_1_iongauge1_measured) as "Growth Chamber Pressure",
  printf('%.3e', m.pm1_vacuum_reading) as "PM1 Vacuum Reading (ion pump?)",
  case
    when m.gen10_200v_sb_valve_shutterstatus = 0 then 'open'
    when m.gen10_200v_sb_valve_shutterstatus = 1 then 'closed'
  end as "Sb Shutter",
  round(m.gen10_200v_sb_valve_measured, 3) as "Sb Valve Measured",
  round(m.gen10_200v_sb_valve_setpoint, 3) as "Sb Valve Setpoint",
  case
    when m.gm1_as1_valve_shutterstatus = 0 then 'open'
    when m.gm1_as1_valve_shutterstatus = 1 then 'closed'
  end as "As Shutter",
  round(m.gm1_as1_valve_measured, 3) as "As Valve Measured",
  round(m.gm1_as1_valve_setpoint, 3) as "As Valve Setpoint",
  case
    when m.gm1_ga1_tip_shutterstatus = 0 then 'open'
    when m.gm1_ga1_tip_shutterstatus = 1 then 'closed'
  end as "Ga Shutter",
  round(m.gm1_ga1_tip_measured, 3) as "Ga Tip Temp Measured (C)",
  round(m.gm1_ga1_tip_setpoint, 3) as "Ga Tip Temp Setpoint (C)",
  case
    when m.gm1_in1_tip_shutterstatus = 0 then 'open'
    when m.gm1_in1_tip_shutterstatus = 1 then 'closed'
  end as "In Shutter",
  round(m.gm1_in1_tip_measured, 3) as "In Tip Temp Measured (C)",
  round(m.gm1_in1_tip_setpoint, 3) as "In Tip Temp Setpoint (C)",
  case
    when m.gm1_al1_tip_shutterstatus = 0 then 'open'
    when m.gm1_al1_tip_shutterstatus = 1 then 'closed'
  end as "Al Shutter",
  round(m.gm1_al1_base_measured, 3) as "Al Base Temp Measured (C)",
  round(m.gm1_al1_base_setpoint, 3) as "Al Base Temp Setpoint (C)",
  case
    when m.gm1_mainshutter_status_value = 0 then 'closed'
    when m.gm1_mainshutter_status_value = 1 then 'open'
    else cast(m.gm1_mainshutter_status_value as text)
  end as "Main Shutter",
  round(m.gm1_subs_rot_measured, 3) as "Substrate Rotation Measured",
  round(m.gm1_subs_rot_setpoint, 3) as "Substrate Rotation Setpoint"
from growth_measurements m
left join growth_runs g on g.run_id = m.run_id
left join raw_exports r on r.export_id = m.run_id;

create view final_sb_step_summary as
with sb_open as (
  select
    d.detected_run_id,
    d.parent_export_id,
    m.time_seconds,
    m.gm1_subs_center_measured as substrate_temp,
    m.growth_module_1_iongauge1_measured as chamber_pressure,
    m.pm1_vacuum_reading as pm1_vacuum_reading
  from detected_growth_runs d
  join growth_measurements m
    on m.run_id = d.parent_export_id
   and m.time_seconds between d.start_second and d.end_second
  where m.gen10_200v_sb_valve_shutterstatus = 0
),
grouped as (
  select
    detected_run_id,
    parent_export_id,
    time_seconds,
    substrate_temp,
    chamber_pressure,
    pm1_vacuum_reading,
    time_seconds - row_number() over (
      partition by detected_run_id
      order by time_seconds
    ) as grp
  from sb_open
),
intervals as (
  select
    detected_run_id,
    parent_export_id,
    min(time_seconds) as start_second,
    max(time_seconds) as end_second,
    count(*) as duration_seconds,
    min(substrate_temp) as min_substrate_temp,
    avg(substrate_temp) as avg_substrate_temp,
    max(substrate_temp) as max_substrate_temp,
    avg(chamber_pressure) as avg_chamber_pressure,
    avg(pm1_vacuum_reading) as avg_pm1_vacuum_reading
  from grouped
  group by detected_run_id, parent_export_id, grp
),
ranked as (
  select
    *,
    row_number() over (
      partition by detected_run_id
      order by end_second desc
    ) as rn
  from intervals
)
select
  ranked.detected_run_id as "Run",
  datetime(r.window_start_at, '+' || ranked.start_second || ' seconds') as "Sb Open Start",
  datetime(r.window_start_at, '+' || ranked.end_second || ' seconds') as "Sb Open End",
  ranked.start_second as "Start Elapsed Seconds",
  ranked.end_second as "End Elapsed Seconds",
  ranked.duration_seconds as "Duration (s)",
  round(ranked.duration_seconds / 60.0, 2) as "Duration (min)",
  round(ranked.min_substrate_temp, 2) as "Min Substrate Temp (C)",
  round(ranked.avg_substrate_temp, 2) as "Avg Substrate Temp (C)",
  round(ranked.max_substrate_temp, 2) as "Max Substrate Temp (C)",
  printf('%.3e', ranked.avg_chamber_pressure) as "Avg Growth Chamber Pressure",
  printf('%.3e', ranked.avg_pm1_vacuum_reading) as "Avg PM1 Vacuum Reading (ion pump?)"
from ranked
join raw_exports r on r.export_id = ranked.parent_export_id
where ranked.rn = 1;
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="data/example_mbe_growth.sqlite", help="SQLite database path")
    args = parser.parse_args()

    with sqlite3.connect(args.db) as db:
        db.executescript(READABLE_VIEW_SQL)

    print("Created views: growth_measurements_readable, final_sb_step_summary")


if __name__ == "__main__":
    main()
