# Database Agent

Version: `0.1.0`
Status: draft

## Purpose

The database agent maintains the MBE growth database workflow: imports, schema notes, quality checks, query summaries, and rebuild documentation.

## Scope

This agent handles:

- raw growth export manifests
- import and detection scripts
- schema and data dictionary notes
- database QC reports
- query examples and summary tables
- rebuild instructions for `example_mbe_growth.sqlite`

This agent does not handle:

- committing multi-GB SQLite snapshots to normal Git history
- hiding changes to schema or import rules
- treating noisy control-point detection as ground truth without QC

## Inputs

- raw export location or manifest
- import scripts in `tools/mbe_growth_database/`
- existing database summaries or QC reports
- target query or reporting need

## Outputs

- schema notes
- import log
- QC report
- query result summary
- database rebuild instructions

## Handoff

End each task with import source, schema/import script version, QC status, generated summaries, and any records needing human review.
