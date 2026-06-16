#!/usr/bin/env python3
"""
Build a standalone interactive HTML explorer for the Schmid et al. Fig. 3(a)
validation sweep.

The HTML is meant to answer one question clearly: how was each point in the
gap-vs-InAs-thickness plot calculated from the Cadtronics E-k data?
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd


FILENAME_RE = re.compile(
    r"^(?P<d1>[0-9.]+)\s+(?P<d2>[0-9.]+)\s+(?P=d1)(?:\s+.*)?\.dat$",
    re.IGNORECASE,
)

PLOT_BANDS = ["V0002", "V0001", "C0001", "C0002", "C0003", "C0004"]
BAND_COLORS = {
    "V0002": "#8B0000",
    "V0001": "#B8860B",
    "C0001": "#0000FF",
    "C0002": "#87CEFA",
    "C0003": "#5DADE2",
    "C0004": "#A9CCE3",
}
BAND_LABELS = {
    "V0002": "Valence band 2",
    "V0001": "Valence band 1",
    "C0001": "Conduction band 1",
    "C0002": "Conduction band 2",
    "C0003": "Conduction band 3",
    "C0004": "Conduction band 4",
}
CAMELBACK_THRESHOLD_MEV = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create an interactive Wurzburg Fig. 3(a) validation HTML.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--metric-window", type=float, default=0.05)
    parser.add_argument("--band-window", type=float, default=0.05)
    parser.add_argument("--title", default="Cadtronics Fig. 3(a) validation explorer")
    return parser.parse_args()


def parse_file(path: Path) -> tuple[float, float] | None:
    match = FILENAME_RE.match(path.name)
    if match is None:
        return None
    return float(match.group("d1")), float(match.group("d2"))


def round_list(values: pd.Series, digits: int = 4) -> list[float]:
    return [round(float(value), digits) for value in values]


def extremum_info(df: pd.DataFrame, k: pd.Series, mask: pd.Series, bands: list[str], mode: str) -> dict:
    best: dict | None = None
    for band in bands:
        values = df.loc[mask, band].astype(float)
        idx = int(values.idxmax() if mode == "max" else values.idxmin())
        info = {
            "band": band,
            "k": round(float(k.loc[idx]), 6),
            "energy": round(float(df.loc[idx, band]), 4),
            "index": idx,
        }
        if best is None:
            best = info
            continue
        if mode == "max" and info["energy"] > best["energy"]:
            best = info
        if mode == "min" and info["energy"] < best["energy"]:
            best = info
    if best is None:
        raise ValueError("No extremum found.")
    return best


def load_record(path: Path, metric_window: float, band_window: float) -> dict | None:
    parsed = parse_file(path)
    if parsed is None:
        return None
    d1, d2 = parsed
    df = pd.read_csv(path, sep=r"\s+")
    k = df[df.columns[0]].astype(float)
    metric_mask = k.abs() <= metric_window
    band_mask = k.abs() <= band_window
    if not bool(metric_mask.any()):
        raise ValueError(f"No k-points inside metric window for {path.name}")
    if not bool(band_mask.any()):
        raise ValueError(f"No k-points inside band window for {path.name}")

    present_bands = [band for band in PLOT_BANDS if band in df.columns]
    if not {"V0001", "V0002", "C0001", "C0002"}.issubset(set(present_bands)):
        raise ValueError(f"Need V0001,V0002,C0001,C0002 in {path.name}")

    vbm = extremum_info(df, k, metric_mask, ["V0001", "V0002"], "max")
    cbm = extremum_info(df, k, metric_mask, ["C0001", "C0002"], "min")
    gap = round(cbm["energy"] - vbm["energy"], 4)
    midgap = round(0.5 * (cbm["energy"] + vbm["energy"]), 4)

    gamma_idx = int(k.abs().idxmin())
    v_gamma_candidates = [
        {"band": band, "energy": float(df.loc[gamma_idx, band])}
        for band in ["V0001", "V0002"]
    ]
    c_gamma_candidates = [
        {"band": band, "energy": float(df.loc[gamma_idx, band])}
        for band in ["C0001", "C0002"]
    ]
    v_gamma = max(v_gamma_candidates, key=lambda item: item["energy"])
    c_gamma = min(c_gamma_candidates, key=lambda item: item["energy"])

    bands = {"K": round_list(k.loc[band_mask])}
    for band in present_bands:
        bands[band] = round_list(df.loc[band_mask, band])

    energies = df.loc[band_mask, present_bands].astype(float)
    y_min = float(energies.min().min())
    y_max = float(energies.max().max())
    y_pad = max(5.0, 0.08 * (y_max - y_min))

    return {
        "file": path.name,
        "d1": d1,
        "d2": d2,
        "geometry": f"{d1:g} / {d2:g} / {d1:g}",
        "metricWindow": metric_window,
        "bandWindow": band_window,
        "gap": gap,
        "midgap": midgap,
        "vbm": vbm,
        "cbm": cbm,
        "vGamma": {
            "band": v_gamma["band"],
            "k": round(float(k.loc[gamma_idx]), 6),
            "energy": round(float(v_gamma["energy"]), 4),
        },
        "cGamma": {
            "band": c_gamma["band"],
            "k": round(float(k.loc[gamma_idx]), 6),
            "energy": round(float(c_gamma["energy"]), 4),
        },
        "gammaGap": round(float(c_gamma["energy"] - v_gamma["energy"]), 4),
        "camelbackDepth": round(float(vbm["energy"] - v_gamma["energy"]), 4),
        "bands": bands,
        "bandOrder": present_bands,
        "yMin": round(y_min - y_pad, 4),
        "yMax": round(min(100.0, y_max + y_pad), 4),
    }


def load_records(directory: Path, metric_window: float, band_window: float) -> list[dict]:
    records: list[dict] = []
    for path in sorted(directory.glob("*.dat")):
        record = load_record(path, metric_window, band_window)
        if record is not None:
            records.append(record)
    if not records:
        raise SystemExit(f"No matching .dat files found in {directory}")
    return sorted(records, key=lambda item: item["d1"])


def interpolate_transition(
    records: list[dict],
    key: str,
    level: float,
    direction: str,
) -> float | None:
    for left, right in zip(records, records[1:]):
        left_value = float(left[key])
        right_value = float(right[key])
        if direction == "up" and not (left_value <= level <= right_value):
            continue
        if direction == "down" and not (left_value >= level >= right_value):
            continue
        if right_value == left_value:
            return float(left["d1"])
        fraction = (level - left_value) / (right_value - left_value)
        return round(float(left["d1"]) + fraction * (float(right["d1"]) - float(left["d1"])), 4)
    return None


def data_transitions(records: list[dict]) -> dict:
    return {
        "camelbackThreshold": CAMELBACK_THRESHOLD_MEV,
        "trivialToTi": interpolate_transition(records, "camelbackDepth", CAMELBACK_THRESHOLD_MEV, "up"),
        "tiToSm": interpolate_transition(records, "gap", 0.0, "down"),
    }


def build_html(records: list[dict], title: str) -> str:
    payload = {
        "title": title,
        "bandColors": BAND_COLORS,
        "bandLabels": BAND_LABELS,
        "records": records,
        "dataTransitions": data_transitions(records),
        "paperPoints": [
            {"d1": 8.0, "gap": 22.6, "label": "triv"},
            {"d1": 10.0, "gap": 11.0, "label": "hyb1"},
            {"d1": 10.75, "gap": 6.7, "label": "hyb2"},
            {"d1": 13.5, "gap": 0.0, "label": "sm"},
        ],
    }
    return HTML_TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cadtronics Fig. 3(a) validation explorer</title>
  <style>
    :root {
      --bg: #f4f2ec;
      --panel: #ffffff;
      --ink: #181818;
      --muted: #676767;
      --grid: #dddddd;
      --accent: #153e75;
      --paper: #b22222;
      --selected: #f3c623;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--ink);
      font-family: "Aptos", "Segoe UI", sans-serif;
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
      align-items: flex-end;
      justify-content: space-between;
      gap: 18px;
    }
    h1 {
      margin: 0;
      font-size: 28px;
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    .note {
      max-width: 660px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.35;
      text-align: right;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(420px, 0.95fr) minmax(540px, 1.25fr);
      gap: 14px;
      min-height: 0;
    }
    .panel {
      background: var(--panel);
      border: 1px solid #d6d2c6;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(30, 25, 10, 0.08);
      padding: 14px;
      min-width: 0;
      overflow: hidden;
    }
    .panelTitle {
      margin: 0 0 8px;
      font-size: 16px;
      font-weight: 800;
      letter-spacing: -0.01em;
    }
    svg {
      display: block;
      width: 100%;
      height: auto;
    }
    .axis text {
      fill: var(--ink);
      font-size: 13px;
    }
    .axis path,
    .axis line {
      stroke: var(--ink);
      stroke-width: 1.4;
      shape-rendering: crispEdges;
    }
    .gridLine {
      stroke: var(--grid);
      stroke-width: 1;
      shape-rendering: crispEdges;
    }
    .region {
      opacity: 0.7;
    }
    .regionLabel {
      fill: #333;
      font-size: 15px;
      font-weight: 800;
    }
    .point {
      cursor: pointer;
      transition: transform 120ms ease;
    }
    .point:hover {
      filter: drop-shadow(0 0 4px rgba(0,0,0,0.25));
    }
    .selectedPoint {
      stroke: #000;
      stroke-width: 3.4;
      fill: var(--selected);
    }
    .paperPoint {
      stroke: var(--paper);
      stroke-width: 2.6;
    }
    .bandLine {
      fill: none;
      stroke-width: 3;
      stroke-linejoin: round;
      stroke-linecap: round;
    }
    .guide {
      stroke: #333;
      stroke-width: 1.5;
      stroke-dasharray: 5 5;
      opacity: 0.82;
    }
    .gapLine {
      stroke: #111;
      stroke-width: 2;
    }
    .gammaGapLine {
      stroke: #5f2385;
      stroke-width: 2.4;
    }
    .camelLine {
      stroke: #b8860b;
      stroke-width: 2.4;
    }
    .bracketCap {
      stroke-width: 2.4;
      stroke-linecap: square;
    }
    .markerVbm {
      fill: #ffcf33;
      stroke: #111;
      stroke-width: 2.2;
    }
    .markerCbm {
      fill: #5bc0ff;
      stroke: #111;
      stroke-width: 2.2;
    }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      align-items: center;
      font-size: 13px;
      margin: 6px 0 2px;
    }
    .legendItem {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      white-space: nowrap;
    }
    .swatch {
      width: 22px;
      height: 0;
      border-top: 3px solid currentColor;
    }
    .details {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
      margin-top: 8px;
      font-size: 13px;
    }
    .card {
      background: #faf9f5;
      border: 1px solid #ded9cc;
      border-radius: 12px;
      padding: 10px;
      min-width: 0;
    }
    .card h3 {
      margin: 0 0 8px;
      font-size: 13px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #444;
    }
    .row {
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 8px;
      border-top: 1px solid #e7e2d7;
      padding: 5px 0;
    }
    .row:first-of-type {
      border-top: 0;
    }
    .label {
      color: var(--muted);
    }
    .value {
      font-family: "Cascadia Mono", "Consolas", monospace;
      text-align: right;
      white-space: nowrap;
    }
    .formula {
      font-family: "Cascadia Mono", "Consolas", monospace;
      font-size: 14px;
      background: #111;
      color: #fff;
      border-radius: 10px;
      padding: 10px;
      margin-top: 8px;
      overflow-x: auto;
    }
    @media (max-width: 1050px) {
      .grid { grid-template-columns: 1fr; }
      .note { text-align: left; }
      header { display: block; }
    }
  </style>
</head>
<body>
<div class="app">
  <header>
    <h1 id="title"></h1>
    <div class="note">
      Click a Cadtronics point to inspect the exact E-k curves, extrema, and arithmetic used for that gap value.
      Red x markers are the Schmid et al. checkpoint values.
    </div>
  </header>

  <main class="grid">
    <section class="panel">
      <h2 class="panelTitle">Fig. 3(a) sweep: extracted gap vs InAs thickness</h2>
      <svg id="sweepSvg" viewBox="0 0 760 520" role="img"></svg>
    </section>

    <section class="panel">
      <h2 class="panelTitle" id="bandTitle">Selected E-k calculation</h2>
      <div class="legend" id="bandLegend"></div>
      <svg id="bandSvg" viewBox="0 0 760 760" role="img"></svg>
      <div class="details">
        <div class="card">
          <h3>Extrema used</h3>
          <div id="extremaTable"></div>
        </div>
        <div class="card">
          <h3>Calculation</h3>
          <div id="calcTable"></div>
          <div class="formula" id="formula"></div>
        </div>
      </div>
    </section>
  </main>
</div>

<script>
const payload = __PAYLOAD__;
let selectedIndex = 0;

const fmt = (value, digits = 1) => Number(value).toFixed(digits);
const fmtK = value => Number(value).toFixed(4);
const ns = "http://www.w3.org/2000/svg";

function el(name, attrs = {}, text = "") {
  const node = document.createElementNS(ns, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== "") node.textContent = text;
  return node;
}

function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
}

function scaleLinear(domain, range) {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  return value => r0 + (value - d0) * (r1 - r0) / (d1 - d0);
}

function niceTicks(min, max, count = 6) {
  if (min === max) return [min];
  const span = max - min;
  const rough = span / Math.max(1, count - 1);
  const power = Math.pow(10, Math.floor(Math.log10(Math.abs(rough))));
  const norm = rough / power;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * power;
  const start = Math.ceil(min / step) * step;
  const ticks = [];
  for (let value = start; value <= max + step * 0.5; value += step) {
    ticks.push(Number(value.toFixed(10)));
  }
  return ticks;
}

function pathFromXY(xs, ys) {
  return xs.map((x, i) => `${i === 0 ? "M" : "L"} ${x.toFixed(2)} ${ys[i].toFixed(2)}`).join(" ");
}

function drawAxes(svg, plot, xScale, yScale, xTicks, yTicks, xLabel, yLabel) {
  const g = el("g", {class: "axis"});
  svg.appendChild(g);

  for (const tick of xTicks) {
    const x = xScale(tick);
    svg.appendChild(el("line", {class: "gridLine", x1: x, y1: plot.y, x2: x, y2: plot.y + plot.h}));
    g.appendChild(el("line", {x1: x, y1: plot.y + plot.h, x2: x, y2: plot.y + plot.h + 7}));
    const t = el("text", {x, y: plot.y + plot.h + 25, "text-anchor": "middle"}, fmt(tick, Number.isInteger(tick) ? 0 : 1));
    g.appendChild(t);
  }

  for (const tick of yTicks) {
    const y = yScale(tick);
    svg.appendChild(el("line", {class: "gridLine", x1: plot.x, y1: y, x2: plot.x + plot.w, y2: y}));
    g.appendChild(el("line", {x1: plot.x - 7, y1: y, x2: plot.x, y2: y}));
    const t = el("text", {x: plot.x - 12, y: y + 4, "text-anchor": "end"}, fmt(tick, 0));
    g.appendChild(t);
  }

  g.appendChild(el("line", {x1: plot.x, y1: plot.y + plot.h, x2: plot.x + plot.w, y2: plot.y + plot.h}));
  g.appendChild(el("line", {x1: plot.x, y1: plot.y, x2: plot.x, y2: plot.y + plot.h}));
  g.appendChild(el("text", {x: plot.x + plot.w / 2, y: plot.y + plot.h + 55, "text-anchor": "middle"}, xLabel));
  const yl = el("text", {x: plot.x - 64, y: plot.y + plot.h / 2, "text-anchor": "middle", transform: `rotate(-90 ${plot.x - 64} ${plot.y + plot.h / 2})`}, yLabel);
  g.appendChild(yl);
}

function drawSweep() {
  const svg = document.getElementById("sweepSvg");
  clear(svg);
  const plot = {x: 82, y: 44, w: 628, h: 385};
  const records = payload.records;
  const xMin = Math.min(...records.map(r => r.d1)) - 0.25;
  const xMax = Math.max(...records.map(r => r.d1)) + 0.25;
  const yMin = Math.min(-8, Math.min(...records.map(r => r.gap)) - 5);
  const yMax = Math.max(32, Math.max(...records.map(r => r.gap)) + 6);
  const x = scaleLinear([xMin, xMax], [plot.x, plot.x + plot.w]);
  const y = scaleLinear([yMin, yMax], [plot.y + plot.h, plot.y]);

  const transitions = payload.dataTransitions;
  const t1 = transitions.trivialToTi ?? xMin;
  const t2 = transitions.tiToSm ?? xMax;
  if (t1 > xMin) {
    svg.appendChild(el("rect", {class: "region", x: x(xMin), y: plot.y, width: x(t1) - x(xMin), height: plot.h, fill: "#e2e2e2"}));
  }
  if (t2 > t1) {
    svg.appendChild(el("rect", {class: "region", x: x(t1), y: plot.y, width: x(t2) - x(t1), height: plot.h, fill: "#c7c7c7"}));
  }
  if (xMax > t2) {
    svg.appendChild(el("rect", {class: "region", x: x(t2), y: plot.y, width: x(xMax) - x(t2), height: plot.h, fill: "#ffffff"}));
  }

  drawAxes(svg, plot, x, y, niceTicks(xMin, xMax, 8), niceTicks(yMin, yMax, 7), "InAs thickness d1 (nm)", "Extracted gap Egap (meV)");

  svg.appendChild(el("line", {x1: plot.x, y1: y(0), x2: plot.x + plot.w, y2: y(0), stroke: "#111", "stroke-width": 1.4}));
  if (transitions.trivialToTi !== null) {
    svg.appendChild(el("line", {x1: x(t1), y1: plot.y, x2: x(t1), y2: plot.y + plot.h, stroke: "#333", "stroke-width": 1.5, "stroke-dasharray": "6 5"}));
    svg.appendChild(el("text", {x: x(t1), y: plot.y + 24, "text-anchor": "middle", "font-size": 12, fill: "#333"}, `data ${fmt(t1, 2)}`));
  }
  if (transitions.tiToSm !== null) {
    svg.appendChild(el("line", {x1: x(t2), y1: plot.y, x2: x(t2), y2: plot.y + plot.h, stroke: "#333", "stroke-width": 1.5, "stroke-dasharray": "6 5"}));
    svg.appendChild(el("text", {x: x(t2), y: plot.y + 24, "text-anchor": "middle", "font-size": 12, fill: "#333"}, `data ${fmt(t2, 2)}`));
  }
  if (t1 > xMin) svg.appendChild(el("text", {class: "regionLabel", x: x((xMin + t1) / 2), y: plot.y + 48, "text-anchor": "middle"}, "trivial"));
  if (t2 > t1) svg.appendChild(el("text", {class: "regionLabel", x: x((t1 + t2) / 2), y: plot.y + 48, "text-anchor": "middle"}, "TI"));
  if (xMax > t2) svg.appendChild(el("text", {class: "regionLabel", x: x((t2 + xMax) / 2), y: plot.y + 48, "text-anchor": "middle"}, "SM"));

  const line = pathFromXY(records.map(r => x(r.d1)), records.map(r => y(r.gap)));
  svg.appendChild(el("path", {d: line, fill: "none", stroke: "var(--accent)", "stroke-width": 3.2}));

  payload.paperPoints.forEach(p => {
    const px = x(p.d1), py = y(p.gap), s = 8;
    svg.appendChild(el("line", {class: "paperPoint", x1: px - s, y1: py - s, x2: px + s, y2: py + s}));
    svg.appendChild(el("line", {class: "paperPoint", x1: px - s, y1: py + s, x2: px + s, y2: py - s}));
    svg.appendChild(el("text", {x: px + 10, y: py - 8, fill: "var(--paper)", "font-size": 12, "font-weight": 800}, p.label));
  });

  records.forEach((r, i) => {
    const point = el("circle", {
      class: `point ${i === selectedIndex ? "selectedPoint" : ""}`,
      cx: x(r.d1),
      cy: y(r.gap),
      r: i === selectedIndex ? 9 : 7,
      fill: i === selectedIndex ? "var(--selected)" : "#fff",
      stroke: "var(--accent)",
      "stroke-width": 2.4,
    });
    point.addEventListener("click", () => selectRecord(i));
    svg.appendChild(point);
    svg.appendChild(el("text", {x: x(r.d1), y: y(r.gap) - 13, "text-anchor": "middle", "font-size": 11}, fmt(r.gap, 1)));
  });

  const legendW = 250;
  const legendH = 58;
  const legendX = plot.x + plot.w - legendW - 12;
  const legendY = plot.y + 12;
  svg.appendChild(el("rect", {x: legendX, y: legendY, width: legendW, height: legendH, rx: 8, fill: "rgba(255,255,255,0.88)", stroke: "#d8d8d8"}));
  svg.appendChild(el("circle", {cx: legendX + 18, cy: legendY + 20, r: 7, fill: "#fff", stroke: "var(--accent)", "stroke-width": 2.4}));
  svg.appendChild(el("text", {x: legendX + 36, y: legendY + 24, "font-size": 13}, "Cadtronics extracted gap"));
  svg.appendChild(el("line", {class: "paperPoint", x1: legendX + 11, y1: legendY + 39, x2: legendX + 25, y2: legendY + 53}));
  svg.appendChild(el("line", {class: "paperPoint", x1: legendX + 11, y1: legendY + 53, x2: legendX + 25, y2: legendY + 39}));
  svg.appendChild(el("text", {x: legendX + 36, y: legendY + 50, "font-size": 13}, "Schmid et al. checkpoints"));
}

function drawBandLegend(record) {
  const legend = document.getElementById("bandLegend");
  legend.innerHTML = "";
  record.bandOrder.forEach(band => {
    const item = document.createElement("span");
    item.className = "legendItem";
    const swatch = document.createElement("span");
    swatch.className = "swatch";
    swatch.style.color = payload.bandColors[band] || "#555";
    item.appendChild(swatch);
    const text = document.createElement("span");
    text.textContent = payload.bandLabels[band] || band;
    item.appendChild(text);
    legend.appendChild(item);
  });
  const vbm = document.createElement("span");
  vbm.className = "legendItem";
  vbm.innerHTML = "<span style=\"display:inline-block;width:12px;height:12px;border-radius:50%;background:#ffcf33;border:2px solid #111\"></span> VBM";
  legend.appendChild(vbm);
  const cbm = document.createElement("span");
  cbm.className = "legendItem";
  cbm.innerHTML = "<span style=\"display:inline-block;width:12px;height:12px;border-radius:50%;background:#5bc0ff;border:2px solid #111\"></span> CBM";
  legend.appendChild(cbm);
}

function drawBandPlot(record) {
  const svg = document.getElementById("bandSvg");
  clear(svg);
  const defs = el("defs");
  const marker = el("marker", {id: "arrow", viewBox: "0 0 10 10", refX: 5, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse"});
  marker.appendChild(el("path", {d: "M 0 0 L 10 5 L 0 10 z", fill: "#111"}));
  defs.appendChild(marker);
  const arrowPurple = el("marker", {id: "arrowPurple", viewBox: "0 0 10 10", refX: 5, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse"});
  arrowPurple.appendChild(el("path", {d: "M 0 0 L 10 5 L 0 10 z", fill: "#5f2385"}));
  defs.appendChild(arrowPurple);
  const arrowGold = el("marker", {id: "arrowGold", viewBox: "0 0 10 10", refX: 5, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse"});
  arrowGold.appendChild(el("path", {d: "M 0 0 L 10 5 L 0 10 z", fill: "#b8860b"}));
  defs.appendChild(arrowGold);
  svg.appendChild(defs);

  const plot = {x: 102, y: 44, w: 500, h: 610};
  const kVals = record.bands.K;
  const xMin = Math.min(...kVals), xMax = Math.max(...kVals);
  const yMin = record.yMin, yMax = record.yMax;
  const x = scaleLinear([xMin, xMax], [plot.x, plot.x + plot.w]);
  const y = scaleLinear([yMin, yMax], [plot.y + plot.h, plot.y]);

  drawAxes(svg, plot, x, y, niceTicks(xMin, xMax, 7), niceTicks(yMin, yMax, 7), "k (1/A)", "Energy (meV)");

  svg.appendChild(el("line", {x1: plot.x, y1: y(record.vbm.energy), x2: plot.x + plot.w, y2: y(record.vbm.energy), class: "guide"}));
  svg.appendChild(el("line", {x1: plot.x, y1: y(record.cbm.energy), x2: plot.x + plot.w, y2: y(record.cbm.energy), class: "guide"}));
  svg.appendChild(el("line", {x1: plot.x, y1: y(record.vGamma.energy), x2: plot.x + plot.w, y2: y(record.vGamma.energy), class: "guide"}));

  record.bandOrder.forEach(band => {
    const xs = kVals.map(x);
    const ys = record.bands[band].map(y);
    svg.appendChild(el("path", {
      d: pathFromXY(xs, ys),
      class: "bandLine",
      stroke: payload.bandColors[band] || "#555",
    }));
  });

  const vX = x(record.vbm.k), vY = y(record.vbm.energy);
  const cX = x(record.cbm.k), cY = y(record.cbm.energy);
  const gammaX = x(0.0);
  const vGammaY = y(record.vGamma.energy);
  const cGammaY = y(record.cGamma.energy);
  const cap = 8;
  svg.appendChild(el("circle", {class: "markerVbm", cx: vX, cy: vY, r: 8}));
  svg.appendChild(el("circle", {class: "markerCbm", cx: cX, cy: cY, r: 8}));
  svg.appendChild(el("text", {x: vX + 12, y: vY + 4, "font-size": 13, "font-weight": 800}, "VBM"));
  svg.appendChild(el("text", {x: cX + 12, y: cY + 4, "font-size": 13, "font-weight": 800}, "CBM"));

  const gapX = Math.min(plot.x + plot.w - 92, Math.max(plot.x + 92, x(0.0) + 84));
  svg.appendChild(el("line", {class: "gapLine", x1: gapX, y1: cY, x2: gapX, y2: vY}));
  svg.appendChild(el("line", {class: "bracketCap", x1: gapX - cap, y1: cY, x2: gapX + cap, y2: cY, stroke: "#111"}));
  svg.appendChild(el("line", {class: "bracketCap", x1: gapX - cap, y1: vY, x2: gapX + cap, y2: vY, stroke: "#111"}));
  svg.appendChild(el("text", {
    x: gapX + 14,
    y: (cY + vY) / 2 + 4,
    "font-size": 16,
    "font-weight": 900,
  }, `${fmt(record.gap, 1)} meV`));

  const gammaGapX = plot.x + plot.w - 34;
  svg.appendChild(el("line", {class: "gammaGapLine", x1: gammaGapX, y1: cGammaY, x2: gammaGapX, y2: vGammaY}));
  svg.appendChild(el("line", {class: "bracketCap", x1: gammaGapX - cap, y1: cGammaY, x2: gammaGapX + cap, y2: cGammaY, stroke: "#5f2385"}));
  svg.appendChild(el("line", {class: "bracketCap", x1: gammaGapX - cap, y1: vGammaY, x2: gammaGapX + cap, y2: vGammaY, stroke: "#5f2385"}));
  const gammaLabel = el("text", {
    x: gammaGapX - 12,
    y: (cGammaY + vGammaY) / 2 - 6,
    "font-size": 13,
    "font-weight": 850,
    "text-anchor": "end",
    fill: "#5f2385",
  });
  gammaLabel.appendChild(el("tspan", {x: gammaGapX - 12, dy: 0}, "Gamma"));
  gammaLabel.appendChild(el("tspan", {x: gammaGapX - 12, dy: 16}, `${fmt(record.gammaGap, 1)} meV`));
  svg.appendChild(gammaLabel);

  const camelX = plot.x + 38;
  svg.appendChild(el("line", {class: "camelLine", x1: camelX, y1: vY, x2: camelX, y2: vGammaY}));
  svg.appendChild(el("line", {class: "bracketCap", x1: camelX - cap, y1: vY, x2: camelX + cap, y2: vY, stroke: "#b8860b"}));
  svg.appendChild(el("line", {class: "bracketCap", x1: camelX - cap, y1: vGammaY, x2: camelX + cap, y2: vGammaY, stroke: "#b8860b"}));
  const camelLabel = el("text", {
    x: camelX + 14,
    y: Math.min(vY, vGammaY) - 18,
    "font-size": 13,
    "font-weight": 850,
    fill: "#8b6508",
  });
  camelLabel.appendChild(el("tspan", {x: plot.x + 14, dy: 0}, "camel-back"));
  camelLabel.appendChild(el("tspan", {x: plot.x + 14, dy: 16}, `gap ${fmt(record.camelbackDepth, 1)} meV`));
  svg.appendChild(camelLabel);

  svg.appendChild(el("text", {x: plot.x, y: 24, "font-size": 15, "font-weight": 800}, record.file));
}

function row(label, value) {
  return `<div class="row"><div class="label">${label}</div><div class="value">${value}</div></div>`;
}

function updateDetails(record) {
  document.getElementById("bandTitle").textContent = `Selected E-k calculation: ${record.geometry}`;
  document.getElementById("extremaTable").innerHTML = [
    row("Metric window", `|k| <= ${record.metricWindow} 1/A`),
    row("VBM band", record.vbm.band),
    row("VBM k", `${fmtK(record.vbm.k)} 1/A`),
    row("VBM energy", `${fmt(record.vbm.energy, 4)} meV`),
    row("CBM band", record.cbm.band),
    row("CBM k", `${fmtK(record.cbm.k)} 1/A`),
    row("CBM energy", `${fmt(record.cbm.energy, 4)} meV`),
  ].join("");

  document.getElementById("calcTable").innerHTML = [
    row("File", record.file),
    row("d1 / d2 / d1", record.geometry),
    row("Indirect gap", `${fmt(record.gap, 4)} meV`),
    row("Gamma gap", `${fmt(record.gammaGap, 4)} meV`),
    row("Camelback depth", `${fmt(record.camelbackDepth, 4)} meV`),
    row("Midgap", `${fmt(record.midgap, 4)} meV`),
  ].join("");

  document.getElementById("formula").textContent =
    `Egap = CBM - VBM = ${fmt(record.cbm.energy, 4)} - ${fmt(record.vbm.energy, 4)} = ${fmt(record.gap, 4)} meV`;
}

function selectRecord(index) {
  selectedIndex = index;
  const record = payload.records[index];
  drawSweep();
  drawBandLegend(record);
  drawBandPlot(record);
  updateDetails(record);
}

document.getElementById("title").textContent = payload.title;
selectRecord(0);
</script>
</body>
</html>
"""


def main() -> None:
    args = parse_args()
    records = load_records(args.directory, args.metric_window, args.band_window)
    html = build_html(records, args.title)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()
