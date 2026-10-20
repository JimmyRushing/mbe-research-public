# Public Export Manifest

Generated from the private research workspace as a curated public portfolio export.

## 2026-10-20 Stack Tutorial and RHEED Description Update

This incremental release adds a standalone SVG stack generator adapted from James Rushing's layer-stack renderer, a newly written fixed-field fingerprint helper, tests, and generic synthetic inputs. It changes no repository license terms. No collaborator's broader provenance or Office-normalization framework is included.

Allowlisted additions:

- `.gitattributes` (LF line endings scoped to the new stack package and demo)

- `tools/stack_schematic/build_stack_schematic.py`
- `tools/stack_schematic/provenance.py`
- `tools/stack_schematic/stack_style.json`
- `tools/stack_schematic/test_stack_schematic.py`
- `tools/stack_schematic/README.md`
- `tools/stack_schematic/examples/stacks.json`
- `tools/stack_schematic/examples/registry.json`
- `docs/demos/stack-schematic/index.md`
- `docs/demos/stack-schematic/example/stack-01.svg`
- `docs/demos/stack-schematic/example/stack-01.svg.provenance.json`

Navigation and description updates are limited to `README.md`, `index.md`, this manifest, `docs/demos/index.md`, `docs/demos/rheed/index.md`, `docs/portfolio/index.md`, and `docs/portfolio/tools.md`. The existing RHEED HTML and historical scripts are unchanged. The current geometry visualizer is now consistently the primary demo; earlier planning tools are historical references with illustrative calibration assumptions.

The example input, labels, dimensions, and uncertainties are invented. No real registry, dataset, process recipe, calibration file, local path, or private-source metadata is copied into the release. The committed companion record includes only file hashes, byte counts, page number, and schema version. Its renderer and helper fingerprints identify the exact public code used for the preview.

Validation: 10 focused regression tests pass, including standard-library-only execution, reproducibility, create-only output, XML escaping, evidence labels, scientific input rejection, and fixed-field metadata. Gitleaks 8.30.1 reports no secrets in the checkout. The release is subject to independent review of the full allowlist, source, generated artifact, and public-facing descriptions before publication.

## Original Export Record

The following sections describe the earlier portfolio baseline; their first-push checklist is historical, not a claim that it has been rerun for every file in this update.

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
- artifact policy, repository overview pages, and `.gitignore` guardrails

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
