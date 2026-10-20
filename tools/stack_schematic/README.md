# Layer-stack schematic generator

Draw readable SVG layer stacks from explicit JSON descriptions. This standalone Python 3.11+ utility has no third-party dependencies. The renderer is adapted from James Rushing's layer-stack drawing tool; the examples and narrow provenance writer were prepared for this public release.

[Walk through the synthetic example](../../docs/demos/stack-schematic/index.md).

## Run from the repository root

```sh
python -S tools/stack_schematic/build_stack_schematic.py --config tools/stack_schematic/examples/stacks.json --registry tools/stack_schematic/examples/registry.json --out-dir stack-output
```

Open `stack-output/stack-01.svg` in a browser. Each SVG has a companion `.provenance.json`. Choose a new output directory for every run: the tool refuses to overwrite existing output. If writing fails partway through, a partial output directory may remain; the process exits with an error. Use `--validate-only` without `--out-dir` to check inputs without writing files.

Run the release regressions:

```sh
python -S -m unittest discover -s tools/stack_schematic -p "test_*.py"
```

## Input contract

- `schema_version` is 1; `layer_order` is `top-to-bottom`.
- `example: true` places a visible illustrative-example warning on every page. Keep it true for synthetic inputs.
- `sources` maps reference keys to descriptions. Every layer has a matching `source_ref`. This checks that a reference exists; it does not verify the evidence or display its description.
- `slides` contains titled sections with `mode` (`nominal`, `measured`, or `mixed`) and `samples`. Every known film thickness displays its own basis regardless of the section mode.
- The registry contains only `samples`, each with `key` and unique `public_label`. Sample definitions refer to `sample_key`; no internal-ID fields or aliases are accepted.
- Film layers specify `material`, `thickness`, `basis`, `unit`, and `source_ref`. Thickness must be finite and positive. `thickness: null` requires `basis: unknown`; it is shown as `?`, never as zero.
- Supported units are `nm`, `um`, `µm`, and `ML`. Units are labels: no conversions or material-dependent monolayer calculations occur.
- Optional `uncertainty` must be finite and nonnegative and uses the same unit as thickness. Optional `approximate: true` adds `~`. Neither is allowed on an unknown thickness. This tool does not calculate uncertainty or give it a statistical interpretation.
- A substrate has `role: substrate`, belongs at the bottom, and has no thickness/basis/unit fields. Each stack has 1–8 layers, including its substrate if present. Pages contain at most three stacks.
- The example palette uses generic `Cap`, `Film`, and `Buffer` labels. `material_colors` may add named materials with six-digit hex colors; existing colors cannot be overridden through the config.

Titles are limited to 62 characters, sample labels to 22, and layer labels to 36. Text fit is approximate and font-dependent; visually inspect every generated figure. Geometry is schematic, not proportional to thickness. The utility does not infer growth order, composition, thickness, or experimental truth.

## What the companion record contains

The deterministic JSON contains only its schema version, page number, and SHA-256/byte counts for the output and five input roles: config, registry, style, renderer, and provenance writer. It records no paths, filenames, command-line arguments, Git history, user identity, timestamps, source descriptions, or input contents. Hashes support exact-file comparison; they are not evidence of scientific validity or proof of who ran the tool.

This is not a general publication sanitizer. Titles, material names, labels, and caveats are intentionally drawn into the SVG. Review those and the input JSON before sharing. Only the supplied invented examples are part of this release. No experimental data, recipes, calibration values, or real sample registries are included. SVG is the supported output in this release.
