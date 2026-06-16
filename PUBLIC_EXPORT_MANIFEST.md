# Public Export Manifest

Generated from the private research workspace as a curated public candidate.

## Included In This Export

- portfolio landing pages under `docs/portfolio/`
- public-safe AI-compatible synthesis and Sb(111) growth-strategy summaries
- selected public presentation PDFs under `docs/assets/presentations/`
- RHEED planning tools and generated demo artifacts
- Cadtronics/k.p analysis tool scripts, a pure GaSb 111 phase-diagram HTML demo, and a standalone Schmid Fig. 3(a) validation HTML demo
- cleaned public Jupyter notebooks for RSM reciprocal-coordinate plotting and RIOs growth-rate conversion
- growth database import, QC, view, timeline, stack-schematic scripts, a sanitized SQLite/Datasette public demo page, and one de-identified representative process-timeline PNG
- XRD plotting utility
- public-safe literature search tooling
- public-safe agent specifications and summaries
- artifact policy and `.gitignore` guardrails

## Intentionally Excluded

- raw growth notes
- raw instrument exports
- full SQLite database snapshots
- private facility notes or SOP-like material
- collaborator correspondence
- raw private/local notebooks
- large untrimmed presentation decks
- credential, connector, or local API-key files

## Validation Run

- RHEED zone-axis finder self-test passed.
- RHEED double-mount setpoint self-test passed.
- Public Python tools passed syntax compilation.
- Targeted scan found no local machine paths or excluded private artifact names.
- Export contains no `.sqlite`, `.db`, `.pptx`, `.docx`, `.xlsx`, or `.zip` files.
- Export contains no files larger than 10 MB.

## Before First Public Push

- Run `gitleaks` or `trufflehog` on this export directory.
- Review each PDF for collaborator/privacy/copyright comfort.
- Open the GitHub Pages site and click every portfolio/demo link.
- Add additional static Cadtronics HTML demos from sanitized `.dat` inputs.
- Add an RSM/XRD example figure or notebook-derived static page.
- Label beta scripts clearly on first-click pages.
