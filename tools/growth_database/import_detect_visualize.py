#!/usr/bin/env python3
"""Import an export, detect growth runs, and generate visualizations."""

from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import create_readable_views
import detect_growth_runs
import generate_growth_timeline as generate_growth_visualization
import import_growth_export


def import_export(
    db_path: Path,
    export_file: Path,
    run_id: str | None,
    allow_unknown_name: bool,
    include_observations: bool,
) -> str:
    source_path = export_file.expanduser().resolve()
    metadata = import_growth_export.resolve_filename_metadata(
        source_path,
        allow_unknown_name or bool(run_id),
    )
    export_id = run_id or metadata["canonical_export_id"] or source_path.stem
    headers, rows = import_growth_export.read_export(source_path)
    sql_names = import_growth_export.unique_names(headers)

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.execute("pragma journal_mode = wal")
        import_growth_export.rebuild_run_tables(
            db,
            export_id,
            source_path,
            metadata,
            headers,
            sql_names,
            rows,
            include_observations=include_observations,
        )

    print(f"Imported {len(rows):,} samples as {export_id}.")
    return str(export_id)


def is_export_candidate(path: Path) -> bool:
    if not path.is_file() or path.suffix.lower() != ".txt":
        return False
    with path.open("r", encoding="utf-8-sig", errors="replace") as handle:
        first_line = handle.readline()
    return len(first_line.split("\t")) >= 10


def detect_runs(
    db_path: Path,
    export_id: str,
    substrate_threshold: float,
    min_duration_seconds: int,
) -> list[str]:
    with sqlite3.connect(db_path) as db:
        metadata = detect_growth_runs.fetch_export_metadata(db, export_id)
        ps_start = metadata["ps_start"] if metadata else None
        sample_labels = detect_growth_runs.labels_from_metadata(metadata)
        intervals = detect_growth_runs.detect_hot_intervals(
            db,
            export_id,
            substrate_threshold,
            min_duration_seconds,
        )
        detect_growth_runs.write_detections(db, export_id, intervals, ps_start, sample_labels)

        run_ids = [
            row[0]
            for row in db.execute(
                """
                select detected_run_id
                from detected_growth_runs
                where parent_export_id = ?
                order by run_number_in_export
                """,
                (export_id,),
            )
        ]

    print(f"Detected {len(run_ids)} growth run(s): {', '.join(run_ids) or 'none'}.")
    return run_ids


def generate_visualizations(db_path: Path, run_ids: list[str], output_dir: Path) -> list[Path]:
    outputs: list[Path] = []
    output_dir.mkdir(parents=True, exist_ok=True)

    for run_id in run_ids:
        output = output_dir / f"{run_id}.html"
        with sqlite3.connect(db_path) as db:
            db.row_factory = sqlite3.Row
            detected, export, rows = generate_growth_visualization.load_run(db, run_id)
            window_start = (
                generate_growth_visualization.dt.datetime.fromisoformat(export["window_start_at"])
                if export["window_start_at"]
                else generate_growth_visualization.dt.datetime(2000, 1, 1)
            )
            segments = generate_growth_visualization.build_segments(rows, window_start)
            html_text = generate_growth_visualization.render_html(run_id, detected, export, rows, segments)
            output.write_text(html_text, encoding="utf-8")
            layers = [segment for segment in segments if segment["type"] == "growth"]
            generate_growth_visualization.update_index(db, run_id, output, detected, export, layers)
        outputs.append(output)
        print(f"Generated {output}.")

    return outputs


def refresh_readable_views(db_path: Path) -> None:
    with sqlite3.connect(db_path) as db:
        db.executescript(create_readable_views.READABLE_VIEW_SQL)
    print("Refreshed readable views.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_file", type=Path, help="Tab/CSV export file or folder of exports to import")
    parser.add_argument("--db", type=Path, default=Path("data/example_mbe_growth.sqlite"), help="SQLite database path")
    parser.add_argument("--run-id", help="Export id override; defaults to parsed filename metadata")
    parser.add_argument(
        "--allow-unknown-name",
        action="store_true",
        help="Allow filenames that do not match the PS... date/time convention",
    )
    parser.add_argument("--substrate-threshold", type=float, default=300.0)
    parser.add_argument("--min-duration-seconds", type=int, default=300)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("outputs/growth_visualizations"),
        help="Directory for generated HTML visualization files",
    )
    parser.add_argument(
        "--include-observations",
        action="store_true",
        help="Also populate the very large long-form growth_observations table",
    )
    args = parser.parse_args()

    db_path = args.db.expanduser().resolve()
    output_dir = args.output_dir.expanduser()

    source = args.export_file.expanduser().resolve()
    if source.is_dir():
        export_files = sorted(path for path in source.iterdir() if is_export_candidate(path))
        skipped_files = sorted(path.name for path in source.iterdir() if path.suffix.lower() == ".txt" and not is_export_candidate(path))
    else:
        export_files = [source]
        skipped_files = []

    all_outputs: list[Path] = []
    for export_file in export_files:
        print(f"\nProcessing {export_file.name}")
        export_id = import_export(
            db_path,
            export_file,
            args.run_id if len(export_files) == 1 else None,
            args.allow_unknown_name,
            args.include_observations,
        )
        run_ids = detect_runs(
            db_path,
            export_id,
            args.substrate_threshold,
            args.min_duration_seconds,
        )
        all_outputs.extend(generate_visualizations(db_path, run_ids, output_dir))

    refresh_readable_views(db_path)

    print("")
    print("Done.")
    if skipped_files:
        print(f"Skipped non-export-shaped text files: {', '.join(skipped_files)}")
    for output in all_outputs:
        print(f"- /visualizations/{output.name}")


if __name__ == "__main__":
    main()
