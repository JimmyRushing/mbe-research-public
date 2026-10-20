#!/usr/bin/env python3
"""Layer-stack schematics from structured JSON to SVG, using Python 3.11+.

Adapted from the layer-stack renderer authored by James Rushing.
See README.md beside this file for the public schema and limitations.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import textwrap
from html import escape
from pathlib import Path

from provenance import write_sidecar

STYLE_PATH = Path(__file__).with_name("stack_style.json")
WIDTH, HEIGHT = 1280, 720
TITLE_LIMIT, SAMPLE_LABEL_LIMIT = 62, 22


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def short_text(value, name, limit=80):
    require(isinstance(value, str) and bool(value.strip()), f"{name} must be nonempty text")
    require(len(value) <= limit and not any(ord(c) < 32 for c in value),
            f"{name} must be a single line of at most {limit} characters")
    return value


def fields(obj, allowed, name):
    require(isinstance(obj, dict), f"{name} must be an object")
    require(not (set(obj) - set(allowed.split())),
            f"Unknown {name} field(s): {', '.join(sorted(set(obj) - set(allowed.split())))}")


def number(value, name, positive=False):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and (value > 0 if positive else value >= 0),
            f"{name} must be a finite {'positive' if positive else 'nonnegative'} number")


def layer_text(layer, mode):
    label = layer.get("label", layer["material"])
    if layer.get("role", "film") == "substrate":
        return label
    value = layer["thickness"]
    thickness = "?" if value is None else f"{value:g}"
    if layer.get("approximate"):
        thickness = "~" + thickness
    if layer.get("uncertainty") is not None:
        thickness += f" ± {layer['uncertainty']:g}"
    text = f"{label} {thickness} {layer['unit']}"
    if layer["basis"] != "unknown":
        text += f" ({layer['basis']})"
    return text


def luminance(color):
    rgb = [int(color[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in rgb]
    return sum(a * b for a, b in zip(linear, (.2126, .7152, .0722)))


def contrast_ratio(first, second):
    bright, dark = sorted((luminance(first), luminance(second)), reverse=True)
    return (bright + .05) / (dark + .05)


def foreground(color):
    return max(("#000000", "#FFFFFF"), key=lambda text: contrast_ratio(color, text))


def display_label(record):
    return record["public_label"]


def validate(config, registry, style):
    fields(config, "schema_version example title layer_order sources slides material_colors", "config")
    require(config.get("schema_version") == 1, "schema_version must be 1")
    require(isinstance(config.get("example", False), bool), "example must be boolean")
    require(config.get("layer_order") == "top-to-bottom", "layer_order must be top-to-bottom")
    short_text(config.get("title"), "title", TITLE_LIMIT)
    sources = config.get("sources")
    require(isinstance(sources, dict) and bool(sources), "sources must map references to evidence descriptions")
    for key, value in sources.items():
        short_text(key, "source key", 60)
        short_text(value, "source description", 1000)
    colors = dict(style["materials"])
    overrides = config.get("material_colors", {})
    require(isinstance(overrides, dict), "material_colors must be an object")
    require(not (set(overrides) & set(colors)),
            "material_colors may only add new materials; canonical palette colors cannot be overridden")
    colors.update(overrides)
    for material, color in colors.items():
        short_text(material, "material", 30)
        require(isinstance(color, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", color),
                f"Invalid color for {material}")
    fields(registry, "samples", "registry")
    records = registry.get("samples", [])
    require(isinstance(records, list) and bool(records), "registry.samples must be nonempty")
    lookup, labels = {}, set()
    for record in records:
        fields(record, "key public_label", "registry entry")
        key = short_text(record.get("key"), "registry key", 80)
        label = short_text(record.get("public_label"), "public_label", SAMPLE_LABEL_LIMIT)
        require(key not in lookup, f"Duplicate registry key: {key}")
        require(label not in labels, f"Duplicate public label: {label}")
        labels.add(label)
        lookup[key] = record
    slides = config.get("slides")
    require(isinstance(slides, list) and bool(slides), "slides must be nonempty")
    visible = [config["title"]]
    for slide in slides:
        fields(slide, "title mode samples", "slide")
        mode = slide.get("mode")
        require(mode in ("nominal", "measured", "mixed"), "mode must be nominal, measured, or mixed")
        visible.append(short_text(slide.get("title"), "slide title", TITLE_LIMIT))
        samples = slide.get("samples")
        require(isinstance(samples, list) and bool(samples), "Each slide must have samples")
        seen = set()
        for sample in samples:
            fields(sample, "sample_key layers caveat public_label", "sample")
            key = sample.get("sample_key")
            require(key in lookup, f"Unknown sample_key: {key}")
            require(key not in seen, f"Duplicate sample in slide: {key}")
            require("public_label" not in sample, "Labels must come from the registry")
            seen.add(key)
            record = lookup[key]
            visible.append(short_text(display_label(record), "sample label", SAMPLE_LABEL_LIMIT))
            if sample.get("caveat"):
                visible.append(short_text(sample["caveat"], "caveat", 100))
            layers = sample.get("layers")
            require(isinstance(layers, list) and 1 <= len(layers) <= 8, "Use 1 to 8 layers per stack; split more complex structures explicitly")
            for index, layer in enumerate(layers):
                fields(layer, "material label role source_ref thickness basis unit uncertainty approximate", "layer")
                material = short_text(layer.get("material"), "material", 30)
                role = layer.get("role", "film")
                require(role in ("film", "substrate"), "role must be film or substrate")
                require(role == "substrate" or material in colors,
                        f"No material color for {material}; supply material_colors explicitly")
                if "label" in layer:
                    short_text(layer["label"], "layer label", 36)
                require(layer.get("source_ref") in sources, f"Missing/unknown source_ref for {material}")
                if role == "substrate":
                    require(index == len(layers) - 1, "Substrate must be the bottom layer")
                    require(not set(layer).intersection(("thickness", "basis", "unit", "uncertainty", "approximate")),
                            "Substrate is a schematic strip; omit thickness, basis, unit, uncertainty, and approximate")
                else:
                    require("thickness" in layer, "Use thickness: null for unknown thickness")
                    require(layer.get("unit") in ("nm", "µm", "um", "ML"), "unit must be nm, µm, um, or ML")
                    basis = layer.get("basis")
                    require(basis in ("nominal", "measured", "unknown"), "Every film needs a thickness basis")
                    if layer["thickness"] is None:
                        require(basis == "unknown", "Null thickness must have basis unknown")
                        require(not layer.get("approximate") and layer.get("uncertainty") is None,
                                "Unknown thickness cannot have uncertainty or approximation")
                    else:
                        number(layer["thickness"], "thickness", positive=True)
                        require(basis != "unknown", "Known thickness must be nominal or measured")
                    require(isinstance(layer.get("approximate", False), bool), "approximate must be boolean")
                    if layer.get("uncertainty") is not None:
                        number(layer["uncertainty"], "uncertainty")
                visible.append(layer_text(layer, mode))
    return lookup, colors


def layout(config, registry, style):
    lookup, colors = validate(config, registry, style)
    pages = []
    for section in config["slides"]:
        samples = section["samples"]
        for start in range(0, len(samples), 3):
            batch = samples[start:start + 3]
            shapes = []

            def box(x, y, w, h, fill, text="", size=22, color=None, name=""):
                lines = []
                if text:
                    # Approximate fixed-size text preflight, not font measurement.
                    # Rendered visual QA is mandatory, particularly for wide glyphs.
                    lines = textwrap.wrap(text, max(1, int((w - 20) / (size * .58))),
                                          break_long_words=False, break_on_hyphens=False)
                    require(all(len(line) * size * .58 <= w - 20 for line in lines)
                            and len(lines) * size * 1.25 <= h - 6,
                            f"Label too long for its box: {text}; shorten or split the stack")
                shapes.append(dict(x=x, y=y, w=w, h=h, fill=fill, lines=lines,
                                   size=size, color=color or foreground(fill or "#FFFFFF"), name=name))

            box(0, 0, WIDTH, 12, style["accent"])
            box(48, 34, 1184, 56, None, config["title"], 32, "#172033", "title")
            suffix = f" · {start // 3 + 1}/{math.ceil(len(samples) / 3)}" if len(samples) > 3 else ""
            box(48, 98, 1184, 44, None, section["title"] + suffix, 23, "#596579", "section")
            w, gap = 340, 34
            left = (WIDTH - len(batch) * w - (len(batch) - 1) * gap) / 2
            for i, sample in enumerate(batch):
                x = left + i * (w + gap)
                record = lookup[sample["sample_key"]]
                label = display_label(record)
                box(x, 167, w, 62, None, label, 24, "#172033", f"sample-{i + 1}")
                layers = sample["layers"]
                h = min(68, 336 / len(layers))
                y = 570 - h * len(layers)
                for j, layer in enumerate(layers):
                    fill = style["substrate"] if layer.get("role") == "substrate" else colors[layer["material"]]
                    box(x, y + j * h, w, h - 2, fill, layer_text(layer, section["mode"]),
                        20 if h >= 50 else 17, name=f"stack-{i + 1}-layer-{j + 1}")
                if sample.get("caveat"):
                    box(x, 582, w, 64, None, sample["caveat"], 16, "#596579", f"caveat-{i + 1}")
            footer = "Schematic: not to scale. ? = thickness unknown."
            if config.get("example"):
                footer = "Illustrative example: not experimental data. " + footer
            box(48, 657, 1184, 42, None, footer, 16, "#596579", "footer")
            pages.append(shapes)
    return pages


def svg(shapes):
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {HEIGHT}" role="img" aria-label="Layer-stack schematic">',
             '<rect width="1280" height="720" fill="white"/>']
    for s in shapes:
        if s["fill"]:
            parts.append(f'<rect x="{s["x"]}" y="{s["y"]}" width="{s["w"]}" height="{s["h"]}" fill="{s["fill"]}"/>')
        y = s["y"] + s["h"] / 2 - (len(s["lines"]) - 1) * s["size"] * .625
        for line in s["lines"]:
            parts.append(f'<text x="{s["x"] + s["w"] / 2}" y="{y}" text-anchor="middle" dominant-baseline="central" font-family="Arial,sans-serif" font-size="{s["size"]}" font-weight="600" fill="{s["color"]}">{escape(line)}</text>')
            y += s["size"] * 1.25
    return "\n".join(parts) + "\n</svg>\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path)
    parser.add_argument("--validate-only", action="store_true")
    args = parser.parse_args()
    try:
        config, registry, style = read_json(args.config), read_json(args.registry), read_json(STYLE_PATH)
        pages = layout(config, registry, style)
        if args.validate_only:
            print(f"Valid: {len(pages)} page(s)")
            return
        require(args.out_dir is not None, "--out-dir is required unless --validate-only")
        require(not args.out_dir.exists(), "Output directory exists; choose a new directory")
        args.out_dir.mkdir(parents=True)
        for i, shapes in enumerate(pages, 1):
            output = args.out_dir / f"stack-{i:02d}.svg"
            output.write_text(svg(shapes), encoding="utf-8", newline="\n")
            write_sidecar(output, page_number=i, inputs={
                "config": args.config, "registry": args.registry, "style": STYLE_PATH,
                "renderer": Path(__file__), "provenance": Path(__file__).with_name("provenance.py")})
        print(f"Wrote {len(pages)} page(s) to {args.out_dir}")
    except (ValueError, KeyError, TypeError, OSError) as exc:
        parser.exit(2, f"Stack schematic: {exc}\n")


if __name__ == "__main__":
    main()
