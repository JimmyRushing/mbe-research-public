# Growth Database And Provenance Demo

Status: `Active workflow tool`

This demo is a high-priority public artifact. It shows how MBE growth days can be converted into structured, queryable, model-ready records without exposing private raw exports or internal growth notes.

Primary public link target: [SQLite/Datasette growth-run import/QC](sqlite-datasette-growth-run-import-qc.html)

## Pipeline

```text
control-point export
  -> SQLite import
  -> readable views
  -> detected growth intervals
  -> timeline visualization
  -> stack schematic
  -> QC / summary tables
```

## Public Demo

The public HTML demo includes a de-identified representative process timeline, workflow summary, and source-script inventory. It shows the shape of the system without publishing raw control-point exports, the full SQLite database, or private run/sample identifiers. It is the intended resume-facing page for:

`SQLite/Datasette growth-run import/QC`

## Public Tools

- [`import_growth_export.py`](../../../tools/growth_database/import_growth_export.py)
- [`detect_growth_runs.py`](../../../tools/growth_database/detect_growth_runs.py)
- [`create_readable_views.py`](../../../tools/growth_database/create_readable_views.py)
- [`import_detect_visualize.py`](../../../tools/growth_database/import_detect_visualize.py)
- [`generate_growth_timeline.py`](../../../tools/growth_database/generate_growth_timeline.py)
- [`generate_stack_schematic.py`](../../../tools/growth_database/generate_stack_schematic.py)

## Development Notes

`create_bfm_analysis_views.py` and `analyze_deox_temperature.py` are included as beta analysis components. They should be documented with sanitized examples before being used as first-click resume links.

## Privacy Boundary

Do not publish real raw control-point exports, full SQLite snapshots, private growth-note PDFs, private identifiers, or facility-specific operational details.
