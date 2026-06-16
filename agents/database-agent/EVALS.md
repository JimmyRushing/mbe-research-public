# Database Agent Evals

Version: `0.1.0`
Status: draft

## Smoke Tests

- Task: Explain how to rebuild the growth database from raw exports.
  Expected behavior: cites import scripts, source locations, schema notes, and QC outputs.

- Task: Summarize growth runs for a sample range.
  Expected behavior: records the query or view and flags uncertain/detected fields.

## Failure Modes

- Commits or stages a multi-GB database.
  Check: database snapshots stay ignored unless a documented artifact policy says otherwise.

- Treats detected control points as verified truth.
  Check: output labels detection confidence and review needs.

## Release Review

- Schema and import assumptions are documented.
- Database can be rebuilt from documented sources.
- QC results are visible before dissertation claims use the data.
