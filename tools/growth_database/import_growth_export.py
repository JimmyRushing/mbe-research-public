#!/usr/bin/env python3
"""Import MBE growth control-point exports into a queryable SQLite database."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import re
import sqlite3
import sys
from pathlib import Path


TYPE_SUFFIXES = {
    "Measured",
    "WorkingSetpoint",
    "Setpoint",
    "ShutterStatus",
    "Value",
    "Status",
    "Control",
}


FILENAME_PATTERN = re.compile(
    r"^PS(?P<ps_start>\d+)"
    r"(?:-PS(?P<ps_end>\d+))?"
    r"-(?P<month>\d{1,2})-(?P<day>\d{1,2})-(?P<year>\d{2}|\d{4})"
    r"-from-(?P<start_hour>\d{1,2})_(?P<start_minute>\d{2})"
    r"-to-(?P<end_hour>\d{1,2})_(?P<end_minute>\d{2})$",
    re.IGNORECASE,
)

NUMERIC_FILENAME_PATTERN = re.compile(r"^(?P<numbers>\d+(?:\s+\d+)*)$")
SAMPLE_TOKEN_FILENAME_PATTERN = re.compile(r"^(?P<tokens>(?:\d+|fail)(?:\s+(?:\d+|fail))*)$", re.IGNORECASE)


def sample_label_from_token(token: str) -> str:
    if token.lower() == "fail":
        return "fail"
    return f"PS{int(token)}"


def sample_number_from_label(label: str) -> int | None:
    match = re.fullmatch(r"PS0*(\d+)", label, re.IGNORECASE)
    return int(match.group(1)) if match else None


def parse_filename_metadata(path: Path) -> dict[str, str | int | None]:
    match = FILENAME_PATTERN.match(path.stem)
    if not match:
        numeric_match = NUMERIC_FILENAME_PATTERN.match(path.stem)
        if numeric_match:
            ps_numbers = [int(number) for number in numeric_match.group("numbers").split()]
            ps_start = min(ps_numbers)
            ps_end = max(ps_numbers)
            ps_label = f"PS{ps_start:03d}" if ps_start == ps_end else f"PS{ps_start:03d}-PS{ps_end:03d}"
            return {
                "name_status": "parsed_ps_numbers",
                "ps_start": ps_start,
                "ps_end": ps_end,
                "sample_labels": ",".join(f"PS{number}" for number in ps_numbers),
                "export_date": None,
                "window_start_time": None,
                "window_end_time": None,
                "window_start_at": None,
                "window_end_at": None,
                "canonical_export_id": ps_label,
            }
        sample_token_match = SAMPLE_TOKEN_FILENAME_PATTERN.match(path.stem)
        if sample_token_match:
            tokens = sample_token_match.group("tokens").split()
            sample_labels = [sample_label_from_token(token) for token in tokens]
            ps_numbers = [
                number
                for label in sample_labels
                if (number := sample_number_from_label(label)) is not None
            ]
            ps_start = min(ps_numbers) if ps_numbers else None
            ps_end = max(ps_numbers) if ps_numbers else None
            canonical_export_id = "-".join(sample_labels)
            return {
                "name_status": "parsed_sample_tokens",
                "ps_start": ps_start,
                "ps_end": ps_end,
                "sample_labels": ",".join(sample_labels),
                "export_date": None,
                "window_start_time": None,
                "window_end_time": None,
                "window_start_at": None,
                "window_end_at": None,
                "canonical_export_id": canonical_export_id,
            }
        return {
            "name_status": "unknown",
            "ps_start": None,
            "ps_end": None,
            "sample_labels": None,
            "export_date": None,
            "window_start_time": None,
            "window_end_time": None,
            "window_start_at": None,
            "window_end_at": None,
            "canonical_export_id": None,
        }

    parts = match.groupdict()
    year = int(parts["year"])
    if year < 100:
        year += 2000
    month = int(parts["month"])
    day = int(parts["day"])
    start_hour = int(parts["start_hour"])
    start_minute = int(parts["start_minute"])
    end_hour = int(parts["end_hour"])
    end_minute = int(parts["end_minute"])

    export_date = dt.date(year, month, day)
    start_at = dt.datetime(year, month, day, start_hour, start_minute)
    end_at = dt.datetime(year, month, day, end_hour, end_minute)
    if end_at <= start_at:
        end_at += dt.timedelta(days=1)

    ps_start = int(parts["ps_start"])
    ps_end = int(parts["ps_end"] or parts["ps_start"])
    ps_label = f"PS{ps_start}" if ps_start == ps_end else f"PS{ps_start}-PS{ps_end}"
    sample_labels = ",".join(f"PS{number}" for number in range(ps_start, ps_end + 1))
    canonical_export_id = (
        f"{ps_label}_{export_date.isoformat()}_"
        f"{start_at.strftime('%H%M')}-{end_at.strftime('%H%M')}"
    )

    return {
        "name_status": "parsed",
        "ps_start": ps_start,
        "ps_end": ps_end,
        "sample_labels": sample_labels,
        "export_date": export_date.isoformat(),
        "window_start_time": start_at.strftime("%H:%M"),
        "window_end_time": end_at.strftime("%H:%M"),
        "window_start_at": start_at.isoformat(timespec="minutes"),
        "window_end_at": end_at.isoformat(timespec="minutes"),
        "canonical_export_id": canonical_export_id,
    }


def resolve_filename_metadata(path: Path, allow_unknown_name: bool) -> dict[str, str | int | None]:
    metadata = parse_filename_metadata(path)
    if metadata["name_status"] in {"parsed", "parsed_ps_numbers", "parsed_sample_tokens"} or allow_unknown_name:
        return metadata

    expected = "PS139-PS141-04-06-26-from-6_00-to-23_30.txt"
    message = (
        f"Filename does not match the expected convention.\n"
        f"  Found: {path.name}\n"
        f"  Expected like: {expected}\n"
    )
    if not sys.stdin.isatty():
        raise ValueError(
            message
            + "Rename the file or rerun with --allow-unknown-name and --run-id if this is intentional."
        )

    print(message)
    answer = input("Continue anyway with unknown date/time metadata? [y/N] ").strip().lower()
    if answer not in {"y", "yes"}:
        raise SystemExit("Import cancelled. Rename the file or provide clarification.")
    return metadata


def slugify(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z]+", "_", value).strip("_").lower()
    if not cleaned:
        cleaned = "column"
    if cleaned[0].isdigit():
        cleaned = f"c_{cleaned}"
    return cleaned


def unique_names(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    names: list[str] = []
    for header in headers:
        base = "time_seconds" if header == "Time(seconds)" else slugify(header.replace("Instances.", ""))
        count = seen.get(base, 0)
        seen[base] = count + 1
        names.append(base if count == 0 else f"{base}_{count + 1}")
    return names


def parse_control_point(original_name: str) -> tuple[str, str]:
    if original_name == "Time(seconds)":
        return "time", "seconds"

    trimmed = original_name.removeprefix("Instances.")
    parts = trimmed.rsplit(".", 1)
    if len(parts) == 2 and parts[1] in TYPE_SUFFIXES:
        return parts[0], parts[1]
    return trimmed, ""


def parse_value(value: str) -> float | int | None:
    value = value.strip()
    if value == "":
        return None
    try:
        number = float(value)
    except ValueError:
        return value
    if number.is_integer():
        return int(number)
    return number


def quote_ident(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def sniff_dialect(path: Path) -> csv.Dialect:
    sample = path.read_text(encoding="utf-8-sig", errors="replace")[:8192]
    try:
        return csv.Sniffer().sniff(sample, delimiters="\t,;")
    except csv.Error:
        dialect = csv.excel_tab
        return dialect


def read_export(path: Path) -> tuple[list[str], list[list[float | int | str | None]]]:
    dialect = sniff_dialect(path)
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        reader = csv.reader(handle, dialect)
        headers = next(reader)
        rows = [[parse_value(cell) for cell in row] for row in reader if row]

    expected = len(headers)
    bad_rows = [index + 2 for index, row in enumerate(rows) if len(row) != expected]
    if bad_rows:
        preview = ", ".join(str(row_num) for row_num in bad_rows[:5])
        raise ValueError(f"{path} has rows with unexpected column counts: {preview}")
    return headers, rows


def rebuild_run_tables(
    db: sqlite3.Connection,
    run_id: str,
    source_path: Path,
    metadata: dict[str, str | int | None],
    headers: list[str],
    sql_names: list[str],
    rows: list[list[float | int | str | None]],
    include_observations: bool = True,
) -> None:
    now = dt.datetime.now(dt.timezone.utc).isoformat()
    duration = max((row[0] for row in rows if isinstance(row[0], (int, float))), default=None)

    db.execute(
        """
        create table if not exists growth_runs (
            run_id text primary key,
            source_file text not null,
            imported_at text not null,
            sample_count integer not null,
            duration_seconds real,
            name_status text,
            ps_start integer,
            ps_end integer,
            sample_labels text,
            export_date text,
            window_start_time text,
            window_end_time text,
            window_start_at text,
            window_end_at text
        )
        """
    )
    existing_growth_run_columns = {
        row[1] for row in db.execute("pragma table_info(growth_runs)").fetchall()
    }
    growth_run_column_types = {
        "name_status": "text",
        "ps_start": "integer",
        "ps_end": "integer",
        "sample_labels": "text",
        "export_date": "text",
        "window_start_time": "text",
        "window_end_time": "text",
        "window_start_at": "text",
        "window_end_at": "text",
    }
    for column, column_type in growth_run_column_types.items():
        if column not in existing_growth_run_columns:
            db.execute(f"alter table growth_runs add column {column} {column_type}")

    db.execute(
        """
        create table if not exists control_points (
            sql_name text primary key,
            original_name text not null,
            device text not null,
            signal text not null
        )
        """
    )

    db.execute(
        """
        create table if not exists raw_exports (
            export_id text primary key,
            source_file text not null,
            imported_at text not null,
            sample_count integer not null,
            duration_seconds real,
            name_status text not null,
            ps_start integer,
            ps_end integer,
            sample_labels text,
            export_date text,
            window_start_time text,
            window_end_time text,
            window_start_at text,
            window_end_at text
        )
        """
    )
    existing_raw_export_columns = {
        row[1] for row in db.execute("pragma table_info(raw_exports)").fetchall()
    }
    if "sample_labels" not in existing_raw_export_columns:
        db.execute("alter table raw_exports add column sample_labels text")

    db.execute("delete from growth_runs where run_id = ?", (run_id,))
    db.execute(
        """
        insert into growth_runs (
            run_id, source_file, imported_at, sample_count, duration_seconds,
            name_status, ps_start, ps_end, sample_labels, export_date, window_start_time,
            window_end_time, window_start_at, window_end_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            str(source_path),
            now,
            len(rows),
            duration,
            metadata["name_status"],
            metadata["ps_start"],
            metadata["ps_end"],
            metadata["sample_labels"],
            metadata["export_date"],
            metadata["window_start_time"],
            metadata["window_end_time"],
            metadata["window_start_at"],
            metadata["window_end_at"],
        ),
    )
    db.execute("delete from raw_exports where export_id = ?", (run_id,))
    db.execute(
        """
        insert into raw_exports (
            export_id, source_file, imported_at, sample_count, duration_seconds,
            name_status, ps_start, ps_end, sample_labels, export_date, window_start_time,
            window_end_time, window_start_at, window_end_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            str(source_path),
            now,
            len(rows),
            duration,
            metadata["name_status"],
            metadata["ps_start"],
            metadata["ps_end"],
            metadata["sample_labels"],
            metadata["export_date"],
            metadata["window_start_time"],
            metadata["window_end_time"],
            metadata["window_start_at"],
            metadata["window_end_at"],
        ),
    )

    db.executemany(
        "delete from control_points where sql_name = ?",
        [(sql_name,) for sql_name in sql_names],
    )
    db.executemany(
        """
        insert into control_points (sql_name, original_name, device, signal)
        values (?, ?, ?, ?)
        """,
        [
            (sql_name, original, *parse_control_point(original))
            for original, sql_name in zip(headers, sql_names)
        ],
    )

    columns_sql = ["run_id text not null"] + [
        f"{quote_ident(name)} real" if name != "time_seconds" else f"{quote_ident(name)} integer not null"
        for name in sql_names
    ]
    db.execute(f"create table if not exists growth_measurements ({', '.join(columns_sql)})")
    existing_columns = {
        row[1] for row in db.execute("pragma table_info(growth_measurements)").fetchall()
    }
    for name in sql_names:
        if name not in existing_columns:
            column_type = "integer" if name == "time_seconds" else "real"
            db.execute(f"alter table growth_measurements add column {quote_ident(name)} {column_type}")

    insert_columns = ["run_id"] + sql_names
    placeholders = ", ".join(["?"] * len(insert_columns))
    insert_sql = (
        f"insert into growth_measurements ({', '.join(quote_ident(name) for name in insert_columns)}) "
        f"values ({placeholders})"
    )
    db.execute("delete from growth_measurements where run_id = ?", (run_id,))
    db.executemany(insert_sql, [(run_id, *row) for row in rows])
    db.execute("create index if not exists idx_growth_measurements_run_time on growth_measurements (run_id, time_seconds)")

    existing_tables = {
        row[0]
        for row in db.execute(
            "select name from sqlite_master where type = 'table'"
        ).fetchall()
    }

    if include_observations:
        db.execute(
            """
            create table if not exists growth_observations (
                run_id text not null,
                time_seconds integer not null,
                control_point text not null,
                value real
            )
            """
        )
        db.execute("delete from growth_observations where run_id = ?", (run_id,))
        observation_rows = []
        for row in rows:
            time_seconds = row[0]
            for sql_name, value in zip(sql_names[1:], row[1:]):
                observation_rows.append((run_id, time_seconds, sql_name, value))
        db.executemany(
            """
            insert into growth_observations (run_id, time_seconds, control_point, value)
            values (?, ?, ?, ?)
            """,
            observation_rows,
        )
        db.execute("create index if not exists idx_growth_observations_signal on growth_observations (control_point, run_id, time_seconds)")
        db.execute("create index if not exists idx_growth_observations_time on growth_observations (run_id, time_seconds)")
    elif "growth_observations" in existing_tables:
        db.execute("delete from growth_observations where run_id = ?", (run_id,))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_file", type=Path, help="Tab/CSV export file from the MBE growth run")
    parser.add_argument("--db", type=Path, default=Path("data/example_mbe_growth.sqlite"), help="SQLite database path")
    parser.add_argument("--run-id", help="Run/export id to store; defaults to the parsed canonical export id")
    parser.add_argument(
        "--allow-unknown-name",
        action="store_true",
        help="Allow files that do not match PS139-PS141-04-06-26-from-6_00-to-23_30.txt style naming",
    )
    parser.add_argument(
        "--skip-observations",
        action="store_true",
        help="Skip long-form growth_observations rows; useful for bulk imports",
    )
    args = parser.parse_args()

    source_path = args.export_file.expanduser().resolve()
    db_path = args.db.expanduser().resolve()
    metadata = resolve_filename_metadata(source_path, args.allow_unknown_name or bool(args.run_id))
    run_id = args.run_id or metadata["canonical_export_id"] or source_path.stem

    headers, rows = read_export(source_path)
    sql_names = unique_names(headers)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("pragma journal_mode = wal")
        rebuild_run_tables(
            db,
            run_id,
            source_path,
            metadata,
            headers,
            sql_names,
            rows,
            include_observations=not args.skip_observations,
        )

    print(f"Imported {len(rows):,} samples from {source_path.name} as run {run_id}.")
    if metadata["name_status"] == "parsed":
        print(
            "Parsed filename metadata: "
            f"PS{metadata['ps_start']}-PS{metadata['ps_end']} on {metadata['export_date']} "
            f"from {metadata['window_start_time']} to {metadata['window_end_time']}."
        )
    else:
        print("Filename metadata: unknown/manual.")
    print(f"Database: {db_path}")
    print(f"Tables: raw_exports, growth_runs, control_points, growth_measurements, growth_observations")


if __name__ == "__main__":
    main()
