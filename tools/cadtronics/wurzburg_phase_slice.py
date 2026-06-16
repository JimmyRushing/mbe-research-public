#!/usr/bin/env python3
"""
Build phase-diagram-style outputs for the Schmid/Würzburg Fig. 3(a)
validation sweep.

This intentionally mirrors the earlier phase-map workflow, but the data are a
single d2 = 5 nm horizontal slice. Outputs:

  - static PNG summary
  - standalone interactive HTML where clicking a point shows the E-k extraction
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.colors import TwoSlopeNorm
from matplotlib.lines import Line2D
import pandas as pd


FILENAME_RE = re.compile(
    r"^(?P<d1>[0-9.]+)\s+(?P<d2>[0-9.]+)\s+(?P=d1)(?:\s+.*)?\.dat$",
    re.IGNORECASE,
)

BAND_ORDER = ["V0002", "V0001", "C0001", "C0002"]
BAND_COLORS = {
    "V0002": "#8B0000",
    "V0001": "#B8860B",
    "C0001": "#0000FF",
    "C0002": "#87CEFA",
}
BAND_LABELS = {
    "V0002": "Valence band 2",
    "V0001": "Valence band 1",
    "C0001": "Conduction band 1",
    "C0002": "Conduction band 2",
}
CAMELBACK_THRESHOLD_MEV = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Make Wurzburg validation phase-slice outputs.")
    parser.add_argument("directory", type=Path)
    parser.add_argument("--png", type=Path, required=True)
    parser.add_argument("--html", type=Path, required=True)
    parser.add_argument("--csv", type=Path, default=None)
    parser.add_argument("--metric-window", type=float, default=0.05)
    parser.add_argument("--band-window", type=float, default=0.05)
    parser.add_argument("--color-limit", type=float, default=45.0)
    parser.add_argument("--title", default="Cadtronics phase-slice validation: d2 = 5 nm")
    parser.add_argument("--no-show", action="store_true")
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
        elif mode == "max" and info["energy"] > best["energy"]:
            best = info
        elif mode == "min" and info["energy"] < best["energy"]:
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

    required = {"V0001", "V0002", "C0001", "C0002"}
    if not required.issubset(df.columns):
        missing = ", ".join(sorted(required.difference(df.columns)))
        raise ValueError(f"{path.name} is missing {missing}")

    vbm = extremum_info(df, k, metric_mask, ["V0001", "V0002"], "max")
    cbm = extremum_info(df, k, metric_mask, ["C0001", "C0002"], "min")
    gamma_idx = int(k.abs().idxmin())
    v_gamma_candidates = [{"band": band, "energy": float(df.loc[gamma_idx, band])} for band in ("V0001", "V0002")]
    c_gamma_candidates = [{"band": band, "energy": float(df.loc[gamma_idx, band])} for band in ("C0001", "C0002")]
    v_gamma = max(v_gamma_candidates, key=lambda item: item["energy"])
    c_gamma = min(c_gamma_candidates, key=lambda item: item["energy"])

    gap = round(cbm["energy"] - vbm["energy"], 4)
    camelback_depth = round(vbm["energy"] - float(v_gamma["energy"]), 4)
    bands = {"K": round_list(k.loc[band_mask])}
    for band in BAND_ORDER:
        bands[band] = round_list(df.loc[band_mask, band])

    plot_values = df.loc[band_mask, BAND_ORDER].astype(float)
    y_min = float(plot_values.min().min())
    y_max = float(plot_values.max().max())
    y_pad = max(5.0, 0.08 * (y_max - y_min))

    return {
        "file": path.name,
        "d1": d1,
        "d2": d2,
        "orientation": "001",
        "geometry": f"{d1:g} / {d2:g} / {d1:g}",
        "metricWindow": metric_window,
        "bandWindow": band_window,
        "vbm": vbm,
        "cbm": cbm,
        "gap": gap,
        "midgap": round(0.5 * (cbm["energy"] + vbm["energy"]), 4),
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
        "camelbackDepth": camelback_depth,
        "camelback": camelback_depth > 1.0,
        "phaseValue": gap if camelback_depth > 1.0 else 0.0,
        "bands": bands,
        "bandOrder": BAND_ORDER,
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
        raise SystemExit(f"No matching symmetric sweep files found in {directory}")
    return sorted(records, key=lambda item: (item["d2"], item["d1"]))


def interpolate_transition(records: list[dict], key: str, level: float, direction: str) -> float | None:
    ordered = sorted(records, key=lambda item: item["d1"])
    for left, right in zip(ordered, ordered[1:]):
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


def write_csv(records: list[dict], csv_path: Path) -> None:
    rows = []
    for record in records:
        rows.append(
            {
                "d1_nm": record["d1"],
                "d2_nm": record["d2"],
                "gap_mev": record["gap"],
                "phase_value_mev": record["phaseValue"],
                "camelback_depth_mev": record["camelbackDepth"],
                "vbm_mev": record["vbm"]["energy"],
                "vbm_band": record["vbm"]["band"],
                "vbm_k": record["vbm"]["k"],
                "cbm_mev": record["cbm"]["energy"],
                "cbm_band": record["cbm"]["band"],
                "cbm_k": record["cbm"]["k"],
                "file": record["file"],
            }
        )
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(csv_path, index=False)


def plot_static(records: list[dict], out: Path, title: str, color_limit: float) -> None:
    df = pd.DataFrame(
        {
            "d1": [r["d1"] for r in records],
            "d2": [r["d2"] for r in records],
            "gap": [r["gap"] for r in records],
            "phaseValue": [r["phaseValue"] for r in records],
            "camelback": [r["camelback"] for r in records],
        }
    )
    cmap = plt.get_cmap("coolwarm_r")
    norm = TwoSlopeNorm(vmin=-color_limit, vcenter=0.0, vmax=color_limit)

    fig, ax = plt.subplots(figsize=(12.5, 4.8))
    fig.suptitle(title, fontsize=22, y=0.98)

    d2_min = float(df["d2"].min())
    d2_max = float(df["d2"].max())
    y_pad = 0.65 if d2_min == d2_max else 0.7
    x_pad = 0.45

    transitions = data_transitions(records)
    t1 = transitions["trivialToTi"] if transitions["trivialToTi"] is not None else float(df["d1"].min()) - x_pad
    t2 = transitions["tiToSm"] if transitions["tiToSm"] is not None else float(df["d1"].max()) + x_pad
    x_min = float(df["d1"].min()) - x_pad
    x_max = float(df["d1"].max()) + x_pad

    if t1 > x_min:
        ax.axvspan(x_min, t1, color="0.90", zorder=0)
    if t2 > t1:
        ax.axvspan(t1, t2, color="0.76", zorder=0)
    if x_max > t2:
        ax.axvspan(t2, x_max, color="1.0", zorder=0)
    if transitions["trivialToTi"] is not None:
        ax.axvline(t1, color="0.35", linestyle="--", linewidth=1.3, zorder=1)
        ax.text(t1, d2_max + y_pad - 0.12, f"data\n{t1:.2f}", ha="center", va="top", fontsize=10, color="0.25")
    if transitions["tiToSm"] is not None:
        ax.axvline(t2, color="0.35", linestyle="--", linewidth=1.3, zorder=1)
        ax.text(t2, d2_max + y_pad - 0.12, f"data\n{t2:.2f}", ha="center", va="top", fontsize=10, color="0.25")

    ax.plot(df["d1"], df["d2"], color="0.35", linewidth=1.1, zorder=1)
    for index, row in df.reset_index(drop=True).iterrows():
        color = cmap(norm(float(row["phaseValue"])))
        face = color if bool(row["camelback"]) else "white"
        edge = "black" if bool(row["camelback"]) else "0.45"
        ax.scatter(row["d1"], row["d2"], s=430, facecolors=face, edgecolors=edge, linewidths=2.2, zorder=3)
        label_offset = 0.17 if index % 2 == 0 else -0.25
        ax.text(
            row["d1"],
            row["d2"] + label_offset,
            f"{row['gap']:.1f}",
            ha="center",
            va="bottom" if label_offset > 0 else "top",
            fontsize=10,
            zorder=4,
        )

    if t1 > x_min:
        ax.text((x_min + t1) / 2, d2_max + y_pad - 0.35, "trivial", ha="center", va="top", fontsize=13, fontweight="bold")
    if t2 > t1:
        ax.text((t1 + t2) / 2, d2_max + y_pad - 0.35, "TI", ha="center", va="top", fontsize=13, fontweight="bold")
    if x_max > t2:
        ax.text((t2 + x_max) / 2, d2_max + y_pad - 0.35, "SM", ha="center", va="top", fontsize=13, fontweight="bold")

    ax.set_xlabel("InAs thickness d1 (nm)", fontsize=14)
    ax.set_ylabel("GaSb thickness d2 (nm)", fontsize=14)
    ax.set_xlim(float(df["d1"].min()) - x_pad, float(df["d1"].max()) + x_pad)
    ax.set_ylim(d2_min - y_pad, d2_max + y_pad)
    ax.set_yticks(sorted(df["d2"].unique()))
    ax.grid(True, color="0.88", linewidth=0.8, zorder=0)

    handles = [
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="black", markeredgecolor="black", markersize=10, label="camel-back"),
        Line2D([0], [0], marker="o", linestyle="none", markerfacecolor="white", markeredgecolor="black", markersize=10, label="no camel-back"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=True, fontsize=11, title="Valence shape")
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, pad=0.018, fraction=0.04)
    cbar.set_label("Phase color (meV)\nwhite = no camel-back\nnegative = semimetal", fontsize=11)

    fig.tight_layout(rect=[0.02, 0.16, 1.0, 0.93])
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(out)


def build_html(records: list[dict], title: str, color_limit: float) -> str:
    payload = {
        "title": title,
        "colorLimit": color_limit,
        "bandColors": BAND_COLORS,
        "bandLabels": BAND_LABELS,
        "records": records,
        "dataTransitions": data_transitions(records),
    }
    return HTML_TEMPLATE.replace("__PAYLOAD__", json.dumps(payload, separators=(",", ":")))


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Cadtronics phase-slice explorer</title>
  <style>
    :root {
      --bg: #f4f2ec;
      --panel: #fff;
      --ink: #171717;
      --muted: #676767;
      --grid: #dedede;
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
      justify-content: space-between;
      align-items: flex-end;
      gap: 18px;
    }
    h1 {
      margin: 0;
      font-size: 28px;
      line-height: 1.05;
      letter-spacing: -0.03em;
    }
    .note {
      max-width: 680px;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.35;
      text-align: right;
    }
    .grid {
      display: grid;
      grid-template-columns: minmax(430px, 0.95fr) minmax(560px, 1.25fr);
      gap: 14px;
      min-height: 0;
    }
    .panel {
      background: var(--panel);
      border: 1px solid #d6d2c6;
      border-radius: 16px;
      box-shadow: 0 10px 30px rgba(30,25,10,.08);
      padding: 14px;
      min-width: 0;
      overflow: hidden;
    }
    .panelTitle {
      margin: 0 0 8px;
      font-size: 16px;
      font-weight: 850;
      letter-spacing: -.01em;
    }
    svg { display: block; width: 100%; height: auto; }
    .axis text { fill: var(--ink); font-size: 13px; }
    .axis line, .axis path { stroke: var(--ink); stroke-width: 1.4; shape-rendering: crispEdges; }
    .gridLine { stroke: var(--grid); stroke-width: 1; shape-rendering: crispEdges; }
    .region { opacity: .72; }
    .regionLabel { fill: #333; font-size: 15px; font-weight: 850; }
    .point { cursor: pointer; }
    .point:hover { filter: drop-shadow(0 0 4px rgba(0,0,0,.25)); }
    .selectedPoint { stroke: #000; stroke-width: 3.8; fill: var(--selected); }
    .bandLine { fill: none; stroke-width: 3; stroke-linejoin: round; stroke-linecap: round; }
    .guide { stroke: #333; stroke-width: 1.5; stroke-dasharray: 5 5; opacity: .82; }
    .gapLine { stroke: #111; stroke-width: 2; marker-start: url(#arrow); marker-end: url(#arrow); }
    .markerVbm { fill: #ffcf33; stroke: #111; stroke-width: 2.2; }
    .markerCbm { fill: #5bc0ff; stroke: #111; stroke-width: 2.2; }
    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 10px 14px;
      align-items: center;
      font-size: 13px;
      margin: 6px 0 2px;
    }
    .legendItem { display: inline-flex; align-items: center; gap: 6px; white-space: nowrap; }
    .swatch { width: 22px; height: 0; border-top: 3px solid currentColor; }
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
      letter-spacing: .08em;
      color: #444;
    }
    .row {
      display: grid;
      grid-template-columns: 1.15fr 1fr;
      gap: 8px;
      border-top: 1px solid #e7e2d7;
      padding: 5px 0;
    }
    .row:first-of-type { border-top: 0; }
    .label { color: var(--muted); }
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
    <div class="note">This is the Fig. 3(a) sweep shown as a phase-diagram slice. Click each point to inspect the E-k bands and the exact VBM/CBM arithmetic.</div>
  </header>
  <main class="grid">
    <section class="panel">
      <h2 class="panelTitle">Phase-slice map</h2>
      <svg id="phaseSvg" viewBox="0 0 760 520" role="img"></svg>
    </section>
    <section class="panel">
      <h2 class="panelTitle" id="bandTitle">Selected E-k calculation</h2>
      <div class="legend" id="bandLegend"></div>
      <svg id="bandSvg" viewBox="0 0 760 760" role="img"></svg>
      <div class="details">
        <div class="card"><h3>Extrema used</h3><div id="extremaTable"></div></div>
        <div class="card"><h3>Calculation</h3><div id="calcTable"></div><div class="formula" id="formula"></div></div>
      </div>
    </section>
  </main>
</div>
<script>
const payload = __PAYLOAD__;
let selectedIndex = 0;
const ns = "http://www.w3.org/2000/svg";
const fmt = (value, digits = 1) => Number(value).toFixed(digits);
const fmtK = value => Number(value).toFixed(4);

function el(name, attrs = {}, text = "") {
  const node = document.createElementNS(ns, name);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  if (text !== "") node.textContent = text;
  return node;
}
function clear(node) { while (node.firstChild) node.removeChild(node.firstChild); }
function scaleLinear(domain, range) {
  const [d0, d1] = domain, [r0, r1] = range;
  return value => r0 + (value - d0) * (r1 - r0) / (d1 - d0);
}
function niceTicks(min, max, count = 6) {
  const span = max - min;
  const rough = span / Math.max(1, count - 1);
  const power = Math.pow(10, Math.floor(Math.log10(Math.abs(rough))));
  const norm = rough / power;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * power;
  const start = Math.ceil(min / step) * step;
  const ticks = [];
  for (let value = start; value <= max + step * 0.5; value += step) ticks.push(Number(value.toFixed(10)));
  return ticks;
}
function colorFor(value) {
  const limit = payload.colorLimit;
  const v = Math.max(-limit, Math.min(limit, value));
  if (v === 0) return "#ffffff";
  const t = (v + limit) / (2 * limit);
  if (t < 0.5) {
    const q = t / 0.5;
    return `rgb(${Math.round(59 + q * 196)},${Math.round(76 + q * 179)},${Math.round(192 + q * 63)})`;
  }
  const q = (t - 0.5) / 0.5;
  return `rgb(${Math.round(255 - q * 75)},${Math.round(255 - q * 251)},${Math.round(255 - q * 217)})`;
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
    g.appendChild(el("text", {x, y: plot.y + plot.h + 25, "text-anchor": "middle"}, fmt(tick, Number.isInteger(tick) ? 0 : 1)));
  }
  for (const tick of yTicks) {
    const y = yScale(tick);
    svg.appendChild(el("line", {class: "gridLine", x1: plot.x, y1: y, x2: plot.x + plot.w, y2: y}));
    g.appendChild(el("line", {x1: plot.x - 7, y1: y, x2: plot.x, y2: y}));
    g.appendChild(el("text", {x: plot.x - 12, y: y + 4, "text-anchor": "end"}, fmt(tick, 1)));
  }
  g.appendChild(el("line", {x1: plot.x, y1: plot.y + plot.h, x2: plot.x + plot.w, y2: plot.y + plot.h}));
  g.appendChild(el("line", {x1: plot.x, y1: plot.y, x2: plot.x, y2: plot.y + plot.h}));
  g.appendChild(el("text", {x: plot.x + plot.w / 2, y: plot.y + plot.h + 55, "text-anchor": "middle"}, xLabel));
  g.appendChild(el("text", {x: plot.x - 64, y: plot.y + plot.h / 2, "text-anchor": "middle", transform: `rotate(-90 ${plot.x - 64} ${plot.y + plot.h / 2})`}, yLabel));
}
function drawPhase() {
  const svg = document.getElementById("phaseSvg");
  clear(svg);
  const records = payload.records;
  const plot = {x: 86, y: 48, w: 620, h: 360};
  const xMin = Math.min(...records.map(r => r.d1)) - 0.45;
  const xMax = Math.max(...records.map(r => r.d1)) + 0.45;
  const y0 = records[0].d2;
  const yMin = y0 - 0.65, yMax = y0 + 0.65;
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
    svg.appendChild(el("rect", {class: "region", x: x(t2), y: plot.y, width: x(xMax) - x(t2), height: plot.h, fill: "#fff"}));
  }
  drawAxes(svg, plot, x, y, niceTicks(xMin, xMax, 8), [y0], "InAs thickness d1 (nm)", "GaSb thickness d2 (nm)");
  if (transitions.trivialToTi !== null) {
    svg.appendChild(el("line", {x1: x(t1), y1: plot.y, x2: x(t1), y2: plot.y + plot.h, stroke: "#555", "stroke-width": 1.5, "stroke-dasharray": "6 5"}));
    svg.appendChild(el("text", {x: x(t1), y: plot.y + 22, "text-anchor": "middle", "font-size": 12, fill: "#444"}, `data ${fmt(t1, 2)}`));
  }
  if (transitions.tiToSm !== null) {
    svg.appendChild(el("line", {x1: x(t2), y1: plot.y, x2: x(t2), y2: plot.y + plot.h, stroke: "#555", "stroke-width": 1.5, "stroke-dasharray": "6 5"}));
    svg.appendChild(el("text", {x: x(t2), y: plot.y + 22, "text-anchor": "middle", "font-size": 12, fill: "#444"}, `data ${fmt(t2, 2)}`));
  }
  if (t1 > xMin) svg.appendChild(el("text", {class: "regionLabel", x: x((xMin + t1) / 2), y: plot.y + 48, "text-anchor": "middle"}, "trivial"));
  if (t2 > t1) svg.appendChild(el("text", {class: "regionLabel", x: x((t1 + t2) / 2), y: plot.y + 48, "text-anchor": "middle"}, "TI"));
  if (xMax > t2) svg.appendChild(el("text", {class: "regionLabel", x: x((t2 + xMax) / 2), y: plot.y + 48, "text-anchor": "middle"}, "SM"));
  svg.appendChild(el("line", {x1: x(xMin), y1: y(y0), x2: x(xMax), y2: y(y0), stroke: "#555", "stroke-width": 1.2}));
  records.forEach((r, i) => {
    const px = x(r.d1), py = y(r.d2);
    const point = el("circle", {
      class: `point ${i === selectedIndex ? "selectedPoint" : ""}`,
      cx: px,
      cy: py,
      r: i === selectedIndex ? 13 : 11,
      fill: i === selectedIndex ? "var(--selected)" : (r.camelback ? colorFor(r.phaseValue) : "#fff"),
      stroke: r.camelback ? "#111" : "#777",
      "stroke-width": i === selectedIndex ? 3.8 : 2.4,
    });
    point.addEventListener("click", () => selectRecord(i));
    svg.appendChild(point);
    svg.appendChild(el("text", {x: px, y: py - 18, "text-anchor": "middle", "font-size": 11}, fmt(r.gap, 1)));
  });
  svg.appendChild(el("text", {x: plot.x, y: 492, "font-size": 13}, "Interpolated from Cadtronics data: trivial at camel-back < 1 meV, TI for camel-back + positive gap, SM after gap crosses zero."));
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
}
function drawBand(record) {
  const svg = document.getElementById("bandSvg");
  clear(svg);
  const defs = el("defs");
  const marker = el("marker", {id: "arrow", viewBox: "0 0 10 10", refX: 5, refY: 5, markerWidth: 5, markerHeight: 5, orient: "auto-start-reverse"});
  marker.appendChild(el("path", {d: "M 0 0 L 10 5 L 0 10 z", fill: "#111"}));
  defs.appendChild(marker);
  svg.appendChild(defs);
  const plot = {x: 102, y: 44, w: 500, h: 610};
  const kVals = record.bands.K;
  const xMin = Math.min(...kVals), xMax = Math.max(...kVals);
  const x = scaleLinear([xMin, xMax], [plot.x, plot.x + plot.w]);
  const y = scaleLinear([record.yMin, record.yMax], [plot.y + plot.h, plot.y]);
  drawAxes(svg, plot, x, y, niceTicks(xMin, xMax, 7), niceTicks(record.yMin, record.yMax, 7), "k (1/A)", "Energy (meV)");
  svg.appendChild(el("line", {x1: plot.x, y1: y(record.vbm.energy), x2: plot.x + plot.w, y2: y(record.vbm.energy), class: "guide"}));
  svg.appendChild(el("line", {x1: plot.x, y1: y(record.cbm.energy), x2: plot.x + plot.w, y2: y(record.cbm.energy), class: "guide"}));
  record.bandOrder.forEach(band => {
    svg.appendChild(el("path", {d: pathFromXY(kVals.map(x), record.bands[band].map(y)), class: "bandLine", stroke: payload.bandColors[band] || "#555"}));
  });
  const vX = x(record.vbm.k), vY = y(record.vbm.energy), cX = x(record.cbm.k), cY = y(record.cbm.energy);
  svg.appendChild(el("circle", {class: "markerVbm", cx: vX, cy: vY, r: 8}));
  svg.appendChild(el("circle", {class: "markerCbm", cx: cX, cy: cY, r: 8}));
  svg.appendChild(el("text", {x: vX + 12, y: vY + 4, "font-size": 13, "font-weight": 800}, "VBM"));
  svg.appendChild(el("text", {x: cX + 12, y: cY + 4, "font-size": 13, "font-weight": 800}, "CBM"));
  const gapX = Math.min(plot.x + plot.w - 78, Math.max(plot.x + 78, x(0) + 42));
  svg.appendChild(el("line", {class: "gapLine", x1: gapX, y1: cY, x2: gapX, y2: vY}));
  svg.appendChild(el("text", {x: gapX + 14, y: (cY + vY) / 2 + 4, "font-size": 16, "font-weight": 900}, `${fmt(record.gap, 1)} meV`));
  svg.appendChild(el("text", {x: plot.x, y: 24, "font-size": 15, "font-weight": 850}, record.file));
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
    row("Phase-map value", `${fmt(record.phaseValue, 4)} meV`),
  ].join("");
  document.getElementById("formula").textContent = `Egap = CBM - VBM = ${fmt(record.cbm.energy, 4)} - ${fmt(record.vbm.energy, 4)} = ${fmt(record.gap, 4)} meV`;
}
function selectRecord(index) {
  selectedIndex = index;
  const record = payload.records[index];
  drawPhase();
  drawBandLegend(record);
  drawBand(record);
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
    plot_static(records, args.png, args.title, args.color_limit)
    html = build_html(records, args.title, args.color_limit)
    args.html.parent.mkdir(parents=True, exist_ok=True)
    args.html.write_text(html, encoding="utf-8")
    print(args.html)
    if args.csv is not None:
        write_csv(records, args.csv)
        print(args.csv)
    if not args.no_show:
        plt.show()


if __name__ == "__main__":
    main()
