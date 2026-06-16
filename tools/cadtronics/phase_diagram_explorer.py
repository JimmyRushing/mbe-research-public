#!/usr/bin/env python3
"""
Build a standalone interactive HTML phase diagram for pure-GaSb TQW scans.

The HTML is self-contained: click a point in the phase map to update the E-k
plot for that geometry.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


PATTERNS = [
    re.compile(
        r"111_TQW_(?P<inas>[0-9.]+) (?P<gasb>[0-9.]+) (?P=inas)\.dat$",
        re.IGNORECASE,
    ),
    re.compile(
        r"TQW (?P<inas>[0-9.]+) inas (?P<gasb>[0-9.]+) gasb (?P=inas) inas (?P<orientation>001|111)\.dat$",
        re.IGNORECASE,
    ),
    re.compile(
        r"bands (?P<inas>[0-9.]+)nm inas (?P<gasb>[0-9.]+)nm gasb (?P=inas)nm inas (?P<orientation>001|111)\.dat$",
        re.IGNORECASE,
    ),
]

BAND_ORDER = ["V0002", "V0001", "C0002", "C0001"]
CONTEXT_BAND_ORDER = [f"V{index:04d}" for index in range(6, 0, -1)] + [
    f"C{index:04d}" for index in range(1, 9)
]
BAND_COLORS = {
    "V0002": "#8B0000",
    "V0001": "#B8860B",
    "C0002": "#87CEFA",
    "C0001": "#0000FF",
}
BAND_LABELS = {
    "V0002": "Valence band 2",
    "V0001": "Valence band 1",
    "C0002": "Conduction band 2",
    "C0001": "Conduction band 1",
}


def is_band_column(column: str) -> bool:
    return bool(re.match(r"^[VC][0-9]+$", column, re.IGNORECASE))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an interactive pure-GaSb TQW phase diagram.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metric-window", type=float, default=0.05)
    parser.add_argument("--band-window", type=float, default=0.05)
    parser.add_argument("--color-limit", type=float, default=40.0)
    parser.add_argument("--exclude", action="append", default=["4/3/4"])
    parser.add_argument("--title", default="Pure GaSb 111 TQW stitched-gap explorer")
    return parser.parse_args()


def parse_file(path: Path) -> dict | None:
    for pattern in PATTERNS:
        match = pattern.match(path.name)
        if match:
            orientation = match.groupdict().get("orientation") or "111"
            return {
                "inas": float(match.group("inas")),
                "gasb": float(match.group("gasb")),
                "orientation": orientation,
            }
    return None


def excluded(inas: float, gasb: float, exclusions: list[str]) -> bool:
    for item in exclusions:
        parts = item.replace("-", "/").split("/")
        if len(parts) != 3:
            continue
        try:
            left = float(parts[0])
            mid = float(parts[1])
            right = float(parts[2])
        except ValueError:
            continue
        if left == right and inas == left and gasb == mid:
            return True
    return False


def round_series(values: pd.Series, digits: int = 4) -> list[float]:
    return [round(float(value), digits) for value in values]


def load_record(path: Path, metric_window: float, band_window: float) -> dict | None:
    parsed = parse_file(path)
    if parsed is None:
        return None

    df = pd.read_csv(path, sep=r"\s+")
    k = df[df.columns[0]]
    metric_mask = k.abs() <= metric_window
    band_mask = k.abs() <= band_window

    vbm = max(float(df.loc[metric_mask, band].max()) for band in ("V0001", "V0002"))
    cbm = min(float(df.loc[metric_mask, band].min()) for band in ("C0001", "C0002"))
    gap = cbm - vbm
    midgap = 0.5 * (vbm + cbm)
    gamma_index = int(k.abs().idxmin())
    v_gamma = max(float(df.loc[gamma_index, band]) for band in ("V0001", "V0002"))
    camelback_depth = vbm - v_gamma

    context_band_order = [band for band in CONTEXT_BAND_ORDER if band in df.columns]
    if not context_band_order:
        context_band_order = [column for column in df.columns[1:] if is_band_column(column)]
    bands = {"K": round_series(k.loc[band_mask])}
    for band in context_band_order:
        bands[band] = round_series(df.loc[band_mask, band])

    context_values = df.loc[band_mask, context_band_order]
    context_y_min = float(context_values.min().min())
    context_y_max = float(context_values.max().max())
    context_pad = max(10.0, 0.04 * (context_y_max - context_y_min))

    zoom_values = df.loc[band_mask, [band for band in BAND_ORDER if band in df.columns]]
    zoom_y_min = float(zoom_values.min().min())
    zoom_y_max = float(zoom_values.max().max())
    zoom_pad = max(3.0, 0.06 * (zoom_y_max - zoom_y_min))

    inas = parsed["inas"]
    gasb = parsed["gasb"]
    geometry = f"{inas:g} / {gasb:g} / {inas:g}"
    return {
        "file": path.name,
        "geometry": geometry,
        "inas": inas,
        "gasb": gasb,
        "orientation": parsed["orientation"],
        "vbm": round(vbm, 4),
        "cbm": round(cbm, 4),
        "gap": round(gap, 4),
        "midgap": round(midgap, 4),
        "camelbackDepth": round(camelback_depth, 4),
        "camelback": camelback_depth > 1.0,
        "yMin": round(zoom_y_min - zoom_pad, 4),
        "yMax": round(min(100.0, zoom_y_max + zoom_pad), 4),
        "contextYMin": round(context_y_min - context_pad, 4),
        "contextYMax": round(min(300.0, context_y_max + context_pad), 4),
        "contextBandOrder": context_band_order,
        "bands": bands,
    }


def load_records(directory: Path, metric_window: float, band_window: float, exclusions: list[str]) -> list[dict]:
    records: list[dict] = []
    for path in sorted(directory.glob("*.dat")):
        record = load_record(path, metric_window, band_window)
        if record is None:
            continue
        if excluded(record["inas"], record["gasb"], exclusions):
            continue
        records.append(record)
    return sorted(records, key=lambda item: (item["gasb"], item["inas"]))


def build_html(records: list[dict], title: str, color_limit: float) -> str:
    payload = {
        "title": title,
        "colorLimit": color_limit,
        "bandOrder": BAND_ORDER,
        "bandColors": BAND_COLORS,
        "bandLabels": BAND_LABELS,
        "records": records,
    }
    payload_json = json.dumps(payload, separators=(",", ":"))
    return HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Pure GaSb TQW stitched-gap explorer</title>
  <style>
    :root {
      --ink: #151515;
      --muted: #666;
      --panel: #ffffff;
      --rule: #d8d8d8;
      --accent: #111;
      --selected: #f6c343;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Aptos", "Segoe UI", sans-serif;
      color: var(--ink);
      background: #f5f5f2;
    }
    .app {
      min-height: 100vh;
      padding: 18px;
      display: grid;
      grid-template-rows: auto 1fr;
      gap: 14px;
    }
    header {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 18px;
    }
    h1 {
      margin: 0;
      font-size: 24px;
      font-weight: 650;
      letter-spacing: 0;
    }
    .hint {
      color: var(--muted);
      font-size: 14px;
      white-space: nowrap;
    }
    .workspace {
      display: grid;
      grid-template-columns: minmax(520px, 1fr) minmax(500px, 0.92fr);
      gap: 16px;
      min-height: 0;
    }
    .panel {
      background: var(--panel);
      border: 1px solid #d6d6d2;
      border-radius: 8px;
      box-shadow: 0 10px 22px rgba(0, 0, 0, 0.06);
      min-width: 0;
      min-height: 0;
      display: grid;
      grid-template-rows: auto 1fr auto;
    }
    .panel-title {
      padding: 12px 14px 0;
      font-size: 16px;
      font-weight: 650;
    }
    .phase-legend {
      margin: -2px 14px 12px;
      padding: 8px 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 22px;
      border: 1px solid #d0d0cc;
      border-radius: 7px;
      background: #fff;
      color: #222;
      font-size: 13px;
    }
    .phase-legend strong { margin-right: 2px; }
    .phase-legend svg {
      width: 22px;
      height: 20px;
      min-height: 0;
      display: inline-block;
      vertical-align: middle;
      margin-right: 5px;
    }
    .plot-wrap {
      min-height: 0;
      padding: 8px 10px 12px;
    }
    svg { display: block; width: 100%; height: 100%; min-height: 560px; }
    #bandSvg { min-height: 1340px; }
    .axis text, .tick-label { fill: var(--ink); font-size: 13px; }
    .axis-title { fill: var(--ink); font-size: 15px; font-weight: 600; }
    .grid-line { stroke: #e6e6e2; stroke-width: 1; }
    .axis-line { stroke: #222; stroke-width: 1.4; }
    .point { cursor: pointer; transition: opacity 120ms ease, transform 120ms ease; }
    .point:hover { opacity: 0.78; }
    .gap-label { font-size: 13px; font-weight: 650; fill: #171717; pointer-events: none; }
    .legend-text { font-size: 13px; fill: #222; }
    .meta {
      padding: 0 14px 12px;
      color: var(--muted);
      font-size: 14px;
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
    }
    .meta strong { color: var(--ink); font-weight: 650; }
    .band-line { fill: none; stroke-linecap: round; stroke-linejoin: round; }
    .context-band { fill: none; stroke-linecap: round; stroke-linejoin: round; }
    .gap-line { stroke: #777; stroke-width: 1.8; stroke-dasharray: 3 4; }
    .gap-marker { stroke: #111; stroke-width: 3; fill: none; }
    .subplot-title { fill: var(--ink); font-size: 14px; font-weight: 700; }
    .inset-fill { fill: #fff; opacity: 0.96; }
    .inset-border { fill: none; stroke: #222; stroke-width: 1.4; }
    .inset-grid { stroke: #e4e4df; stroke-width: 0.8; }
    .inset-tick { fill: var(--ink); font-size: 10px; }
    .inset-title { fill: var(--ink); font-size: 12px; font-weight: 650; }
    @media (max-width: 1100px) {
      .workspace { grid-template-columns: 1fr; }
      .hint { white-space: normal; }
    }
  </style>
</head>
<body>
  <main class="app">
    <header>
      <h1 id="pageTitle"></h1>
      <div class="hint">Click a point to inspect the matching E-k dispersion</div>
    </header>
    <section class="workspace">
      <article class="panel">
        <div class="panel-title">Pure-GaSb phase map</div>
        <div class="plot-wrap"><svg id="phaseSvg" viewBox="0 0 900 660" role="img"></svg></div>
        <div class="phase-legend">
          <strong>Valence shape</strong>
          <span><svg viewBox="0 0 30 26" aria-hidden="true"><polygon points="15,3 28,23 2,23" fill="#222" stroke="#111" stroke-width="2"/></svg>camel-back</span>
          <span><svg viewBox="0 0 30 26" aria-hidden="true"><polygon points="15,3 28,23 2,23" fill="#fff" stroke="#222" stroke-width="2"/></svg>no camel-back</span>
        </div>
      </article>
      <article class="panel">
        <div class="panel-title" id="bandTitle">E-k dispersion</div>
        <div class="plot-wrap"><svg id="bandSvg" viewBox="0 0 760 1360" role="img"></svg></div>
        <div class="meta" id="meta"></div>
      </article>
    </section>
  </main>
  <script>
    const DATA = __PAYLOAD__;
    const records = DATA.records;
    let selectedIndex = 0;

    const NS = "http://www.w3.org/2000/svg";
    const phaseSvg = document.getElementById("phaseSvg");
    const bandSvg = document.getElementById("bandSvg");
    const meta = document.getElementById("meta");
    document.getElementById("pageTitle").textContent = DATA.title;

    function el(name, attrs = {}, parent = null) {
      const node = document.createElementNS(NS, name);
      for (const [key, value] of Object.entries(attrs)) {
        node.setAttribute(key, value);
      }
      if (parent) parent.appendChild(node);
      return node;
    }

    function textNode(parent, x, y, content, attrs = {}) {
      const node = el("text", { x, y, ...attrs }, parent);
      node.textContent = content;
      return node;
    }

    function extent(values, pad = 0) {
      return [Math.min(...values) - pad, Math.max(...values) + pad];
    }

    function scale(domain, range) {
      const [d0, d1] = domain;
      const [r0, r1] = range;
      return value => r0 + ((value - d0) / (d1 - d0)) * (r1 - r0);
    }

    function clamp(value, min, max) {
      return Math.max(min, Math.min(max, value));
    }

    function hexToRgb(hex) {
      const raw = hex.replace("#", "");
      return [
        parseInt(raw.slice(0, 2), 16),
        parseInt(raw.slice(2, 4), 16),
        parseInt(raw.slice(4, 6), 16)
      ];
    }

    function rgbToHex(rgb) {
      return "#" + rgb.map(v => Math.round(v).toString(16).padStart(2, "0")).join("");
    }

    function mix(a, b, t) {
      const ca = hexToRgb(a);
      const cb = hexToRgb(b);
      return rgbToHex(ca.map((v, i) => v + (cb[i] - v) * t));
    }

    function gapColor(gap) {
      const limit = DATA.colorLimit;
      const v = clamp(gap, -limit, limit);
      if (v < 0) return mix("#c91531", "#f0ebe5", (v + limit) / limit);
      return mix("#f0ebe5", "#3552c7", v / limit);
    }

    function trianglePoints(cx, cy, size) {
      const h = size * 0.94;
      return `${cx},${cy - h * 0.58} ${cx - size * 0.56},${cy + h * 0.42} ${cx + size * 0.56},${cy + h * 0.42}`;
    }

    function clear(svg) {
      while (svg.firstChild) svg.removeChild(svg.firstChild);
    }

    function drawAxis(svg, x, y, w, h, xDomain, yDomain, xTicks, yTicks, xTitle, yTitle) {
      const sx = scale(xDomain, [x, x + w]);
      const sy = scale(yDomain, [y + h, y]);
      for (const tick of xTicks) {
        const px = sx(tick);
        el("line", { x1: px, x2: px, y1: y, y2: y + h, class: "grid-line" }, svg);
        textNode(svg, px, y + h + 24, String(tick), { "text-anchor": "middle", class: "tick-label" });
      }
      for (const tick of yTicks) {
        const py = sy(tick);
        el("line", { x1: x, x2: x + w, y1: py, y2: py, class: "grid-line" }, svg);
        textNode(svg, x - 12, py + 5, String(tick), { "text-anchor": "end", class: "tick-label" });
      }
      el("rect", { x, y, width: w, height: h, fill: "none", class: "axis-line" }, svg);
      textNode(svg, x + w / 2, y + h + 58, xTitle, { "text-anchor": "middle", class: "axis-title" });
      const yLabel = textNode(svg, x - 62, y + h / 2, yTitle, { "text-anchor": "middle", class: "axis-title" });
      yLabel.setAttribute("transform", `rotate(-90 ${x - 62} ${y + h / 2})`);
      return { sx, sy };
    }

    function drawColorbar(svg, x, y, h) {
      const defs = el("defs", {}, svg);
      const grad = el("linearGradient", { id: "gapGradient", x1: "0", x2: "0", y1: "1", y2: "0" }, defs);
      el("stop", { offset: "0%", "stop-color": gapColor(-DATA.colorLimit) }, grad);
      el("stop", { offset: "50%", "stop-color": gapColor(0) }, grad);
      el("stop", { offset: "100%", "stop-color": gapColor(DATA.colorLimit) }, grad);
      el("rect", { x, y, width: 24, height: h, fill: "url(#gapGradient)", stroke: "#111" }, svg);
      const ticks = [-DATA.colorLimit, -20, 0, 20, DATA.colorLimit].filter((v, i, arr) => arr.indexOf(v) === i);
      const sy = scale([-DATA.colorLimit, DATA.colorLimit], [y + h, y]);
      ticks.forEach(tick => {
        const py = sy(tick);
        el("line", { x1: x + 24, x2: x + 31, y1: py, y2: py, stroke: "#111", "stroke-width": 1 }, svg);
        textNode(svg, x + 37, py + 4, String(tick), { class: "tick-label" });
      });
      const label = textNode(svg, x + 82, y + h / 2, "Phase color (meV)", {
        "text-anchor": "middle",
        class: "axis-title"
      });
      label.setAttribute("transform", `rotate(-90 ${x + 82} ${y + h / 2})`);
      textNode(svg, x - 26, y + h + 30, "white = no camel-back", {
        "text-anchor": "start",
        class: "legend-text"
      });
      textNode(svg, x - 26, y + h + 48, "negative = semimetal", {
        "text-anchor": "start",
        class: "legend-text"
      });
    }

    function phaseValue(record) {
      return record.camelback ? record.gap : 0;
    }

    function interpolatedGap(x, y) {
      let total = 0;
      let weightTotal = 0;
      for (const record of records) {
        const dx = x - record.inas;
        const dy = y - record.gasb;
        const distance2 = dx * dx + dy * dy;
        if (distance2 < 1e-9) return phaseValue(record);
        const weight = 1 / Math.pow(distance2, 1.25);
        total += weight * phaseValue(record);
        weightTotal += weight;
      }
      return total / weightTotal;
    }

    function drawPhaseBackground(svg, sx, sy, xDomain, yDomain) {
      const nx = 78;
      const ny = 48;
      const xSpan = xDomain[1] - xDomain[0];
      const ySpan = yDomain[1] - yDomain[0];
      for (let ix = 0; ix < nx; ix += 1) {
        const xA = xDomain[0] + (ix / nx) * xSpan;
        const xB = xDomain[0] + ((ix + 1) / nx) * xSpan;
        const xMid = 0.5 * (xA + xB);
        for (let iy = 0; iy < ny; iy += 1) {
          const yA = yDomain[0] + (iy / ny) * ySpan;
          const yB = yDomain[0] + ((iy + 1) / ny) * ySpan;
          const yMid = 0.5 * (yA + yB);
          const gap = clamp(interpolatedGap(xMid, yMid), -DATA.colorLimit, DATA.colorLimit);
          el("rect", {
            x: sx(xA),
            y: sy(yB),
            width: Math.max(0.5, sx(xB) - sx(xA) + 0.35),
            height: Math.max(0.5, sy(yA) - sy(yB) + 0.35),
            fill: gapColor(gap),
            opacity: 0.34
          }, svg);
        }
      }
    }

    function drawPhase() {
      clear(phaseSvg);
      const margin = { left: 88, top: 44, right: 122, bottom: 76 };
      const w = 900 - margin.left - margin.right;
      const h = 660 - margin.top - margin.bottom;
      const xDomain = extent(records.map(r => r.inas), 0.7);
      const yDomain = extent(records.map(r => r.gasb), 0.7);
      const xTicks = [];
      for (let v = Math.ceil(xDomain[0]); v <= Math.floor(xDomain[1]); v++) xTicks.push(v);
      const yTicks = [];
      for (let v = Math.ceil(yDomain[0] * 2) / 2; v <= Math.floor(yDomain[1] * 2) / 2; v += 0.5) yTicks.push(v);
      const bgSx = scale(xDomain, [margin.left, margin.left + w]);
      const bgSy = scale(yDomain, [margin.top + h, margin.top]);
      drawPhaseBackground(phaseSvg, bgSx, bgSy, xDomain, yDomain);
      const { sx, sy } = drawAxis(
        phaseSvg,
        margin.left,
        margin.top,
        w,
        h,
        xDomain,
        yDomain,
        xTicks,
        yTicks.map(v => Number(v.toFixed(1))),
        "InAs thickness (nm)",
        "GaSb thickness (nm)"
      );

      records.forEach((record, index) => {
        const x = sx(record.inas);
        const y = sy(record.gasb);
        const color = gapColor(record.gap);
        const fill = record.camelback ? color : "#fff";
        const stroke = record.camelback ? "#111" : "#777";
        const width = index === selectedIndex ? 5 : (record.camelback ? 2.6 : 3.4);
        const point = el("polygon", {
          points: trianglePoints(x, y, 27),
          fill,
          stroke: index === selectedIndex ? "var(--selected)" : stroke,
          "stroke-width": width,
          class: "point"
        }, phaseSvg);
        point.addEventListener("click", () => {
          selectedIndex = index;
          drawPhase();
          drawBand(record);
        });
        textNode(phaseSvg, x, y - 25, record.gap.toFixed(1), {
          "text-anchor": "middle",
          class: "gap-label"
        });
      });

      drawColorbar(phaseSvg, 792, 64, 450);
    }

    function linePath(xs, ys, sx, sy) {
      return xs.map((x, i) => `${i === 0 ? "M" : "L"}${sx(x).toFixed(2)},${sy(ys[i]).toFixed(2)}`).join(" ");
    }

    function niceStep(rawStep) {
      const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)));
      const residual = rawStep / magnitude;
      if (residual <= 1) return magnitude;
      if (residual <= 2) return 2 * magnitude;
      if (residual <= 5) return 5 * magnitude;
      return 10 * magnitude;
    }

    function yTicksFor(min, max, targetCount = 6) {
      const span = Math.max(1e-9, max - min);
      const step = niceStep(span / targetCount);
      const start = Math.ceil(min / step) * step;
      const ticks = [];
      for (let value = start; value <= max; value += step) ticks.push(value);
      return ticks.map(value => Number(value.toFixed(6)));
    }

    function bandStrokeColor(band) {
      if (DATA.bandColors[band]) return DATA.bandColors[band];
      return band.startsWith("C") ? "#6f90a9" : "#716b62";
    }

    function drawInsetAxis(svg, x, y, w, h, xDomain, yDomain) {
      el("rect", { x: x - 10, y: y - 26, width: w + 20, height: h + 52, rx: 8, class: "inset-fill" }, svg);
      const sx = scale(xDomain, [x, x + w]);
      const sy = scale(yDomain, [y + h, y]);
      [-0.05, 0, 0.05].forEach(tick => {
        const px = sx(tick);
        el("line", { x1: px, x2: px, y1: y, y2: y + h, class: "inset-grid" }, svg);
      });
      yTicksFor(yDomain[0], yDomain[1], 4).forEach(tick => {
        const py = sy(tick);
        el("line", { x1: x, x2: x + w, y1: py, y2: py, class: "inset-grid" }, svg);
        textNode(svg, x - 7, py + 3, String(tick), { "text-anchor": "end", class: "inset-tick" });
      });
      el("rect", { x, y, width: w, height: h, class: "inset-border" }, svg);
      textNode(svg, x + 8, y - 9, "critical-band zoom", { class: "inset-title" });
      [
        { value: -0.05, label: "[1-10]" },
        { value: 0, label: "Gamma" },
        { value: 0.05, label: "[2-1-1]" }
      ].forEach(item => {
        textNode(svg, sx(item.value), y + h + 18, item.label, {
          "text-anchor": "middle",
          class: "inset-tick"
        });
      });
      return { sx, sy };
    }

    function drawCriticalInset(svg, record, x, y, w, h) {
      const xDomain = [-0.05, 0.05];
      const yDomain = [record.yMin, record.yMax];
      const { sx, sy } = drawInsetAxis(svg, x, y, w, h, xDomain, yDomain);
      const clipId = "critical-inset-clip";
      const defs = svg.querySelector("defs") || el("defs", {}, svg);
      const clip = el("clipPath", { id: clipId }, defs);
      el("rect", { x, y, width: w, height: h }, clip);
      const clipped = el("g", { "clip-path": `url(#${clipId})` }, svg);
      const xs = record.bands.K;
      DATA.bandOrder.forEach(band => {
        if (!record.bands[band]) return;
        el("path", {
          d: linePath(xs, record.bands[band], sx, sy),
          stroke: DATA.bandColors[band],
          "stroke-width": band.startsWith("C0001") || band.startsWith("V0001") ? 3.2 : 2.6,
          class: "band-line"
        }, clipped);
      });
      el("line", { x1: x, x2: x + w, y1: sy(record.vbm), y2: sy(record.vbm), class: "gap-line" }, clipped);
      el("line", { x1: x, x2: x + w, y1: sy(record.cbm), y2: sy(record.cbm), class: "gap-line" }, clipped);
      const xGap = sx(0.004);
      el("line", { x1: xGap, x2: xGap, y1: sy(record.vbm), y2: sy(record.cbm), class: "gap-marker" }, clipped);
      el("line", { x1: xGap - 7, x2: xGap + 7, y1: sy(record.vbm), y2: sy(record.vbm), class: "gap-marker" }, clipped);
      el("line", { x1: xGap - 7, x2: xGap + 7, y1: sy(record.cbm), y2: sy(record.cbm), class: "gap-marker" }, clipped);
      textNode(svg, xGap + 12, sy(record.midgap) + 4, `${record.gap.toFixed(1)} meV`, {
        class: "gap-label"
      });
    }

    function drawDirectionLabels(svg, sx, y) {
      const customLabels = [
        { value: -0.05, label: "[1-10]" },
        { value: 0, label: "Gamma" },
        { value: 0.05, label: "[2-1-1]" }
      ];
      customLabels.forEach(item => {
        textNode(svg, sx(item.value), y, item.label, {
          "text-anchor": "middle",
          class: "tick-label"
        });
      });
    }

    function drawCriticalPlot(svg, record, layout) {
      const { x, y, w, h } = layout;
      const xDomain = [-0.05, 0.05];
      const yDomain = [record.yMin, record.yMax];
      const clipId = "critical-plot-clip";
      const defs = svg.querySelector("defs") || el("defs", {}, svg);
      const clip = el("clipPath", { id: clipId }, defs);
      el("rect", { x, y, width: w, height: h }, clip);
      textNode(svg, x, y - 14, "Near-gap zoom", { class: "subplot-title" });
      const { sx, sy } = drawAxis(
        svg,
        x,
        y,
        w,
        h,
        xDomain,
        yDomain,
        [-0.05, 0, 0.05],
        yTicksFor(yDomain[0], yDomain[1], 5),
        "",
        "Energy (meV)"
      );
      drawDirectionLabels(svg, sx, y + h + 48);
      const xs = record.bands.K;
      const clipped = el("g", { "clip-path": `url(#${clipId})` }, svg);
      DATA.bandOrder.forEach(band => {
        if (!record.bands[band]) return;
        el("path", {
          d: linePath(xs, record.bands[band], sx, sy),
          stroke: DATA.bandColors[band],
          "stroke-width": band.startsWith("C0001") || band.startsWith("V0001") ? 3.4 : 2.8,
          class: "band-line"
        }, clipped);
      });
      el("line", { x1: x, x2: x + w, y1: sy(record.vbm), y2: sy(record.vbm), class: "gap-line" }, clipped);
      el("line", { x1: x, x2: x + w, y1: sy(record.cbm), y2: sy(record.cbm), class: "gap-line" }, clipped);
      const xGap = sx(0.004);
      el("line", { x1: xGap, x2: xGap, y1: sy(record.vbm), y2: sy(record.cbm), class: "gap-marker" }, clipped);
      el("line", { x1: xGap - 8, x2: xGap + 8, y1: sy(record.vbm), y2: sy(record.vbm), class: "gap-marker" }, clipped);
      el("line", { x1: xGap - 8, x2: xGap + 8, y1: sy(record.cbm), y2: sy(record.cbm), class: "gap-marker" }, clipped);
      textNode(svg, xGap + 14, sy(record.midgap) + 5, `${record.gap.toFixed(1)} meV`, {
        class: "gap-label"
      });
      drawBandLegend(svg, x + 12, y + 12);
    }

    function drawContextPlot(svg, record, layout) {
      const { x, y, w, h } = layout;
      const xDomain = [-0.05, 0.05];
      const yDomain = [record.contextYMin, record.contextYMax];
      const clipId = "context-plot-clip";
      const defs = svg.querySelector("defs") || el("defs", {}, svg);
      const clip = el("clipPath", { id: clipId }, defs);
      el("rect", { x, y, width: w, height: h }, clip);
      textNode(svg, x, y - 14, "V1-V6 and C1-C8 context", { class: "subplot-title" });
      const { sx, sy } = drawAxis(
        svg,
        x,
        y,
        w,
        h,
        xDomain,
        yDomain,
        [-0.05, 0, 0.05],
        yTicksFor(yDomain[0], yDomain[1], 6),
        "",
        "Energy (meV)"
      );
      drawDirectionLabels(svg, sx, y + h + 48);
      const xs = record.bands.K;
      const clipped = el("g", { "clip-path": `url(#${clipId})` }, svg);
      const contextBands = record.contextBandOrder || DATA.bandOrder;
      contextBands.forEach(band => {
        if (!record.bands[band]) return;
        const isCritical = DATA.bandOrder.includes(band);
        el("path", {
          d: linePath(xs, record.bands[band], sx, sy),
          stroke: bandStrokeColor(band),
          "stroke-width": isCritical ? 1.9 : 1.1,
          opacity: isCritical ? 0.86 : 0.48,
          class: "context-band"
        }, clipped);
      });
    }

    function drawBand(record) {
      clear(bandSvg);
      document.getElementById("bandTitle").textContent = `${record.geometry}    zoom + context E-k plots    gap ${record.gap.toFixed(1)} meV`;
      const defs = el("defs", {}, bandSvg);
      drawCriticalPlot(bandSvg, record, { x: 150, y: 66, w: 470, h: 545 });
      drawContextPlot(bandSvg, record, { x: 150, y: 820, w: 470, h: 475 });
      meta.innerHTML = [
        `<div><strong>Geometry</strong><br>${record.geometry}</div>`,
        `<div><strong>Gap</strong><br>${record.gap.toFixed(2)} meV</div>`,
        `<div><strong>Valence shape</strong><br>${record.camelback ? "camel-back" : "no camel-back"}</div>`,
        `<div><strong>VBM</strong><br>${record.vbm.toFixed(2)} meV</div>`,
        `<div><strong>CBM</strong><br>${record.cbm.toFixed(2)} meV</div>`,
        `<div><strong>File</strong><br>${record.file}</div>`
      ].join("");
    }

    function drawBandLegend(svg, x, y) {
      el("rect", { x, y, width: 244, height: 102, rx: 6, fill: "#fff", stroke: "#d0d0cc", opacity: 0.94 }, svg);
      DATA.bandOrder.forEach((band, i) => {
        const row = Math.floor(i / 2);
        const col = i % 2;
        const px = x + 14 + col * 118;
        const py = y + 30 + row * 36;
        el("line", { x1: px, x2: px + 28, y1: py, y2: py, stroke: DATA.bandColors[band], "stroke-width": 4 }, svg);
        textNode(svg, px + 34, py + 5, DATA.bandLabels[band], { class: "legend-text" });
      });
    }

    if (!records.length) {
      document.querySelector(".workspace").innerHTML = "<p>No records found.</p>";
    } else {
      selectedIndex = records.findIndex(r => r.gap < 0);
      if (selectedIndex < 0) selectedIndex = 0;
      drawPhase();
      drawBand(records[selectedIndex]);
    }
  </script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    records = load_records(args.directory, args.metric_window, args.band_window, args.exclude)
    if not records:
        raise SystemExit("No matching pure-GaSb TQW records found.")
    html = build_html(records, args.title, args.color_limit)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
