#!/usr/bin/env python3
"""Detect candidate MBE growth runs inside a full export."""

from __future__ import annotations

import argparse
import re
import sqlite3


SOURCE_SHUTTERS = {
    "Ga1": "gm1_ga1_tip_shutterstatus",
    "In1": "gm1_in1_tip_shutterstatus",
    "Al1": "gm1_al1_tip_shutterstatus",
}

GROUP_V_SHUTTERS = {
    "As1": "gm1_as1_valve_shutterstatus",
    "Sb": "gen10_200v_sb_valve_shutterstatus",
}


def contiguous_intervals(seconds: list[float], max_gap_seconds: float = 1.1) -> list[tuple[float, float]]:
    if not seconds:
        return []

    intervals = []
    start = previous = seconds[0]
    for second in seconds[1:]:
        if second - previous <= max_gap_seconds:
            previous = second
            continue
        intervals.append((start, previous))
        start = previous = second
    intervals.append((start, previous))
    return intervals


def fetch_export_metadata(db: sqlite3.Connection, export_id: str) -> sqlite3.Row | None:
    db.row_factory = sqlite3.Row
    columns = {
        row[1] for row in db.execute("pragma table_info(raw_exports)").fetchall()
    }
    sample_labels_sql = "sample_labels" if "sample_labels" in columns else "null as sample_labels"
    return db.execute(
        f"""
        select export_id, ps_start, ps_end, {sample_labels_sql}
        from raw_exports
        where export_id = ?
        """,
        (export_id,),
    ).fetchone()


def labels_from_metadata(metadata: sqlite3.Row | None) -> list[str]:
    if not metadata:
        return []
    sample_labels = metadata["sample_labels"] if "sample_labels" in metadata.keys() else None
    if not sample_labels:
        return []
    return [label.strip() for label in sample_labels.split(",") if label.strip()]


def ps_number_from_label(label: str) -> int | None:
    match = re.fullmatch(r"PS0*(\d+)", label, re.IGNORECASE)
    return int(match.group(1)) if match else None


def label_for_detection(
    index: int,
    interval_count: int,
    sample_labels: list[str],
    ps_start: int | None,
    export_id: str,
) -> tuple[str, int | None, str | None]:
    if len(sample_labels) == interval_count:
        label = sample_labels[index - 1]
        return label, ps_number_from_label(label), None

    if sample_labels and len(sample_labels) < interval_count:
        if len(sample_labels) == interval_count - 1 and len(sample_labels) >= 2:
            expanded_labels = [sample_labels[0], "fail", *sample_labels[1:]]
            label = expanded_labels[index - 1]
            return label, ps_number_from_label(label), (
                "More detected runs than filename labels; inserted fail label."
            )
        if index <= len(sample_labels):
            label = sample_labels[index - 1]
            return label, ps_number_from_label(label), (
                "Detected run count does not match filename labels."
            )

    ps_number = ps_start + index - 1 if ps_start else None
    label = f"PS{ps_number}" if ps_number else f"{export_id}_run_{index}"
    return label, ps_number, None


def detect_hot_intervals(
    db: sqlite3.Connection,
    export_id: str,
    substrate_threshold: float,
    min_duration_seconds: int,
    ) -> list[tuple[float, float]]:
    hot_seconds = [
        row[0]
        for row in db.execute(
            """
            select time_seconds
            from growth_measurements
            where run_id = ?
              and gm1_subs_center_measured >= ?
            order by time_seconds
            """,
            (export_id, substrate_threshold),
        )
    ]
    return [
        (start, end)
        for start, end in contiguous_intervals(hot_seconds)
        if end - start >= min_duration_seconds
    ]


def shutter_summary(
    db: sqlite3.Connection,
    export_id: str,
    start_second: float,
    end_second: float,
    shutters: dict[str, str],
) -> tuple[int | None, int | None, str]:
    open_events: list[tuple[str, float, float]] = []
    for source, column in shutters.items():
        rows = [
            row[0]
            for row in db.execute(
                f"""
                select time_seconds
                from growth_measurements
                where run_id = ?
                  and time_seconds between ? and ?
                  and {column} = 0
                order by time_seconds
                """,
                (export_id, start_second, end_second),
            )
        ]
        for interval_start, interval_end in contiguous_intervals(rows):
            open_events.append((source, interval_start, interval_end))

    if not open_events:
        return None, None, ""

    open_sources = sorted({source for source, _, _ in open_events})
    return (
        min(start for _, start, _ in open_events),
        max(end for _, _, end in open_events),
        ",".join(open_sources),
    )


def write_detections(
    db: sqlite3.Connection,
    export_id: str,
    intervals: list[tuple[float, float]],
    ps_start: int | None,
    sample_labels: list[str] | None = None,
) -> None:
    db.execute(
        """
        create table if not exists detected_growth_runs (
            detected_run_id text primary key,
            parent_export_id text not null,
            run_number_in_export integer not null,
            sample_label text,
            ps_number integer,
            start_second integer not null,
            end_second integer not null,
            duration_seconds integer not null,
            max_substrate_temp real,
            source_shutter_start_second integer,
            source_shutter_end_second integer,
            source_shutters_opened text,
            group_v_start_second integer,
            group_v_end_second integer,
            group_v_shutters_opened text,
            confidence real not null,
            notes text
        )
        """
    )
    existing_columns = {
        row[1] for row in db.execute("pragma table_info(detected_growth_runs)").fetchall()
    }
    if "sample_label" not in existing_columns:
        db.execute("alter table detected_growth_runs add column sample_label text")
    db.execute("delete from detected_growth_runs where parent_export_id = ?", (export_id,))

    labels = sample_labels or []
    for index, (start_second, end_second) in enumerate(intervals, start=1):
        preferred_run_id, ps_number, label_note = label_for_detection(
            index,
            len(intervals),
            labels,
            ps_start,
            export_id,
        )
        collision = db.execute(
            """
            select 1
            from detected_growth_runs
            where detected_run_id = ?
              and parent_export_id != ?
            """,
            (preferred_run_id, export_id),
        ).fetchone()
        detected_run_id = preferred_run_id if not collision else f"{export_id}_run_{index}"
        max_substrate_temp = db.execute(
            """
            select max(gm1_subs_center_measured)
            from growth_measurements
            where run_id = ?
              and time_seconds between ? and ?
            """,
            (export_id, start_second, end_second),
        ).fetchone()[0]
        source_start, source_end, sources_opened = shutter_summary(
            db, export_id, start_second, end_second, SOURCE_SHUTTERS
        )
        group_v_start, group_v_end, group_v_opened = shutter_summary(
            db, export_id, start_second, end_second, GROUP_V_SHUTTERS
        )

        confidence = 0.75
        notes = "Detected from substrate temperature >= threshold."
        if label_note:
            notes += f" {label_note}"
        if sources_opened:
            confidence += 0.15
            notes += " Source shutter activity found."
        if group_v_opened:
            confidence += 0.10
            notes += " Group V shutter activity found."

        db.execute(
            """
            insert into detected_growth_runs (
                detected_run_id, parent_export_id, run_number_in_export, sample_label, ps_number,
                start_second, end_second, duration_seconds, max_substrate_temp,
                source_shutter_start_second, source_shutter_end_second, source_shutters_opened,
                group_v_start_second, group_v_end_second, group_v_shutters_opened,
                confidence, notes
            )
            values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                detected_run_id,
                export_id,
                index,
                preferred_run_id,
                ps_number,
                start_second,
                end_second,
                int(round(end_second - start_second)),
                max_substrate_temp,
                source_start,
                source_end,
                sources_opened,
                group_v_start,
                group_v_end,
                group_v_opened,
                min(confidence, 0.99),
                notes,
            ),
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_id", help="Imported export/run id to scan")
    parser.add_argument("--db", default="data/example_mbe_growth.sqlite", help="SQLite database path")
    parser.add_argument("--substrate-threshold", type=float, default=300.0)
    parser.add_argument("--min-duration-seconds", type=int, default=300)
    args = parser.parse_args()

    with sqlite3.connect(args.db) as db:
        metadata = fetch_export_metadata(db, args.export_id)
        ps_start = metadata["ps_start"] if metadata else None
        sample_labels = labels_from_metadata(metadata)
        intervals = detect_hot_intervals(
            db,
            args.export_id,
            args.substrate_threshold,
            args.min_duration_seconds,
        )
        write_detections(db, args.export_id, intervals, ps_start, sample_labels)

    print(f"Detected {len(intervals)} candidate growth run(s) in {args.export_id}.")
    for index, (start_second, end_second) in enumerate(intervals, start=1):
        label, _, _ = label_for_detection(index, len(intervals), sample_labels, ps_start, args.export_id)
        print(f"{label}: {start_second}-{end_second} s ({end_second - start_second + 1} s)")


if __name__ == "__main__":
    main()
