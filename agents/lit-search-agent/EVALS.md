# Lit Search Agent Evals

Version: `0.1.0`
Status: draft

## Smoke Tests

- Task: Screen ten papers from a query result.
  Expected behavior: reports query, criteria, selected papers, and rejected papers with reasons.

- Task: Build an evidence table for one dissertation claim.
  Expected behavior: separates strong evidence, weak evidence, and missing evidence.

## Failure Modes

- Fabricates citation metadata.
  Check: each citation has a source path, DOI, or clear metadata source.

- Overstates an abstract.
  Check: marks claims as abstract-only unless full text was inspected.

## Release Review

- Query logging is explicit.
- Output can be used directly in dissertation writing.
- Copyright-sensitive storage boundaries are clear.
