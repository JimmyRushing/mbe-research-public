#!/usr/bin/env python3
"""Generate an HTML/SVG visualization for one detected MBE growth run."""

from __future__ import annotations

import argparse
import datetime as dt
import html
import math
import sqlite3
from pathlib import Path


GROUP_III = {
    "Ga": "ga_shutter",
    "In": "in_shutter",
    "Al": "al_shutter",
}

GROUP_V = {
    "As": "as_shutter",
    "Sb": "sb_shutter",
}

MATERIAL_LABELS = {
    (("Ga",), ("As",)): "GaAs",
    (("In",), ("As",)): "InAs",
    (("Al",), ("As",)): "AlAs",
    (("Ga",), ("Sb",)): "GaSb",
    (("In",), ("Sb",)): "InSb",
    (("Ga", "In"), ("As",)): "InGaAs",
    (("Ga", "In"), ("Sb",)): "InGaSb",
    (("Ga", "In"), ("As", "Sb")): "InGaAsSb",
}

SEGMENT_COLORS = {
    "growth": "#2b8a7e",
    "bath": "#6c6a00",
    "idle": "#d9dee7",
}

SOURCE_COLORS = {
    "Ga": "#2f6fed",
    "In": "#b83280",
    "Al": "#7c4dff",
    "As": "#c36b00",
    "Sb": "#00875a",
}


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def fmt_time(seconds: int) -> str:
    minutes, sec = divmod(seconds, 60)
    hours, minute = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minute:02d}m"
    if minute:
        return f"{minute}m {sec:02d}s"
    return f"{sec}s"


def fmt_clock(value: dt.datetime) -> str:
    return value.strftime("%H:%M:%S")


def fmt_pressure(value: float | None) -> str:
    if value is None:
        return ""
    return f"{value:.3e}"


def open_sources(row: sqlite3.Row, sources: dict[str, str]) -> list[str]:
    return [name for name, column in sources.items() if row[column] == 0]


def material_label(group_iii: list[str], group_v: list[str]) -> str:
    key = (tuple(group_iii), tuple(group_v))
    if key in MATERIAL_LABELS:
        return MATERIAL_LABELS[key]
    if group_v:
        return f"{'+'.join(group_iii)} under {'+'.join(group_v)}"
    return f"{'+'.join(group_iii)} growth"


def bath_label(group_v: list[str]) -> str:
    if not group_v:
        return "idle / ramp / cooldown"
    return f"{'+'.join(group_v)} bath"


def classify_segment(group_iii: list[str], group_v: list[str]) -> tuple[str, str]:
    if group_iii:
        return "growth", material_label(group_iii, group_v)
    if group_v:
        return "bath", bath_label(group_v)
    return "idle", "idle / ramp / cooldown"


def load_run(db: sqlite3.Connection, run_id: str) -> tuple[sqlite3.Row, sqlite3.Row, list[sqlite3.Row]]:
    db.row_factory = sqlite3.Row
    detected = db.execute(
        """
        select *
        from detected_growth_runs
        where detected_run_id = ?
        """,
        (run_id,),
    ).fetchone()
    if not detected:
        raise SystemExit(f"No detected growth run found for {run_id!r}.")

    export = db.execute(
        """
        select *
        from raw_exports
        where export_id = ?
        """,
        (detected["parent_export_id"],),
    ).fetchone()
    if not export:
        raise SystemExit(f"Parent export for {run_id!r} is missing raw export metadata.")

    rows = db.execute(
        """
        select
          time_seconds,
          gm1_subs_center_measured as substrate_temp,
          growth_module_1_iongauge1_measured as chamber_pressure,
          pm1_vacuum_reading as pm1_vacuum,
          gm1_ga1_tip_shutterstatus as ga_shutter,
          gm1_in1_tip_shutterstatus as in_shutter,
          gm1_al1_tip_shutterstatus as al_shutter,
          gm1_as1_valve_shutterstatus as as_shutter,
          gen10_200v_sb_valve_shutterstatus as sb_shutter
        from growth_measurements
        where run_id = ?
          and time_seconds between ? and ?
        order by time_seconds
        """,
        (detected["parent_export_id"], detected["start_second"], detected["end_second"]),
    ).fetchall()
    if not rows:
        raise SystemExit(f"No measurement rows found for {run_id!r}.")

    return detected, export, rows


def build_segments(rows: list[sqlite3.Row], window_start: dt.datetime) -> list[dict[str, object]]:
    segments: list[dict[str, object]] = []
    current: dict[str, object] | None = None

    for row in rows:
        group_iii = open_sources(row, GROUP_III)
        group_v = open_sources(row, GROUP_V)
        segment_type, label = classify_segment(group_iii, group_v)
        state = (tuple(group_iii), tuple(group_v), segment_type, label)

        if (
            current is None
            or current["state"] != state
            or row["time_seconds"] - current["end_second"] > 1.1
        ):
            if current is not None:
                segments.append(finalize_segment(current, window_start))
            current = {
                "state": state,
                "type": segment_type,
                "label": label,
                "group_iii": group_iii,
                "group_v": group_v,
                "start_second": row["time_seconds"],
                "end_second": row["time_seconds"],
                "substrate_values": [row["substrate_temp"]],
                "pressure_values": [row["chamber_pressure"]],
            }
        else:
            current["end_second"] = row["time_seconds"]
            current["substrate_values"].append(row["substrate_temp"])
            current["pressure_values"].append(row["chamber_pressure"])

    if current is not None:
        segments.append(finalize_segment(current, window_start))
    return segments


def average(values: list[float | None]) -> float | None:
    numeric = [value for value in values if value is not None]
    if not numeric:
        return None
    return sum(numeric) / len(numeric)


def finalize_segment(segment: dict[str, object], window_start: dt.datetime) -> dict[str, object]:
    start_second = int(segment["start_second"])
    end_second = int(segment["end_second"])
    substrate_values = segment["substrate_values"]
    pressure_values = segment["pressure_values"]
    return {
        **segment,
        "duration_seconds": max(1, int(round(end_second - start_second))),
        "start_time": window_start + dt.timedelta(seconds=start_second),
        "end_time": window_start + dt.timedelta(seconds=end_second),
        "avg_substrate_temp": average(substrate_values),
        "min_substrate_temp": min(value for value in substrate_values if value is not None),
        "max_substrate_temp": max(value for value in substrate_values if value is not None),
        "avg_chamber_pressure": average(pressure_values),
    }


def downsample(rows: list[sqlite3.Row], max_points: int = 900) -> list[sqlite3.Row]:
    if len(rows) <= max_points:
        return rows
    stride = math.ceil(len(rows) / max_points)
    return rows[::stride]


def line_path(points: list[tuple[float, float]]) -> str:
    if not points:
        return ""
    head, *tail = points
    parts = [f"M {head[0]:.2f} {head[1]:.2f}"]
    parts.extend(f"L {x:.2f} {y:.2f}" for x, y in tail)
    return " ".join(parts)


def scale(value: float, domain_min: float, domain_max: float, range_min: float, range_max: float) -> float:
    if domain_max == domain_min:
        return (range_min + range_max) / 2
    fraction = (value - domain_min) / (domain_max - domain_min)
    return range_min + fraction * (range_max - range_min)


def render_timeline_svg(
    rows: list[sqlite3.Row],
    segments: list[dict[str, object]],
    start_second: int,
    end_second: int,
) -> str:
    width = 1160
    left = 96
    right = 34
    top = 34
    band_h = 42
    lane_h = 24
    chart_top = top + band_h + 150
    chart_h = 150
    height = chart_top + chart_h + 54
    plot_w = width - left - right
    span = max(1, end_second - start_second)

    def x_for(second: int) -> float:
        return left + ((second - start_second) / span) * plot_w

    svg: list[str] = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Growth run timeline">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{left}" y="22" class="svg-title">Process timeline</text>',
    ]

    for segment in segments:
        x = x_for(int(segment["start_second"]))
        x2 = x_for(int(segment["end_second"]) + 1)
        color = SEGMENT_COLORS[str(segment["type"])]
        svg.append(
            f'<rect x="{x:.2f}" y="{top}" width="{max(1, x2 - x):.2f}" height="{band_h}" '
            f'fill="{color}" opacity="0.86"/>'
        )
        if x2 - x > 54:
            svg.append(
                f'<text x="{x + 4:.2f}" y="{top + 26}" class="band-label">{esc(segment["label"])}</text>'
            )
    svg.append(f'<text x="20" y="{top + 26}" class="axis-label">Phase</text>')

    lanes = [*GROUP_III.keys(), *GROUP_V.keys()]
    lane_start = top + band_h + 34
    for index, source in enumerate(lanes):
        y = lane_start + index * lane_h
        svg.append(f'<line x1="{left}" y1="{y}" x2="{width - right}" y2="{y}" class="grid"/>')
        svg.append(f'<text x="54" y="{y + 5}" class="axis-label">{source}</text>')
        for segment in segments:
            open_names = segment["group_iii"] if source in GROUP_III else segment["group_v"]
            if source not in open_names:
                continue
            x = x_for(int(segment["start_second"]))
            x2 = x_for(int(segment["end_second"]) + 1)
            svg.append(
                f'<rect x="{x:.2f}" y="{y - 8}" width="{max(1, x2 - x):.2f}" height="13" '
                f'rx="2" fill="{SOURCE_COLORS[source]}"/>'
            )

    temps = [row["substrate_temp"] for row in rows if row["substrate_temp"] is not None]
    pressures = [row["chamber_pressure"] for row in rows if row["chamber_pressure"] and row["chamber_pressure"] > 0]
    temp_min = min(temps)
    temp_max = max(temps)
    log_pressure_min = math.log10(min(pressures)) if pressures else -10
    log_pressure_max = math.log10(max(pressures)) if pressures else -8
    sampled = downsample(rows)

    svg.append(f'<rect x="{left}" y="{chart_top}" width="{plot_w}" height="{chart_h}" fill="#f8fafc" stroke="#d8dee8"/>')
    svg.append(f'<text x="20" y="{chart_top + 24}" class="axis-label">Sub temp</text>')
    svg.append(f'<text x="{width - 145}" y="{chart_top + 24}" class="axis-label">Pressure log</text>')
    temp_points = [
        (
            x_for(row["time_seconds"]),
            scale(row["substrate_temp"], temp_min, temp_max, chart_top + chart_h - 12, chart_top + 12),
        )
        for row in sampled
        if row["substrate_temp"] is not None
    ]
    pressure_points = [
        (
            x_for(row["time_seconds"]),
            scale(math.log10(row["chamber_pressure"]), log_pressure_min, log_pressure_max, chart_top + chart_h - 12, chart_top + 12),
        )
        for row in sampled
        if row["chamber_pressure"] and row["chamber_pressure"] > 0
    ]
    svg.append(f'<path d="{line_path(temp_points)}" fill="none" stroke="#1f5fbf" stroke-width="2.2"/>')
    svg.append(f'<path d="{line_path(pressure_points)}" fill="none" stroke="#b42318" stroke-width="1.8" opacity="0.8"/>')

    for fraction in [0, 0.25, 0.5, 0.75, 1]:
        second = int(start_second + fraction * span)
        x = x_for(second)
        svg.append(f'<line x1="{x:.2f}" y1="{top + band_h}" x2="{x:.2f}" y2="{chart_top + chart_h}" class="grid"/>')
        svg.append(f'<text x="{x - 28:.2f}" y="{height - 18}" class="tick-label">{fmt_time(second - start_second)}</text>')

    svg.append(
        f'<text x="{left}" y="{chart_top + chart_h + 20}" class="legend">'
        f'<tspan fill="#1f5fbf">Substrate temp</tspan>  '
        f'<tspan fill="#b42318">Growth chamber pressure</tspan></text>'
    )
    svg.append("</svg>")
    return "\n".join(svg)


def render_stack_svg(layers: list[dict[str, object]]) -> str:
    width = 420
    height = 620
    top = 34
    bottom = 38
    left = 54
    stack_w = 160
    stack_h = height - top - bottom
    min_layer_h = 18
    svg = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-label="Time-scaled material stack">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#ffffff"/>',
        f'<text x="{left}" y="22" class="svg-title">Resulting stack</text>',
        f'<text x="{left + stack_w + 28}" y="22" class="legend">time-scaled, not thickness</text>',
    ]
    if not layers:
        svg.append(f'<rect x="{left}" y="{top}" width="{stack_w}" height="{stack_h}" fill="#f4f6f8" stroke="#ccd3de"/>')
        svg.append(f'<text x="{left + 20}" y="{top + 38}" class="axis-label">No group III growth intervals found</text>')
        svg.append("</svg>")
        return "\n".join(svg)

    total_duration = sum(int(layer["duration_seconds"]) for layer in layers) or 1
    raw_heights = [
        max(min_layer_h, stack_h * int(layer["duration_seconds"]) / total_duration)
        for layer in layers
    ]
    height_scale = stack_h / sum(raw_heights)
    layer_heights = [height * height_scale for height in raw_heights]

    y = top + stack_h
    for index, (layer, layer_h) in enumerate(zip(layers, layer_heights), start=1):
        y -= layer_h
        color = SEGMENT_COLORS["growth"] if index % 2 else "#3f9f8f"
        label_y = y + min(layer_h - 4, 18)
        svg.append(
            f'<rect x="{left}" y="{y:.2f}" width="{stack_w}" height="{layer_h:.2f}" '
            f'fill="{color}" stroke="#ffffff" stroke-width="1.5"/>'
        )
        if layer_h > 13:
            svg.append(f'<text x="{left + 8}" y="{label_y:.2f}" class="stack-label">{esc(layer["label"])}</text>')
        detail = (
            f'{index}. {layer["label"]}: {fmt_time(int(layer["duration_seconds"]))}, '
            f'avg {float(layer["avg_substrate_temp"]):.1f} C'
        )
        svg.append(
            f'<line x1="{left + stack_w}" y1="{y + layer_h / 2:.2f}" x2="{left + stack_w + 20}" '
            f'y2="{y + layer_h / 2:.2f}" stroke="#94a3b8"/>'
        )
        svg.append(
            f'<text x="{left + stack_w + 28}" y="{y + layer_h / 2 + 4:.2f}" class="layer-detail">{esc(detail)}</text>'
        )
    svg.append("</svg>")
    return "\n".join(svg)


def render_table_rows(
    segments: list[dict[str, object]],
    limit: int | None = None,
    has_real_time: bool = True,
    run_start_second: int = 0,
) -> str:
    rows = segments if limit is None else segments[:limit]
    html_rows = []
    for segment in rows:
        start_label = (
            fmt_clock(segment["start_time"])
            if has_real_time
            else fmt_time(int(segment["start_second"]) - run_start_second)
        )
        end_label = (
            fmt_clock(segment["end_time"])
            if has_real_time
            else fmt_time(int(segment["end_second"]) - run_start_second)
        )
        html_rows.append(
            "<tr>"
            f"<td>{esc(start_label)}</td>"
            f"<td>{esc(end_label)}</td>"
            f"<td>{esc(fmt_time(int(segment['duration_seconds'])))}</td>"
            f"<td>{esc(segment['type'])}</td>"
            f"<td>{esc(segment['label'])}</td>"
            f"<td>{float(segment['avg_substrate_temp']):.1f}</td>"
            f"<td>{esc(fmt_pressure(segment['avg_chamber_pressure']))}</td>"
            "</tr>"
        )
    return "\n".join(html_rows)


def render_html(
    run_id: str,
    detected: sqlite3.Row,
    export: sqlite3.Row,
    rows: list[sqlite3.Row],
    segments: list[dict[str, object]],
) -> str:
    has_real_time = bool(export["window_start_at"])
    window_start = dt.datetime.fromisoformat(export["window_start_at"]) if has_real_time else dt.datetime(2000, 1, 1)
    start_time = window_start + dt.timedelta(seconds=detected["start_second"])
    end_time = window_start + dt.timedelta(seconds=detected["end_second"])
    layers = [segment for segment in segments if segment["type"] == "growth"]
    baths = [segment for segment in segments if segment["type"] == "bath"]
    total_duration = int(detected["end_second"] - detected["start_second"] + 1)
    stack_summary = ", ".join(
        f"{layer['label']} ({fmt_time(int(layer['duration_seconds']))})"
        for layer in layers
    ) or "No group III growth intervals found"

    timeline_svg = render_timeline_svg(rows, segments, int(detected["start_second"]), int(detected["end_second"]))
    stack_svg = render_stack_svg(layers)
    run_window_label = (
        f"{fmt_clock(start_time)} - {fmt_clock(end_time)}"
        if has_real_time
        else f"{fmt_time(int(detected['start_second']))} - {fmt_time(int(detected['end_second']))} elapsed"
    )
    time_note = (
        "Times are actual clock times from filename metadata."
        if has_real_time
        else "No filename date/time was available, so times are elapsed/export-relative."
    )

    css = """
    :root {
      color-scheme: light;
      --text: #172033;
      --muted: #5c667a;
      --line: #d8dee8;
      --panel: #f7f9fc;
      --growth: #2b8a7e;
      --bath: #6c6a00;
      --idle: #d9dee7;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: #ffffff;
      line-height: 1.35;
    }
    main { max-width: 1280px; margin: 0 auto; padding: 28px 28px 44px; }
    header { border-bottom: 1px solid var(--line); padding-bottom: 18px; margin-bottom: 22px; }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }
    h2 { margin: 0 0 12px; font-size: 18px; letter-spacing: 0; }
    p { margin: 0; color: var(--muted); }
    .stats {
      display: grid;
      grid-template-columns: repeat(4, minmax(160px, 1fr));
      gap: 10px;
      margin-top: 18px;
    }
    .stat { border: 1px solid var(--line); border-radius: 8px; padding: 10px 12px; background: var(--panel); }
    .stat b { display: block; font-size: 12px; color: var(--muted); font-weight: 600; margin-bottom: 4px; }
    .stat span { font-size: 17px; font-weight: 650; }
    .layout {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 430px;
      gap: 18px;
      align-items: start;
    }
    section { border: 1px solid var(--line); border-radius: 8px; padding: 16px; background: #fff; margin-bottom: 18px; }
    .timeline-wrap { overflow-x: auto; }
    svg { width: 100%; height: auto; display: block; }
    .svg-title { font-size: 17px; font-weight: 700; fill: var(--text); }
    .axis-label, .tick-label, .legend { font-size: 12px; fill: var(--muted); }
    .band-label { font-size: 12px; fill: #fff; font-weight: 700; }
    .stack-label { font-size: 12px; fill: #fff; font-weight: 700; }
    .layer-detail { font-size: 11px; fill: var(--text); }
    .grid { stroke: #d8dee8; stroke-width: 1; }
    table { width: 100%; border-collapse: collapse; font-size: 13px; }
    th, td { text-align: left; border-bottom: 1px solid var(--line); padding: 7px 8px; vertical-align: top; }
    th { color: var(--muted); font-size: 12px; font-weight: 700; background: #f8fafc; position: sticky; top: 0; }
    .note { color: var(--muted); font-size: 13px; margin-top: 8px; }
    @media (max-width: 980px) {
      main { padding: 20px 14px 34px; }
      .layout { grid-template-columns: 1fr; }
      .stats { grid-template-columns: repeat(2, minmax(140px, 1fr)); }
    }
    """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{esc(run_id)} Growth Visualization</title>
  <style>{css}</style>
</head>
<body>
  <main>
    <header>
      <h1>{esc(run_id)} Growth Visualization</h1>
      <p><a href="/visualizations/index.html">All visualizations</a></p>
      <p>{esc(time_note)} Stack height is time-scaled from shutter-open duration, not calibrated physical thickness.</p>
      <div class="stats">
        <div class="stat"><b>Run window</b><span>{esc(run_window_label)}</span></div>
        <div class="stat"><b>Total duration</b><span>{esc(fmt_time(total_duration))}</span></div>
        <div class="stat"><b>Source shutters</b><span>{esc(detected["source_shutters_opened"] or "none")}</span></div>
        <div class="stat"><b>Group V shutters</b><span>{esc(detected["group_v_shutters_opened"] or "none")}</span></div>
      </div>
    </header>

    <section>
      <div class="timeline-wrap">{timeline_svg}</div>
    </section>

    <div class="layout">
      <section>
        <h2>Process Segments</h2>
        <table>
          <thead>
            <tr>
              <th>Start</th><th>End</th><th>Duration</th><th>Type</th><th>Label</th><th>Avg Sub Temp (C)</th><th>Avg Chamber Pressure</th>
            </tr>
          </thead>
          <tbody>{render_table_rows(segments, has_real_time=has_real_time, run_start_second=int(detected["start_second"]))}</tbody>
        </table>
      </section>

      <section>
        <h2>Resulting Stack</h2>
        {stack_svg}
        <p class="note">{esc(stack_summary)}</p>
      </section>
    </div>

    <section>
      <h2>Group V Bath Intervals</h2>
      <table>
        <thead>
          <tr>
            <th>Start</th><th>End</th><th>Duration</th><th>Type</th><th>Label</th><th>Avg Sub Temp (C)</th><th>Avg Chamber Pressure</th>
          </tr>
        </thead>
        <tbody>{render_table_rows(baths, has_real_time=has_real_time, run_start_second=int(detected["start_second"]))}</tbody>
      </table>
    </section>
  </main>
</body>
</html>
"""


def render_visualization_index_html(rows: list[sqlite3.Row]) -> str:
    cards = []
    for row in rows:
        cards.append(
            '<a class="card" href="{url}">'
            '<span class="run">{run}</span>'
            '<span class="time">{start} to {end}</span>'
            '<span class="stack">{stack}</span>'
            '</a>'.format(
                url=esc(row["visualization_url"]),
                run=esc(row["run_id"]),
                start=esc(row["start_time"].replace("T", " ")),
                end=esc(row["end_time"].replace("T", " ")),
                stack=esc(row["detected_stack_summary"]),
            )
        )

    css = """
    :root {
      color-scheme: light;
      --text: #172033;
      --muted: #5c667a;
      --line: #d8dee8;
      --panel: #f7f9fc;
      --accent: #2b8a7e;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: var(--text);
      background: #fff;
    }
    main { max-width: 960px; margin: 0 auto; padding: 30px 24px 44px; }
    h1 { margin: 0 0 8px; font-size: 28px; letter-spacing: 0; }
    p { margin: 0 0 22px; color: var(--muted); }
    .grid { display: grid; gap: 12px; }
    .card {
      display: grid;
      grid-template-columns: 110px minmax(190px, 1fr) minmax(260px, 2fr);
      gap: 14px;
      align-items: center;
      padding: 14px 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      color: inherit;
      text-decoration: none;
    }
    .card:hover { border-color: var(--accent); background: #f2fbf8; }
    .run { font-size: 20px; font-weight: 750; color: var(--accent); }
    .time { color: var(--muted); font-size: 13px; }
    .stack { font-size: 14px; }
    @media (max-width: 760px) {
      main { padding: 22px 14px 34px; }
      .card { grid-template-columns: 1fr; gap: 5px; }
    }
    """

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Growth Visualizations</title>
  <style>{css}</style>
</head>
<body>
  <main>
    <h1>Growth Visualizations</h1>
    <p>Generated pages for detected MBE growth runs. Stack height is time-scaled, not calibrated thickness.</p>
    <div class="grid">
      {''.join(cards)}
    </div>
  </main>
</body>
</html>
"""


def write_visualization_index_page(db: sqlite3.Connection, output_dir: Path) -> None:
    db.row_factory = sqlite3.Row
    rows = db.execute(
        """
        select run_id, visualization_url, start_time, end_time, detected_stack_summary
        from growth_visualization_index
        order by run_id
        """
    ).fetchall()
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(render_visualization_index_html(rows), encoding="utf-8")


def update_index(
    db: sqlite3.Connection,
    run_id: str,
    output: Path,
    detected: sqlite3.Row,
    export: sqlite3.Row,
    layers: list[dict[str, object]],
) -> None:
    has_real_time = bool(export["window_start_at"])
    window_start = dt.datetime.fromisoformat(export["window_start_at"]) if has_real_time else dt.datetime(2000, 1, 1)
    start_time = window_start + dt.timedelta(seconds=detected["start_second"])
    end_time = window_start + dt.timedelta(seconds=detected["end_second"])
    stack_summary = ", ".join(
        f"{layer['label']} ({fmt_time(int(layer['duration_seconds']))})"
        for layer in layers
    ) or "No group III growth intervals found"
    generated_at = dt.datetime.now(dt.timezone.utc).isoformat()
    visualization_url = f"/visualizations/{output.name}"
    visualization_full_url = f"http://127.0.0.1:8001{visualization_url}"

    db.execute(
        """
        create table if not exists growth_visualization_index (
            run_id text primary key,
            visualization_file text not null,
            visualization_url text not null,
            visualization_full_url text,
            start_time text not null,
            end_time text not null,
            detected_stack_summary text not null,
            generated_at text not null
        )
        """
    )
    existing_columns = {
        row[1] for row in db.execute("pragma table_info(growth_visualization_index)").fetchall()
    }
    if "visualization_full_url" not in existing_columns:
        db.execute("alter table growth_visualization_index add column visualization_full_url text")

    db.execute("drop view if exists growth_visualization_index_readable")
    db.execute(
        """
        create view growth_visualization_index_readable as
        select
            run_id as "Run",
            visualization_url as "Visualization URL",
            visualization_full_url as "Visualization Full URL",
            visualization_file as "Visualization File",
            start_time as "Start Time",
            end_time as "End Time",
            detected_stack_summary as "Detected Stack Summary",
            generated_at as "Generated At"
        from growth_visualization_index
        """
    )
    db.execute(
        """
        insert into growth_visualization_index (
            run_id, visualization_file, visualization_url, visualization_full_url, start_time, end_time,
            detected_stack_summary, generated_at
        )
        values (?, ?, ?, ?, ?, ?, ?, ?)
        on conflict(run_id) do update set
            visualization_file = excluded.visualization_file,
            visualization_url = excluded.visualization_url,
            visualization_full_url = excluded.visualization_full_url,
            start_time = excluded.start_time,
            end_time = excluded.end_time,
            detected_stack_summary = excluded.detected_stack_summary,
            generated_at = excluded.generated_at
        """,
        (
            run_id,
            str(output.resolve()),
            visualization_url,
            visualization_full_url,
            start_time.isoformat(timespec="seconds") if has_real_time else f"{fmt_time(int(detected['start_second']))} elapsed",
            end_time.isoformat(timespec="seconds") if has_real_time else f"{fmt_time(int(detected['end_second']))} elapsed",
            stack_summary,
            generated_at,
        ),
    )
    write_visualization_index_page(db, output.parent)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_id", help="Detected run id, for example PS140")
    parser.add_argument("--db", default="data/example_mbe_growth.sqlite", help="SQLite database path")
    parser.add_argument("--output", type=Path, help="HTML output path")
    args = parser.parse_args()

    output = args.output or Path("outputs/growth_visualizations") / f"{args.run_id}.html"
    output.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(args.db) as db:
        db.row_factory = sqlite3.Row
        detected, export, rows = load_run(db, args.run_id)
        window_start = dt.datetime.fromisoformat(export["window_start_at"]) if export["window_start_at"] else dt.datetime(2000, 1, 1)
        segments = build_segments(rows, window_start)
        html_text = render_html(args.run_id, detected, export, rows, segments)
        output.write_text(html_text, encoding="utf-8")
        layers = [segment for segment in segments if segment["type"] == "growth"]
        update_index(db, args.run_id, output, detected, export, layers)

    print(f"Generated {output}")


if __name__ == "__main__":
    main()
