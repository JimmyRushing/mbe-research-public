"""Create Datasette-friendly views for BFM/ion-gauge proxy checks."""

from __future__ import annotations

import argparse
import sqlite3
from pathlib import Path


def create_views(db: sqlite3.Connection) -> None:
    measurement_columns = {
        row[1] for row in db.execute("pragma table_info(growth_measurements)").fetchall()
    }
    has_bfm_reading = "gm1_bfm_reading" in measurement_columns
    bfm_reading_expr = (
        "m.gm1_bfm_reading" if has_bfm_reading else "null"
    )
    arm_bfm_summary = f"""
            count({bfm_reading_expr}) as "BFM Reading Samples",
            case when count({bfm_reading_expr}) > 0 then printf('%.3e', avg({bfm_reading_expr})) end as "Avg BFM Reading",
            case when count({bfm_reading_expr}) > 0 then printf('%.3e', min({bfm_reading_expr})) end as "Min BFM Reading",
            case when count({bfm_reading_expr}) > 0 then printf('%.3e', max({bfm_reading_expr})) end as "Max BFM Reading","""
    single_bfm_summary = """
            count(bfm_reading_for_analysis) as "BFM Reading Samples",
            case when count(bfm_reading_for_analysis) > 0 then printf('%.3e', avg(bfm_reading_for_analysis)) end as "Avg BFM Reading",
            case when count(bfm_reading_for_analysis) > 0 then printf('%.3e', min(bfm_reading_for_analysis)) end as "Min BFM Reading",
            case when count(bfm_reading_for_analysis) > 0 then printf('%.3e', max(bfm_reading_for_analysis)) end as "Max BFM Reading","""
    window_bfm_summary = """
            bfm_reading_samples as "BFM Reading Samples",
            case when bfm_reading_samples > 0 then printf('%.3e', avg_bfm_reading) end as "Avg BFM Reading",
            case when bfm_reading_samples > 0 then printf('%.3e', min_bfm_reading) end as "Min BFM Reading",
            case when bfm_reading_samples > 0 then printf('%.3e', max_bfm_reading) end as "Max BFM Reading","""

    db.executescript(
        f"""
        drop view if exists bfm_ion_gauge_candidates_readable;
        drop view if exists bfm_arm_state_summary_readable;
        drop view if exists bfm_single_shutter_summary_readable;
        drop view if exists bfm_single_shutter_windows_readable;

        create view bfm_ion_gauge_candidates_readable as
        select
            sql_name as "Database Column",
            original_name as "Export Header",
            device as "Device",
            signal as "Signal"
        from control_points
        where lower(original_name) like '%ion%'
           or lower(original_name) like '%gauge%'
           or lower(original_name) like '%vacuum%'
           or lower(original_name) like '%bfm%'
           or lower(original_name) like '%pressure%'
        order by original_name;

        create view bfm_arm_state_summary_readable as
        select
            case m.gm1_bfm_arm_control_value
                when 1 then 'extended'
                when 0 then 'retracted'
                else cast(m.gm1_bfm_arm_control_value as text)
            end as "BFM Arm Control",
            m.gm1_bfm_arm_status_value as "BFM Arm Status Raw",
            case m.gm1_mainshutter_status_value
                when 1 then 'open'
                when 0 then 'closed'
                else cast(m.gm1_mainshutter_status_value as text)
            end as "Main Shutter Status",
            m.gm1_mainshutter_status_value as "Main Shutter Status Raw",
            count(*) as "Samples",
{arm_bfm_summary}
            printf('%.3e', avg(m.growth_module_1_iongauge1_measured)) as "Avg Growth Module IonGauge1",
            printf('%.3e', max(m.growth_module_1_iongauge1_measured)) as "Max Growth Module IonGauge1",
            printf('%.3e', avg(m.pm1_vacuum_reading)) as "Avg PM1 Vacuum",
            printf('%.3e', max(m.pm1_vacuum_reading)) as "Max PM1 Vacuum"
        from growth_measurements m
        group by
            m.gm1_bfm_arm_control_value,
            m.gm1_bfm_arm_status_value,
            m.gm1_mainshutter_status_value
        order by
            m.gm1_bfm_arm_control_value,
            m.gm1_mainshutter_status_value;

        create view bfm_single_shutter_summary_readable as
        with single as (
            select
                m.*,
                {bfm_reading_expr} as bfm_reading_for_analysis,
                case
                    when m.gm1_ga1_tip_shutterstatus = 0 then 'Ga'
                    when m.gm1_in1_tip_shutterstatus = 0 then 'In'
                    when m.gm1_al1_tip_shutterstatus = 0 then 'Al'
                    when m.gm1_as1_valve_shutterstatus = 0 then 'As'
                    when m.gen10_200v_sb_valve_shutterstatus = 0 then 'Sb'
                end as open_source
            from growth_measurements m
            where m.gm1_bfm_arm_control_value = 1
              and (
                case when m.gm1_ga1_tip_shutterstatus = 0 then 1 else 0 end +
                case when m.gm1_in1_tip_shutterstatus = 0 then 1 else 0 end +
                case when m.gm1_al1_tip_shutterstatus = 0 then 1 else 0 end +
                case when m.gm1_as1_valve_shutterstatus = 0 then 1 else 0 end +
                case when m.gen10_200v_sb_valve_shutterstatus = 0 then 1 else 0 end
              ) = 1
        )
        select
            open_source as "Only Open Shutter",
            count(*) as "Samples",
            count(distinct run_id) as "Exports",
{single_bfm_summary}
            printf('%.3e', avg(growth_module_1_iongauge1_measured)) as "Avg Growth Module IonGauge1",
            printf('%.3e', min(growth_module_1_iongauge1_measured)) as "Min Growth Module IonGauge1",
            printf('%.3e', max(growth_module_1_iongauge1_measured)) as "Max Growth Module IonGauge1",
            printf('%.3e', avg(pm1_vacuum_reading)) as "Avg PM1 Vacuum",
            printf('%.3e', min(pm1_vacuum_reading)) as "Min PM1 Vacuum",
            printf('%.3e', max(pm1_vacuum_reading)) as "Max PM1 Vacuum"
        from single
        group by open_source
        order by avg(growth_module_1_iongauge1_measured) desc;

        create view bfm_single_shutter_windows_readable as
        with marked as (
            select
                m.run_id,
                m.time_seconds,
                (
                    case when m.gm1_ga1_tip_shutterstatus = 0 then 1 else 0 end +
                    case when m.gm1_in1_tip_shutterstatus = 0 then 1 else 0 end +
                    case when m.gm1_al1_tip_shutterstatus = 0 then 1 else 0 end +
                    case when m.gm1_as1_valve_shutterstatus = 0 then 1 else 0 end +
                    case when m.gen10_200v_sb_valve_shutterstatus = 0 then 1 else 0 end
                ) as open_shutter_count,
                case
                    when m.gm1_ga1_tip_shutterstatus = 0 then 'Ga'
                    when m.gm1_in1_tip_shutterstatus = 0 then 'In'
                    when m.gm1_al1_tip_shutterstatus = 0 then 'Al'
                    when m.gm1_as1_valve_shutterstatus = 0 then 'As'
                    when m.gen10_200v_sb_valve_shutterstatus = 0 then 'Sb'
                    else 'none'
                end as open_source,
                {bfm_reading_expr} as gm1_bfm_reading,
                m.growth_module_1_iongauge1_measured,
                m.pm1_vacuum_reading,
                case
                    when m.gm1_ga1_tip_shutterstatus = 0 then m.gm1_ga1_tip_measured
                    when m.gm1_in1_tip_shutterstatus = 0 then m.gm1_in1_tip_measured
                    when m.gm1_al1_tip_shutterstatus = 0 then m.gm1_al1_base_measured
                    when m.gm1_as1_valve_shutterstatus = 0 then m.gm1_as1_bulk_measured
                    when m.gen10_200v_sb_valve_shutterstatus = 0 then m.gen10_200v_sb_bulk_measured
                end as source_temperature_c,
                row_number() over (
                    partition by m.run_id
                    order by m.time_seconds
                ) as rn_all,
                row_number() over (
                    partition by
                        m.run_id,
                        m.gm1_ga1_tip_shutterstatus,
                        m.gm1_in1_tip_shutterstatus,
                        m.gm1_al1_tip_shutterstatus,
                        m.gm1_as1_valve_shutterstatus,
                        m.gen10_200v_sb_valve_shutterstatus
                    order by m.time_seconds
                ) as rn_state
            from growth_measurements m
            where m.gm1_bfm_arm_control_value = 1
        ),
        windows as (
            select
                run_id,
                open_source,
                open_shutter_count,
                min(time_seconds) as start_second,
                max(time_seconds) as end_second,
                count(*) as samples,
                count(gm1_bfm_reading) as bfm_reading_samples,
                avg(gm1_bfm_reading) as avg_bfm_reading,
                min(gm1_bfm_reading) as min_bfm_reading,
                max(gm1_bfm_reading) as max_bfm_reading,
                avg(growth_module_1_iongauge1_measured) as avg_growth_ion,
                max(growth_module_1_iongauge1_measured) as max_growth_ion,
                avg(pm1_vacuum_reading) as avg_pm1,
                max(pm1_vacuum_reading) as max_pm1,
                avg(source_temperature_c) as avg_source_temperature_c
            from marked
            group by run_id, open_source, open_shutter_count, rn_all - rn_state
        )
        select
            run_id as "Run/Export",
            open_source as "Only Open Shutter",
            start_second as "Start (s)",
            end_second as "End (s)",
            samples as "Samples",
{window_bfm_summary}
            printf('%.3e', avg_growth_ion) as "Avg Growth Module IonGauge1",
            printf('%.3e', max_growth_ion) as "Max Growth Module IonGauge1",
            printf('%.3e', avg_pm1) as "Avg PM1 Vacuum",
            printf('%.3e', max_pm1) as "Max PM1 Vacuum",
            round(avg_source_temperature_c, 1) as "Avg Source Temp (C)"
        from windows
        where samples >= 20
          and open_shutter_count = 1
        order by bfm_reading_samples desc, avg_bfm_reading desc, avg_growth_ion desc;
        """
    )
    db.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/example_mbe_growth.sqlite"))
    args = parser.parse_args()

    with sqlite3.connect(args.db) as db:
        create_views(db)

    print("Created BFM analysis views.")


if __name__ == "__main__":
    main()
