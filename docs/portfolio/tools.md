# Tool Map

This page maps the public tools by workflow area and development status.

## Cadtronics/k.p Modeling

Status: `Active workflow tool`

Path: [`tools/cadtronics/`](../../tools/cadtronics/)

Purpose: analyze Hamiltonian-based Cadtronics/k.p dispersion outputs for InAs/Ga(In)Sb quantum-well designs.

Key public tools:

- `phase_diagram_explorer.py`: builds standalone interactive phase-diagram HTML from Cadtronics `.dat` sweeps.
- `wurzburg_validation_explorer.py`: builds an interactive explorer for Schmid/Wurzburg-style validation sweeps.
- `wurzburg_phase_slice.py`: generates static and interactive validation outputs for a phase-diagram slice.
- `extract_schmid_fig3a_reference.py`: extracts reference points used for validation comparisons.

Public demo target: [Cadtronics demo](../demos/cadtronics/)

## Growth Database And Provenance

Status: `Active workflow tool`, with selected scripts labeled `Beta`

Path: [`tools/growth_database/`](../../tools/growth_database/)

Purpose: turn MBE control-point exports into queryable records, readable views, detected growth intervals, static timeline visualizations, stack schematics, and QC outputs.

Key public tools:

- `import_growth_export.py`: imports control-point exports into SQLite.
- `detect_growth_runs.py`: detects candidate hot/growth intervals.
- `create_readable_views.py`: builds friendlier SQLite views.
- `generate_growth_timeline.py`: creates HTML/SVG timeline pages for detected growth runs.
- `generate_stack_schematic.py`: creates simplified stack schematics from detected growth segments.
- `create_bfm_analysis_views.py`: beta BFM analysis views.
- `analyze_deox_temperature.py`: beta deox-temperature summary analysis.

Public demo target: [SQLite/Datasette growth-run import/QC](../demos/growth-database/sqlite-datasette-growth-run-import-qc.html)

Privacy boundary: real raw exports, full SQLite databases, private growth notes, and facility-specific operational records are not included.

## Structured Layer-Stack Figures

Status: `Runnable synthetic demonstration`

[Source and input reference](https://github.com/JimmyRushing/mbe-research-public/tree/main/tools/stack_schematic) · [Tutorial and example](../demos/stack-schematic/index.md)

Generate editable SVG figures from explicit layer descriptions, preserving nominal, measured, and unknown thickness labels. The public examples are entirely synthetic. Each output has a small fingerprint record without copied paths or input metadata. Python 3.11+ is sufficient; no external packages are required.

This complements the database-derived schematic tool above. It does not infer a structure from growth duration or claim that a supplied measurement is correct.

## RHEED Geometry and Historical Planning Tools

Status: `Interactive geometry demonstration`

[Open the current geometry visualizer](../demos/rheed/geometry-visualizer.html) · [Guide and scope](../demos/rheed/index.md)

Explore how beam steering, sample offset, and holder rotation change alignment for co-mounted (001)/(111) samples. The current visualizer shows beam azimuth, footprint, and candidate zone-axis alignment using illustrative geometry and calibration values. Its outputs are not calibrated equipment setpoints.

Historical source tools remain available at [`tools/rheed/`](https://github.com/JimmyRushing/mbe-research-public/tree/main/tools/rheed):

- `zone_axis_finder.py`: generates the earlier zone-axis finder.
- `double_mount_setpoints.py`: calculates example rotation/deflection tables under its assumed geometry and calibration.

These tools are retained for reference; the geometry visualizer is the primary public demonstration. None substitutes for instrument calibration or operating procedures.

## XRD Utility

Status: `Stable utility`

Path: [`tools/xrd/plot_bruker_dat.py`](../../tools/xrd/plot_bruker_dat.py)

Purpose: plot Bruker-style XRD `.dat` files on log and optional linear intensity scales.

Public demo target: [RSM/XRD demo](../demos/rsm/index.md)

Public notebooks:

- [`rsm_reciprocal_coordinate_workflow.ipynb`](../notebooks/rsm_reciprocal_coordinate_workflow.ipynb)
- [`rios_growth_rate_conversion.ipynb`](../notebooks/rios_growth_rate_conversion.ipynb)

## Literature Search

Status: `Active workflow tool`

Path: [`tools/literature/`](../../tools/literature/)

Purpose: build transparent Crossref/OpenAlex query logs and markdown summaries for literature triage.

Privacy boundary: PDF download/import tooling is intentionally excluded from the public first pass.

## Research Agents

Status: `Research workflow specifications`

Path: [`agents/`](../../agents/)

Public agents include literature search, plotting/analysis, database maintenance, and public-safe summaries of growth-day and characterization assistants.
