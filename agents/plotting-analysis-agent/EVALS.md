# Plotting Analysis Agent Evals

Version: `0.1.0`
Status: draft

## Smoke Tests

- Task: Replot an existing XRD figure with a minor formatting change.
  Expected behavior: reuses the existing script or local style, records changed outputs, and preserves raw data.

- Task: Generate a TEM-derived summary figure.
  Expected behavior: records input image/data files, assumptions, and output paths.

## Failure Modes

- Loses provenance.
  Check: every final figure has a script and input file list.

- Hides analysis choices.
  Check: smoothing, fitting, scaling, and normalization are stated.

## Release Review

- Figures are reproducible from tracked scripts and documented inputs.
- Draft and final outputs are clearly distinguished.
- Interpretation notes are suitable for dissertation reuse.
