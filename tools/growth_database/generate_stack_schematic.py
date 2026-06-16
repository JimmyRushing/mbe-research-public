#!/usr/bin/env python3
"""Generate a large block-style stack schematic for one detected growth run."""

from __future__ import annotations

import argparse
import datetime as dt
import sqlite3
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import generate_growth_timeline as growth_viz


MATERIAL_COLORS = {
    "GaSb": "#4f79c6",
    "GaAs": "#4f79c6",
    "InAs": "#9fd28c",
    "InGaAs": "#9fd28c",
    "InGaSb": "#8fcf9f",
    "InGaAsSb": "#9fd28c",
    "InSb": "#9fd28c",
    "AlAs": "#ffc20a",
    "AlSb": "#ffc20a",
    "Al under Sb": "#ffc20a",
    "Sb bath": "#d80000",
    "As bath": "#d80000",
    "As+Sb bath": "#d80000",
    "substrate": "#5c5c5c",
    "default": "#7c8aa5",
}


def color_for(label: str, segment_type: str) -> str:
    if segment_type == "bath":
        return MATERIAL_COLORS.get(label, "#d80000")
    if label in MATERIAL_COLORS:
        return MATERIAL_COLORS[label]
    if "Al" in label:
        return MATERIAL_COLORS["AlSb"]
    if "In" in label:
        return MATERIAL_COLORS["InGaSb"]
    if "Ga" in label:
        return MATERIAL_COLORS["GaSb"]
    return MATERIAL_COLORS["default"]


def text_color(background: str) -> str:
    dark = {"#4f79c6", "#d80000", "#5c5c5c", "#7c8aa5"}
    return "#ffffff" if background in dark else "#ffffff"


def relevant_stack_segments(segments: list[dict[str, object]], include_baths: bool) -> list[dict[str, object]]:
    selected = []
    growth_started = False
    for segment in segments:
        if segment["type"] == "growth":
            selected.append(segment)
            growth_started = True
        elif include_baths and growth_started and segment["type"] == "bath":
            selected.append(segment)
    return selected


def display_label(segment: dict[str, object], show_duration: bool) -> str:
    base = str(segment["label"])
    if show_duration:
        return f"{growth_viz.fmt_time(int(segment['duration_seconds']))} {base}"
    return base


def block_heights(segments: list[dict[str, object]], stack_height: int) -> list[float]:
    if not segments:
        return []
    min_h = 34
    durations = [int(segment["duration_seconds"]) for segment in segments]
    total = sum(durations) or 1
    raw = [max(min_h, stack_height * duration / total) for duration in durations]
    scale = stack_height / sum(raw)
    return [height * scale for height in raw]


def render_stack_svg(
    run_id: str,
    segments: list[dict[str, object]],
    show_duration: bool,
    substrate_label: str,
) -> str:
    width = 760
    substrate_h = 120
    stack_h = 520
    margin = 28
    height = margin * 2 + stack_h + substrate_h
    x = 36
    w = width - x * 2
    y = margin
    heights = block_heights(segments, stack_h)

    svg = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="{growth_viz.esc(run_id)} stack schematic">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<rect x="{x}" y="{y}" width="{w}" height="{stack_h + substrate_h}" fill="none" stroke="#1f4e9d" stroke-width="3"/>',
    ]

    current_y = y
    for segment, block_h in zip(reversed(segments), reversed(heights)):
        label = display_label(segment, show_duration)
        fill = color_for(str(segment["label"]), str(segment["type"]))
        font_size = 30 if block_h >= 58 else 22
        svg.append(
            f'<rect x="{x}" y="{current_y:.2f}" width="{w}" height="{block_h:.2f}" '
            f'fill="{fill}" stroke="#1f4e9d" stroke-width="2"/>'
        )
        svg.append(
            f'<text x="{x + w / 2}" y="{current_y + block_h / 2 + font_size * 0.35:.2f}" '
            f'text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
            f'font-size="{font_size}" font-weight="700" fill="{text_color(fill)}">{growth_viz.esc(label)}</text>'
        )
        current_y += block_h

    substrate_y = y + stack_h
    svg.append(
        f'<rect x="{x}" y="{substrate_y}" width="{w}" height="{substrate_h}" '
        f'fill="{MATERIAL_COLORS["substrate"]}" stroke="#1f4e9d" stroke-width="2"/>'
    )
    svg.append(
        f'<text x="{x + w / 2}" y="{substrate_y + substrate_h / 2 + 12}" '
        f'text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
        f'font-size="34" font-weight="700" fill="#ffffff">{growth_viz.esc(substrate_label)}</text>'
    )
    svg.append("</svg>")
    return "\n".join(svg)


def render_html(
    run_id: str,
    detected: sqlite3.Row,
    export: sqlite3.Row,
    segments: list[dict[str, object]],
    stack_segments: list[dict[str, object]],
    show_duration: bool,
    substrate_label: str,
) -> str:
    has_real_time = bool(export["window_start_at"])
    window_start = dt.datetime.fromisoformat(export["window_start_at"]) if has_real_time else dt.datetime(2000, 1, 1)
    start_time = window_start + dt.timedelta(seconds=detected["start_second"])
    end_time = window_start + dt.timedelta(seconds=detected["end_second"])
    run_window = (
        f"{growth_viz.fmt_clock(start_time)}-{growth_viz.fmt_clock(end_time)}"
        if has_real_time
        else f"{growth_viz.fmt_time(int(detected['start_second']))}-{growth_viz.fmt_time(int(detected['end_second']))} elapsed"
    )
    svg = render_stack_svg(run_id, stack_segments, show_duration, substrate_label)
    table_rows = "\n".join(
        "<tr>"
        f"<td>{growth_viz.esc(segment['label'])}</td>"
        f"<td>{growth_viz.esc(segment['type'])}</td>"
        f"<td>{growth_viz.esc(growth_viz.fmt_time(int(segment['duration_seconds'])))}</td>"
        f"<td>{float(segment['avg_substrate_temp']):.1f}</td>"
        "</tr>"
        for segment in stack_segments
    )
    css = """
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #172033;
      background: #fff;
    }
    main { max-width: 1080px; margin: 0 auto; padding: 26px 24px 42px; }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }
    p { color: #5c667a; margin: 0 0 16px; }
    .layout { display: grid; grid-template-columns: minmax(360px, 760px) 1fr; gap: 24px; align-items: start; }
    .panel { border: 1px solid #d8dee8; border-radius: 8px; padding: 16px; background: #fff; }
    svg { width: 100%; height: auto; display: block; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; border-bottom: 1px solid #d8dee8; padding: 7px 8px; }
    th { color: #5c667a; background: #f8fafc; font-size: 12px; }
    .links { display: flex; gap: 14px; flex-wrap: wrap; margin-bottom: 16px; }
    a { color: #1f5fbf; }
    @media (max-width: 900px) {
      main { padding: 20px 14px 34px; }
      .layout { grid-template-columns: 1fr; }
    }
    """
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{growth_viz.esc(run_id)} Stack Schematic</title>
  <style>{css}</style>
</head>
<body>
  <main>
    <h1>{growth_viz.esc(run_id)} Stack Schematic</h1>
    <p class="links">
      <a href="/visualizations/index.html">All visualizations</a>
      <a href="/visualizations/{growth_viz.esc(run_id)}.html">Timeline page</a>
    </p>
    <p>Run window: {growth_viz.esc(run_window)}. Block heights are time-scaled from detected shutter intervals, not calibrated nanometers. Substrate orientation is not inferred from the control-point export.</p>
    <div class="layout">
      <div class="panel">{svg}</div>
      <div class="panel">
        <h2>Blocks</h2>
        <table>
          <thead><tr><th>Label</th><th>Type</th><th>Duration</th><th>Avg Temp (C)</th></tr></thead>
          <tbody>{table_rows}</tbody>
        </table>
      </div>
    </div>
  </main>
</body>
</html>
"""


def generate(
    run_id: str,
    db_path: Path,
    output: Path,
    include_baths: bool,
    show_duration: bool,
    substrate_label: str,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as db:
        db.row_factory = sqlite3.Row
        detected, export, rows = growth_viz.load_run(db, run_id)
        window_start = dt.datetime.fromisoformat(export["window_start_at"]) if export["window_start_at"] else dt.datetime(2000, 1, 1)
        segments = growth_viz.build_segments(rows, window_start)
        stack_segments = relevant_stack_segments(segments, include_baths)
        output.write_text(
            render_html(run_id, detected, export, segments, stack_segments, show_duration, substrate_label),
            encoding="utf-8",
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="Detected run id, for example PS57")
    parser.add_argument("--db", type=Path, default=Path("data/example_mbe_growth.sqlite"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--no-baths", action="store_true", help="Only show growth layers, not bath intervals")
    parser.add_argument("--hide-duration", action="store_true", help="Use material/bath labels only")
    parser.add_argument("--substrate-label", default="GaSb substrate")
    args = parser.parse_args()

    output = args.output or Path("outputs/growth_visualizations") / f"{args.run_id}_stack.html"
    generate(
        args.run_id,
        args.db,
        output,
        include_baths=not args.no_baths,
        show_duration=not args.hide_duration,
        substrate_label=args.substrate_label,
    )
    print(f"Generated {output}")


if __name__ == "__main__":
    main()
