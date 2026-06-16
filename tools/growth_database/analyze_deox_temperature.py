#!/usr/bin/env python3
"""Create a separate deox-temperature analysis from detected growth runs."""

from __future__ import annotations

import argparse
import csv
import math
import sqlite3
from pathlib import Path


def percentile(sorted_values: list[float], fraction: float) -> float | None:
    if not sorted_values:
        return None
    if len(sorted_values) == 1:
        return sorted_values[0]
    position = (len(sorted_values) - 1) * fraction
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return sorted_values[lower]
    weight = position - lower
    return sorted_values[lower] * (1 - weight) + sorted_values[upper] * weight


def holder_proxy(deox_temp_c: float | None) -> str:
    if deox_temp_c is None:
        return "unknown"
    if deox_temp_c < 750:
        return "low-temp holder proxy"
    if deox_temp_c < 825:
        return "mid-temp holder proxy"
    if deox_temp_c < 900:
        return "high-temp holder proxy"
    return "outlier / check"


def setup_tables(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        drop view if exists deox_temps_readable;
        drop view if exists deox_temp_statistics_readable;
        drop view if exists deox_temp_bins_readable;
        drop view if exists deox_holder_proxy_summary_readable;
        drop table if exists deox_temps;
        drop table if exists deox_temp_statistics;
        drop table if exists deox_temp_bins;
        drop table if exists deox_holder_proxy_summary;

        create table deox_temps (
            run_id text primary key,
            sample_label text,
            parent_export_id text not null,
            run_number_in_export integer not null,
            ps_number integer,
            sort_ps_number integer,
            deox_temp_c real,
            holder_proxy text not null,
            run_start_second real not null,
            run_end_second real not null,
            run_duration_seconds real not null,
            source_shutters_opened text,
            group_v_shutters_opened text,
            visualization_url text
        );

        create table deox_temp_statistics (
            metric text primary key,
            value real
        );

        create table deox_temp_bins (
            bin_label text primary key,
            min_temp_c real,
            max_temp_c real,
            run_count integer not null
        );

        create table deox_holder_proxy_summary (
            holder_proxy text primary key,
            run_count integer not null,
            min_deox_temp_c real,
            avg_deox_temp_c real,
            max_deox_temp_c real
        );
        """
    )


def create_views(db: sqlite3.Connection) -> None:
    db.executescript(
        """
        create view deox_temps_readable as
        select
            run_id as "Run",
            sample_label as "Sample Label",
            round(deox_temp_c, 1) as "Deox Temp (C)",
            holder_proxy as "Holder Proxy",
            parent_export_id as "Export / Day",
            run_number_in_export as "Run Number In Export",
            ps_number as "PS Number",
            round(run_duration_seconds, 1) as "Run Duration (s)",
            source_shutters_opened as "Source Shutters Opened",
            group_v_shutters_opened as "Group V Shutters Opened",
            visualization_url as "Visualization URL"
        from deox_temps
        order by sort_ps_number, run_number_in_export, run_id;

        create view deox_temp_statistics_readable as
        select
            metric as "Metric",
            case
                when metric = 'run_count' then cast(round(value, 0) as text)
                else printf('%.1f', value)
            end as "Value"
        from deox_temp_statistics
        order by
            case metric
                when 'run_count' then 1
                when 'min_c' then 2
                when 'q1_c' then 3
                when 'median_c' then 4
                when 'mean_c' then 5
                when 'q3_c' then 6
                when 'max_c' then 7
                when 'stddev_c' then 8
                else 99
            end;

        create view deox_temp_bins_readable as
        select
            bin_label as "Deox Temp Bin (C)",
            run_count as "Run Count"
        from deox_temp_bins
        order by min_temp_c;

        create view deox_holder_proxy_summary_readable as
        select
            holder_proxy as "Holder Proxy",
            run_count as "Run Count",
            round(min_deox_temp_c, 1) as "Min Deox Temp (C)",
            round(avg_deox_temp_c, 1) as "Avg Deox Temp (C)",
            round(max_deox_temp_c, 1) as "Max Deox Temp (C)"
        from deox_holder_proxy_summary
        order by
            case holder_proxy
                when 'low-temp holder proxy' then 1
                when 'mid-temp holder proxy' then 2
                when 'high-temp holder proxy' then 3
                when 'outlier / check' then 4
                else 99
            end;
        """
    )


def write_csv(path: Path, rows: list[sqlite3.Row]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        if not rows:
            return
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        for row in rows:
            writer.writerow(dict(row))


def analyze(db: sqlite3.Connection) -> int:
    db.row_factory = sqlite3.Row
    db.execute("pragma busy_timeout = 30000")
    setup_tables(db)

    rows = db.execute(
        """
        select
            d.detected_run_id,
            d.sample_label,
            d.parent_export_id,
            d.run_number_in_export,
            d.ps_number,
            coalesce(d.ps_number, r.ps_start) as sort_ps_number,
            d.max_substrate_temp,
            d.start_second,
            d.end_second,
            d.duration_seconds,
            d.source_shutters_opened,
            d.group_v_shutters_opened,
            coalesce(v.visualization_url, '/visualizations/' || d.detected_run_id || '.html') as visualization_url
        from detected_growth_runs d
        left join raw_exports r on r.export_id = d.parent_export_id
        left join growth_visualization_index v on v.run_id = d.detected_run_id
        where d.max_substrate_temp is not null
        order by coalesce(d.ps_number, r.ps_start), d.run_number_in_export, d.detected_run_id
        """
    ).fetchall()

    for row in rows:
        db.execute(
            """
            insert into deox_temps (
                run_id, sample_label, parent_export_id, run_number_in_export,
                ps_number, sort_ps_number, deox_temp_c, holder_proxy, run_start_second, run_end_second,
                run_duration_seconds, source_shutters_opened,
                group_v_shutters_opened, visualization_url
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["detected_run_id"],
                row["sample_label"],
                row["parent_export_id"],
                row["run_number_in_export"],
                row["ps_number"],
                row["sort_ps_number"],
                row["max_substrate_temp"],
                holder_proxy(row["max_substrate_temp"]),
                row["start_second"],
                row["end_second"],
                row["duration_seconds"],
                row["source_shutters_opened"],
                row["group_v_shutters_opened"],
                row["visualization_url"],
            ),
        )

    values = sorted(float(row["max_substrate_temp"]) for row in rows)
    if values:
        mean = sum(values) / len(values)
        variance = sum((value - mean) ** 2 for value in values) / len(values)
        stats = {
            "run_count": float(len(values)),
            "min_c": min(values),
            "q1_c": percentile(values, 0.25),
            "median_c": percentile(values, 0.50),
            "mean_c": mean,
            "q3_c": percentile(values, 0.75),
            "max_c": max(values),
            "stddev_c": math.sqrt(variance),
        }
        for metric, value in stats.items():
            db.execute(
                "insert into deox_temp_statistics (metric, value) values (?, ?)",
                (metric, value),
            )

    bins = [
        ("<700", None, 700.0),
        ("700-749.9", 700.0, 750.0),
        ("750-799.9", 750.0, 800.0),
        ("800-849.9", 800.0, 850.0),
        ("850-899.9", 850.0, 900.0),
        (">=900", 900.0, None),
    ]
    for label, low, high in bins:
        run_count = sum(
            1
            for value in values
            if (low is None or value >= low) and (high is None or value < high)
        )
        db.execute(
            """
            insert into deox_temp_bins (bin_label, min_temp_c, max_temp_c, run_count)
            values (?, ?, ?, ?)
            """,
            (label, low, high, run_count),
        )

    for proxy in [
        "low-temp holder proxy",
        "mid-temp holder proxy",
        "high-temp holder proxy",
        "outlier / check",
    ]:
        proxy_values = [
            float(row["max_substrate_temp"])
            for row in rows
            if holder_proxy(row["max_substrate_temp"]) == proxy
        ]
        if not proxy_values:
            continue
        db.execute(
            """
            insert into deox_holder_proxy_summary (
                holder_proxy, run_count, min_deox_temp_c,
                avg_deox_temp_c, max_deox_temp_c
            )
            values (?, ?, ?, ?, ?)
            """,
            (
                proxy,
                len(proxy_values),
                min(proxy_values),
                sum(proxy_values) / len(proxy_values),
                max(proxy_values),
            ),
        )

    create_views(db)
    db.commit()
    return len(rows)


def export_outputs(db: sqlite3.Connection, output_dir: Path) -> None:
    db.row_factory = sqlite3.Row
    outputs = {
        "deox_temps.csv": "select * from deox_temps_readable",
        "deox_temp_statistics.csv": "select * from deox_temp_statistics_readable",
        "deox_temp_bins.csv": "select * from deox_temp_bins_readable",
        "deox_holder_proxy_summary.csv": "select * from deox_holder_proxy_summary_readable",
    }
    for filename, query in outputs.items():
        write_csv(output_dir / filename, db.execute(query).fetchall())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=Path("data/example_mbe_growth.sqlite"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/analysis"))
    args = parser.parse_args()

    with sqlite3.connect(args.db) as db:
        db.row_factory = sqlite3.Row
        run_count = analyze(db)
        export_outputs(db, args.output_dir)

    print(f"Analyzed deox temperatures for {run_count} detected run(s).")


if __name__ == "__main__":
    main()
