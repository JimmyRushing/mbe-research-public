#!/usr/bin/env python3
"""
Build a standalone interactive double-mounted MBE RHEED zone-axis finder.

The generated HTML models cubic samples on an MBE manipulator and lets the
user adjust manipulator rotation, deflX, and deflY while seeing nearby in-plane
RHEED reflection/zone-axis candidates for double-mounted (001) and (111) samples.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


SAMPLES = {
    "001": {
        "label": "(001)",
        "normal": [0, 0, 1],
        "zero": [1, 1, 0],
        "zeroLabel": "[110]",
        "color": "#0f766e",
        "accent": "#14b8a6",
    },
    "111": {
        "label": "(111)",
        "normal": [1, 1, 1],
        "zero": [1, -1, 0],
        "zeroLabel": "[1 -1 0]",
        "color": "#b45309",
        "accent": "#f59e0b",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a standalone HTML double-mounted MBE RHEED zone-axis finder for (001)/(111) mounts."
    )
    parser.add_argument("--out", type=Path, default=Path("analysis/double_mounted_rheed_zone_axis_finder.html"))
    parser.add_argument("--title", default="Double-mounted MBE RHEED zone-axis finder")
    parser.add_argument("--rotation", type=float, default=0.0, help="Initial manipulator rotation in degrees.")
    parser.add_argument("--deflx", type=float, default=0.0, help="Initial deflX value in instrument units.")
    parser.add_argument("--defly", type=float, default=0.0, help="Initial deflY value in instrument units.")
    parser.add_argument(
        "--deflx-scale",
        type=float,
        default=0.10,
        help="Azimuth correction in degrees per deflX unit.",
    )
    parser.add_argument(
        "--defly-scale",
        type=float,
        default=0.05,
        help="Incidence correction in degrees per deflY unit.",
    )
    parser.add_argument("--base-incidence", type=float, default=1.5, help="Initial grazing incidence in degrees.")
    parser.add_argument("--target-incidence", type=float, default=1.5, help="Desired grazing incidence in degrees.")
    parser.add_argument("--offset-001", type=float, default=0.0, help="Stage rotation offset for the (001) sample.")
    parser.add_argument("--offset-111", type=float, default=0.0, help="Stage rotation offset for the (111) sample.")
    parser.add_argument("--max-index", type=int, default=3, choices=range(1, 7), metavar="N")
    parser.add_argument("--self-test", action="store_true", help="Run crystallographic sanity checks and exit.")
    return parser.parse_args()


def gcd3(values: list[int]) -> int:
    result = 0
    for value in values:
        result = math.gcd(result, abs(value))
    return result


def canonical_line(vector: tuple[int, int, int]) -> tuple[int, int, int]:
    values = list(vector)
    divisor = gcd3(values)
    if divisor:
        values = [value // divisor for value in values]
    for value in values:
        if value != 0:
            if value < 0:
                values = [-item for item in values]
            break
    return tuple(values)


def surface_axes(normal: list[int], max_index: int) -> set[tuple[int, int, int]]:
    axes: set[tuple[int, int, int]] = set()
    for h in range(-max_index, max_index + 1):
        for k in range(-max_index, max_index + 1):
            for l in range(-max_index, max_index + 1):
                if h == k == l == 0:
                    continue
                if gcd3([h, k, l]) != 1:
                    continue
                if h * normal[0] + k * normal[1] + l * normal[2] != 0:
                    continue
                axes.add(canonical_line((h, k, l)))
    return axes


def run_self_test() -> None:
    axes_001 = surface_axes(SAMPLES["001"]["normal"], 2)
    axes_111 = surface_axes(SAMPLES["111"]["normal"], 2)
    assert (1, 1, 0) in axes_001
    assert (1, -1, 0) in axes_111
    assert (1, 0, -1) in axes_111
    assert (0, 1, -1) in axes_111
    assert all(axis[2] == 0 for axis in axes_001)
    assert all(sum(axis) == 0 for axis in axes_111)
    html = build_html(
        {
            "title": "test",
            "defaults": {
                "rotation": 0.0,
                "deflx": 0.0,
                "defly": 0.0,
                "deflxScale": 0.1,
                "deflyScale": 0.05,
                "baseIncidence": 1.5,
                "targetIncidence": 1.5,
                "offset001": 0.0,
                "offset111": 0.0,
                "maxIndex": 3,
            },
            "samples": SAMPLES,
        }
    )
    assert "__PAYLOAD__" not in html
    assert "Double-mounted MBE RHEED zone-axis finder" in html
    print("Self-test passed: (001)/(111) in-plane axis generation and HTML payload look sane.")


def build_payload(args: argparse.Namespace) -> dict:
    return {
        "title": args.title,
        "defaults": {
            "rotation": args.rotation,
            "deflx": args.deflx,
            "defly": args.defly,
            "deflxScale": args.deflx_scale,
            "deflyScale": args.defly_scale,
            "baseIncidence": args.base_incidence,
            "targetIncidence": args.target_incidence,
            "offset001": args.offset_001,
            "offset111": args.offset_111,
            "maxIndex": args.max_index,
        },
        "samples": SAMPLES,
    }


def build_html(payload: dict) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"))
    return HTML_TEMPLATE.replace("__PAYLOAD__", payload_json)


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return

    html = build_html(build_payload(args))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")
    print(f"Wrote {args.out}")


HTML_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Double-mounted MBE RHEED zone-axis finder</title>
  <style>
    :root {
      --ink: #17201f;
      --muted: #60706d;
      --line: #cdd8d4;
      --soft: #eef4f1;
      --surface: #fbfcfb;
      --paper: #ffffff;
      --focus: #0f766e;
      --warn: #b45309;
      --bad: #a53b3b;
      --good: #177245;
      --shadow: 0 10px 30px rgba(24, 39, 35, 0.08);
    }

    * {
      box-sizing: border-box;
    }

    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      background: #f4f7f5;
      font-family: "Aptos", "Segoe UI", Arial, sans-serif;
    }

    .app {
      min-height: 100vh;
      display: grid;
      grid-template-rows: auto auto 1fr;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 18px;
      padding: 18px 22px 12px;
      border-bottom: 1px solid var(--line);
      background: var(--paper);
    }

    h1 {
      margin: 0;
      font-size: clamp(22px, 3vw, 34px);
      font-weight: 760;
      letter-spacing: 0;
    }

    .subtitle {
      margin-top: 4px;
      color: var(--muted);
      font-size: 14px;
    }

    .description-panel {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(250px, 0.55fr);
      gap: 18px;
      align-items: center;
      margin: 14px 16px 0;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
      box-shadow: var(--shadow);
    }

    .description-panel h2 {
      margin: 0 0 7px;
      font-size: 19px;
      letter-spacing: 0;
    }

    .description-panel p {
      margin: 0;
      max-width: 920px;
      color: #344340;
      font-size: 16px;
      line-height: 1.58;
    }

    .description-panel p + p {
      margin-top: 7px;
    }

    .mount-figure {
      display: grid;
      justify-items: center;
      gap: 7px;
      margin: 0;
    }

    .mount-figure img {
      display: block;
      width: min(100%, 230px);
      height: auto;
      border-radius: 8px;
      box-shadow: 0 10px 24px rgba(23, 32, 31, 0.14);
    }

    .mount-figure figcaption {
      color: var(--muted);
      font-size: 12px;
      font-weight: 650;
      text-align: center;
    }

    .header-metrics {
      display: flex;
      flex-wrap: wrap;
      justify-content: flex-end;
      gap: 8px;
    }

    .metric {
      min-width: 110px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
    }

    .metric span {
      display: block;
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }

    .metric strong {
      display: block;
      margin-top: 2px;
      font-size: 16px;
    }

    main {
      display: grid;
      grid-template-columns: minmax(285px, 350px) minmax(0, 1fr);
      gap: 16px;
      padding: 16px;
    }

    aside,
    .workspace {
      min-width: 0;
    }

    aside {
      display: grid;
      align-content: start;
      gap: 12px;
    }

    .panel {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--paper);
      box-shadow: var(--shadow);
    }

    .panel h2 {
      margin: 0;
      padding: 12px 14px 8px;
      font-size: 14px;
      font-weight: 760;
      letter-spacing: 0;
      border-bottom: 1px solid var(--line);
    }

    .control-grid {
      display: grid;
      gap: 12px;
      padding: 13px;
    }

    .control {
      display: grid;
      gap: 6px;
    }

    .control label,
    .check-row label {
      color: #273533;
      font-size: 13px;
      font-weight: 650;
    }

    .paired {
      display: grid;
      grid-template-columns: 1fr 82px;
      gap: 8px;
      align-items: center;
    }

    input,
    select,
    button {
      font: inherit;
    }

    input[type="number"],
    select {
      width: 100%;
      min-height: 34px;
      padding: 6px 8px;
      border: 1px solid #b8c5c1;
      border-radius: 6px;
      background: #fff;
      color: var(--ink);
    }

    input[type="range"] {
      width: 100%;
      accent-color: var(--focus);
    }

    .two-col {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 10px;
    }

    .checks {
      display: grid;
      gap: 9px;
    }

    .check-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 10px;
      min-height: 34px;
      padding: 7px 9px;
      border: 1px solid var(--line);
      border-radius: 7px;
      background: var(--surface);
    }

    .check-row input {
      width: 18px;
      height: 18px;
      accent-color: var(--focus);
    }

    .button-row {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 8px;
      padding: 0 13px 13px;
    }

    button {
      min-height: 36px;
      border: 1px solid #95aaa4;
      border-radius: 6px;
      background: #f9fbfa;
      color: var(--ink);
      font-weight: 700;
      cursor: pointer;
    }

    button:hover,
    button:focus-visible {
      border-color: var(--focus);
      outline: none;
    }

    .workspace {
      display: grid;
      grid-template-rows: minmax(360px, 54vh) auto;
      gap: 16px;
    }

    .visual {
      display: grid;
      grid-template-columns: minmax(300px, 0.95fr) minmax(260px, 0.65fr);
      min-height: 0;
      overflow: hidden;
    }

    .compass-wrap {
      position: relative;
      min-height: 360px;
      border-right: 1px solid var(--line);
      background:
        linear-gradient(90deg, rgba(15, 118, 110, 0.06), transparent 48%),
        linear-gradient(0deg, rgba(180, 83, 9, 0.05), transparent 42%),
        #fcfdfc;
    }

    canvas {
      display: block;
      width: 100%;
      height: 100%;
    }

    .readout {
      position: absolute;
      left: 14px;
      bottom: 14px;
      display: grid;
      gap: 5px;
      max-width: calc(100% - 28px);
      padding: 9px 10px;
      border: 1px solid rgba(23, 32, 31, 0.16);
      border-radius: 8px;
      background: rgba(255, 255, 255, 0.9);
      backdrop-filter: blur(6px);
      font-size: 13px;
    }

    .legend {
      display: flex;
      flex-wrap: wrap;
      gap: 9px 12px;
      color: var(--muted);
    }

    .legend b {
      display: inline-block;
      width: 10px;
      height: 10px;
      margin-right: 5px;
      border-radius: 999px;
      vertical-align: -1px;
    }

    .detail-stack {
      display: grid;
      grid-template-rows: auto 1fr;
      min-height: 0;
    }

    .selected-axis {
      padding: 14px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
    }

    .selected-axis h2 {
      padding: 0;
      border: 0;
      font-size: 16px;
    }

    .selected-axis .axis-big {
      margin-top: 10px;
      font-size: clamp(34px, 6vw, 56px);
      font-weight: 800;
      line-height: 0.95;
      letter-spacing: 0;
    }

    .selected-axis .axis-meta {
      margin-top: 8px;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.45;
    }

    .nearest-list {
      min-height: 0;
      overflow: auto;
      padding: 10px;
      background: #fbfcfb;
    }

    .mini-card {
      display: grid;
      grid-template-columns: auto 1fr auto;
      gap: 9px;
      align-items: center;
      padding: 9px;
      margin-bottom: 8px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .mini-card .swatch {
      width: 4px;
      height: 42px;
      border-radius: 4px;
    }

    .mini-card strong {
      display: block;
      font-size: 17px;
    }

    .mini-card span {
      display: block;
      margin-top: 2px;
      color: var(--muted);
      font-size: 12px;
    }

    .delta {
      min-width: 62px;
      text-align: right;
      font-weight: 800;
    }

    .tables {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 16px;
    }

    .table-panel {
      overflow: hidden;
    }

    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 13px;
    }

    th,
    td {
      padding: 9px 10px;
      text-align: right;
      border-bottom: 1px solid var(--line);
      white-space: nowrap;
    }

    th:first-child,
    td:first-child {
      text-align: left;
    }

    th {
      color: var(--muted);
      background: #f7faf8;
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.07em;
    }

    tr:last-child td {
      border-bottom: 0;
    }

    .axis-cell {
      font-weight: 800;
    }

    .pill {
      display: inline-block;
      min-width: 50px;
      padding: 3px 7px;
      border-radius: 999px;
      color: #fff;
      font-weight: 800;
      text-align: center;
    }

    .pill.good {
      background: var(--good);
    }

    .pill.ok {
      background: var(--warn);
    }

    .pill.bad {
      background: var(--bad);
    }

    .empty {
      padding: 16px;
      color: var(--muted);
      font-size: 13px;
    }

    @media (max-width: 980px) {
      header,
      main {
        padding-left: 12px;
        padding-right: 12px;
      }

      header {
        align-items: flex-start;
        flex-direction: column;
      }

      .header-metrics {
        justify-content: flex-start;
      }

      main,
      .visual,
      .tables {
        grid-template-columns: 1fr;
      }

      .description-panel {
        grid-template-columns: 1fr;
      }

      .workspace {
        grid-template-rows: auto auto;
      }

      .visual {
        min-height: auto;
      }

      .compass-wrap {
        min-height: 440px;
        border-right: 0;
        border-bottom: 1px solid var(--line);
      }
    }

    @media (max-width: 560px) {
      .two-col,
      .button-row,
      .paired {
        grid-template-columns: 1fr;
      }

      .metric {
        min-width: calc(50% - 4px);
      }

      .description-panel {
        margin: 12px 12px 0;
        padding: 12px;
      }

      th,
      td {
        padding-left: 7px;
        padding-right: 7px;
        font-size: 12px;
      }
    }
  </style>
</head>
<body>
  <div class="app">
    <header>
      <div>
        <h1 id="title">Double-mounted MBE RHEED zone-axis finder</h1>
        <div class="subtitle">Cubic dual-mount azimuth map with editable beam-steering calibration.</div>
      </div>
      <div class="header-metrics" aria-live="polite">
        <div class="metric"><span>Rotation</span><strong id="rotationMetric">0.0 deg</strong></div>
        <div class="metric"><span>Az trim</span><strong id="azTrimMetric">0.0 deg</strong></div>
        <div class="metric"><span>Incidence</span><strong id="incMetric">1.50 deg</strong></div>
      </div>
    </header>

    <section class="description-panel" aria-labelledby="descriptionTitle">
      <div>
        <h2 id="descriptionTitle">Script-to-lab interface</h2>
        <p>
          This graphical user interface presents work that is largely performed in an AI-assisted script environment. It makes the utility of those scripts visible by turning crystallographic calculations, dual-mounted sample geometry, and editable beam-steering calibration into a live azimuth map.
        </p>
        <p>
          The goal is to provide a more accessible workflow for labmates: compare (001) and (111) mounts, check likely RHEED zone-axis candidates, and export a compact candidate table without running the full script stack.
        </p>
      </div>
      <figure class="mount-figure">
        <img src="dual-mounted-sample-cartoon.png" alt="Dual-mounted sample cartoon showing a square GaSb(001) substrate and triangular GaSb(111)A substrate on the same circular holder.">
        <figcaption>dual-mounted sample geometry</figcaption>
      </figure>
    </section>

    <main>
      <aside>
        <section class="panel">
          <h2>Manipulator</h2>
          <div class="control-grid">
            <div class="control">
              <label for="rotation">Rotation</label>
              <div class="paired">
                <input id="rotationRange" type="range" min="0" max="360" step="0.1">
                <input id="rotation" type="number" min="-720" max="720" step="0.1">
              </div>
            </div>
            <div class="two-col">
              <div class="control">
                <label for="deflx">deflX</label>
                <input id="deflx" type="number" step="0.1">
              </div>
              <div class="control">
                <label for="defly">deflY</label>
                <input id="defly" type="number" step="0.1">
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>Beam Calibration</h2>
          <div class="control-grid">
            <div class="two-col">
              <div class="control">
                <label for="deflxScale">deflX deg/unit</label>
                <input id="deflxScale" type="number" step="0.001">
              </div>
              <div class="control">
                <label for="deflyScale">deflY deg/unit</label>
                <input id="deflyScale" type="number" step="0.001">
              </div>
            </div>
            <div class="two-col">
              <div class="control">
                <label for="baseIncidence">Base incidence</label>
                <input id="baseIncidence" type="number" step="0.01">
              </div>
              <div class="control">
                <label for="targetIncidence">Target incidence</label>
                <input id="targetIncidence" type="number" step="0.01">
              </div>
            </div>
          </div>
        </section>

        <section class="panel">
          <h2>Dual Mount</h2>
          <div class="control-grid">
            <div class="checks">
              <div class="check-row">
                <label for="use001">(001), zero [110]</label>
                <input id="use001" type="checkbox" checked>
              </div>
              <div class="check-row">
                <label for="use111">(111), zero [1 -1 0]</label>
                <input id="use111" type="checkbox" checked>
              </div>
            </div>
            <div class="two-col">
              <div class="control">
                <label for="offset001">(001) offset</label>
                <input id="offset001" type="number" step="0.1">
              </div>
              <div class="control">
                <label for="offset111">(111) offset</label>
                <input id="offset111" type="number" step="0.1">
              </div>
            </div>
            <div class="control">
              <label for="maxIndex">Max Miller index</label>
              <select id="maxIndex">
                <option value="1">1</option>
                <option value="2">2</option>
                <option value="3">3</option>
                <option value="4">4</option>
                <option value="5">5</option>
                <option value="6">6</option>
              </select>
            </div>
          </div>
          <div class="button-row">
            <button id="resetButton" type="button">Reset</button>
            <button id="csvButton" type="button">Export CSV</button>
          </div>
        </section>
      </aside>

      <section class="workspace">
        <section class="panel visual">
          <div class="compass-wrap">
            <canvas id="compass" width="900" height="700"></canvas>
            <div class="readout">
              <div class="legend">
                <span><b style="background:#0f766e"></b>(001)</span>
                <span><b style="background:#b45309"></b>(111)</span>
                <span><b style="background:#17201f"></b>current</span>
              </div>
              <div id="beamReadout"></div>
            </div>
          </div>
          <div class="detail-stack">
            <div class="selected-axis">
              <h2>Nearest Axis</h2>
              <div id="axisBig" class="axis-big">[110]</div>
              <div id="axisMeta" class="axis-meta"></div>
            </div>
            <div id="nearestList" class="nearest-list"></div>
          </div>
        </section>

        <section class="tables">
          <section class="panel table-panel">
            <h2>(001) nearest axes</h2>
            <div id="table001"></div>
          </section>
          <section class="panel table-panel">
            <h2>(111) nearest axes</h2>
            <div id="table111"></div>
          </section>
        </section>

        <section class="panel table-panel">
          <h2>Shared rotation candidates</h2>
          <div id="overlapTable"></div>
        </section>
      </section>
    </main>
  </div>

  <script>
    const PAYLOAD = __PAYLOAD__;
    const DEG = Math.PI / 180;
    const RAD = 180 / Math.PI;
    const stateKeys = [
      "rotation",
      "deflx",
      "defly",
      "deflxScale",
      "deflyScale",
      "baseIncidence",
      "targetIncidence",
      "offset001",
      "offset111",
      "maxIndex"
    ];

    const els = {};
    for (const id of [
      ...stateKeys,
      "rotationRange",
      "use001",
      "use111",
      "rotationMetric",
      "azTrimMetric",
      "incMetric",
      "beamReadout",
      "axisBig",
      "axisMeta",
      "nearestList",
      "table001",
      "table111",
      "overlapTable",
      "compass",
      "resetButton",
      "csvButton",
      "title"
    ]) {
      els[id] = document.getElementById(id);
    }

    let lastRows = [];

    function mod(value, period) {
      return ((value % period) + period) % period;
    }

    function signedDelta(target, current, period) {
      return mod(target - current + period / 2, period) - period / 2;
    }

    function lineDelta(target, current) {
      return signedDelta(target, current, 180);
    }

    function lineDistance(a, b) {
      return Math.abs(lineDelta(a, b));
    }

    function dot(a, b) {
      return a.reduce((sum, value, index) => sum + value * b[index], 0);
    }

    function cross(a, b) {
      return [
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0]
      ];
    }

    function norm(a) {
      return Math.sqrt(dot(a, a));
    }

    function normalize(a) {
      const length = norm(a);
      return length === 0 ? [0, 0, 0] : a.map(value => value / length);
    }

    function sub(a, b) {
      return a.map((value, index) => value - b[index]);
    }

    function scale(a, factor) {
      return a.map(value => value * factor);
    }

    function gcd2(a, b) {
      a = Math.abs(a);
      b = Math.abs(b);
      while (b !== 0) {
        const next = a % b;
        a = b;
        b = next;
      }
      return a;
    }

    function gcd3(h, k, l) {
      return gcd2(gcd2(h, k), l);
    }

    function canonicalLine(vector) {
      const divisor = gcd3(vector[0], vector[1], vector[2]) || 1;
      let out = vector.map(value => value / divisor);
      for (const value of out) {
        if (value !== 0) {
          if (value < 0) {
            out = out.map(item => -item);
          }
          break;
        }
      }
      return out;
    }

    function axisLabel(vector) {
      return "[" + vector.map(value => String(value)).join(" ") + "]";
    }

    function buildBasis(sample) {
      const n = normalize(sample.normal);
      const zero = normalize(sample.zero);
      const u = normalize(sub(zero, scale(n, dot(zero, n))));
      const v = normalize(cross(n, u));
      return { n, u, v };
    }

    function generateAxes(sampleKey, maxIndex) {
      const sample = PAYLOAD.samples[sampleKey];
      const basis = buildBasis(sample);
      const seen = new Map();
      for (let h = -maxIndex; h <= maxIndex; h++) {
        for (let k = -maxIndex; k <= maxIndex; k++) {
          for (let l = -maxIndex; l <= maxIndex; l++) {
            if (h === 0 && k === 0 && l === 0) continue;
            if (gcd3(h, k, l) !== 1) continue;
            const raw = [h, k, l];
            if (dot(raw, sample.normal) !== 0) continue;
            const canonical = canonicalLine(raw);
            const key = canonical.join(",");
            if (seen.has(key)) continue;
            const unit = normalize(canonical);
            const angle = mod(Math.atan2(dot(unit, basis.v), dot(unit, basis.u)) * RAD, 180);
            const maxAbs = Math.max(...canonical.map(Math.abs));
            const indexSum = canonical.reduce((sum, value) => sum + Math.abs(value), 0);
            seen.set(key, {
              vector: canonical,
              label: axisLabel(canonical),
              angle,
              maxAbs,
              indexSum,
              sampleKey
            });
          }
        }
      }
      return [...seen.values()].sort((a, b) => {
        if (a.maxAbs !== b.maxAbs) return a.maxAbs - b.maxAbs;
        if (a.indexSum !== b.indexSum) return a.indexSum - b.indexSum;
        return a.angle - b.angle;
      });
    }

    function readNumber(id) {
      const value = Number(els[id].value);
      return Number.isFinite(value) ? value : 0;
    }

    function readState() {
      return {
        rotation: readNumber("rotation"),
        deflx: readNumber("deflx"),
        defly: readNumber("defly"),
        deflxScale: readNumber("deflxScale"),
        deflyScale: readNumber("deflyScale"),
        baseIncidence: readNumber("baseIncidence"),
        targetIncidence: readNumber("targetIncidence"),
        offset001: readNumber("offset001"),
        offset111: readNumber("offset111"),
        maxIndex: Math.max(1, Math.min(6, Math.round(readNumber("maxIndex")))),
        use001: els.use001.checked,
        use111: els.use111.checked
      };
    }

    function setDefaults() {
      const defaults = PAYLOAD.defaults;
      for (const [key, value] of Object.entries(defaults)) {
        if (els[key]) els[key].value = value;
      }
      els.use001.checked = true;
      els.use111.checked = true;
      syncRotationRange(defaults.rotation);
    }

    function syncRotationRange(value) {
      els.rotationRange.value = mod(Number(value) || 0, 360);
    }

    function targetForAxis(axis, sampleKey, state) {
      const offset = sampleKey === "001" ? state.offset001 : state.offset111;
      const trim = state.deflx * state.deflxScale;
      const baseTarget = mod(axis.angle + offset - trim, 180);
      const delta = lineDelta(baseTarget, state.rotation);
      return {
        target: mod(state.rotation + delta, 360),
        delta
      };
    }

    function computeSample(sampleKey, state) {
      const axes = generateAxes(sampleKey, state.maxIndex);
      const offset = sampleKey === "001" ? state.offset001 : state.offset111;
      const azimuth = mod(state.rotation - offset + state.deflx * state.deflxScale, 360);
      const matches = axes.map(axis => {
        const target = targetForAxis(axis, sampleKey, state);
        const miss = lineDistance(axis.angle, azimuth);
        return {
          ...axis,
          miss,
          targetRotation: target.target,
          deltaRotation: target.delta,
          sampleLabel: PAYLOAD.samples[sampleKey].label,
          color: PAYLOAD.samples[sampleKey].color
        };
      }).sort((a, b) => {
        if (a.miss !== b.miss) return a.miss - b.miss;
        return a.indexSum - b.indexSum;
      });
      return { sampleKey, azimuth, axes, matches };
    }

    function formatDegree(value, digits = 1) {
      return `${value.toFixed(digits)} deg`;
    }

    function deltaText(value) {
      const sign = value > 0 ? "+" : "";
      return `${sign}${value.toFixed(1)} deg`;
    }

    function classForMiss(value) {
      if (value <= 0.5) return "good";
      if (value <= 2.0) return "ok";
      return "bad";
    }

    function renderTable(target, rows) {
      if (!rows.length) {
        target.innerHTML = '<div class="empty">Disabled</div>';
        return;
      }
      const body = rows.slice(0, 8).map(row => `
        <tr>
          <td class="axis-cell" style="color:${row.color}">${row.label}</td>
          <td><span class="pill ${classForMiss(row.miss)}">${row.miss.toFixed(2)}</span></td>
          <td>${row.targetRotation.toFixed(1)}</td>
          <td>${deltaText(row.deltaRotation)}</td>
        </tr>
      `).join("");
      target.innerHTML = `
        <table>
          <thead><tr><th>Axis</th><th>Miss</th><th>Rotate to</th><th>Delta</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      `;
    }

    function renderNearestList(results) {
      const rows = results.flatMap(result => result.matches.slice(0, 4))
        .sort((a, b) => a.miss - b.miss)
        .slice(0, 8);
      if (!rows.length) {
        els.nearestList.innerHTML = '<div class="empty">Enable a mounted sample.</div>';
        return;
      }
      els.nearestList.innerHTML = rows.map(row => `
        <div class="mini-card">
          <div class="swatch" style="background:${row.color}"></div>
          <div>
            <strong>${row.sampleLabel} ${row.label}</strong>
            <span>miss ${row.miss.toFixed(2)} deg, rotate to ${row.targetRotation.toFixed(1)} deg</span>
          </div>
          <div class="delta">${deltaText(row.deltaRotation)}</div>
        </div>
      `).join("");
    }

    function averageLine(a, b) {
      const delta = lineDelta(b, a);
      return mod(a + delta / 2, 180);
    }

    function renderOverlap(state, result001, result111) {
      if (!result001 || !result111) {
        els.overlapTable.innerHTML = '<div class="empty">Enable both samples to compare shared rotations.</div>';
        return;
      }
      const rows = [];
      for (const a of result001.axes) {
        const targetA = mod(a.angle + state.offset001 - state.deflx * state.deflxScale, 180);
        for (const b of result111.axes) {
          const targetB = mod(b.angle + state.offset111 - state.deflx * state.deflxScale, 180);
          const split = lineDistance(targetA, targetB);
          if (split > 8) continue;
          const target = averageLine(targetA, targetB);
          rows.push({
            axis001: a.label,
            axis111: b.label,
            split,
            target: mod(target, 360),
            delta: lineDelta(target, state.rotation)
          });
        }
      }
      rows.sort((a, b) => {
        if (a.split !== b.split) return a.split - b.split;
        return Math.abs(a.delta) - Math.abs(b.delta);
      });
      if (!rows.length) {
        els.overlapTable.innerHTML = '<div class="empty">No shared low-index rotations within 8 deg at these offsets.</div>';
        return;
      }
      const body = rows.slice(0, 10).map(row => `
        <tr>
          <td class="axis-cell" style="color:${PAYLOAD.samples["001"].color}">${row.axis001}</td>
          <td class="axis-cell" style="color:${PAYLOAD.samples["111"].color}">${row.axis111}</td>
          <td>${row.split.toFixed(2)}</td>
          <td>${row.target.toFixed(1)}</td>
          <td>${deltaText(row.delta)}</td>
        </tr>
      `).join("");
      els.overlapTable.innerHTML = `
        <table>
          <thead><tr><th>(001)</th><th>(111)</th><th>Split</th><th>Rotation</th><th>Delta</th></tr></thead>
          <tbody>${body}</tbody>
        </table>
      `;
    }

    function resizeCanvas() {
      const canvas = els.compass;
      const rect = canvas.getBoundingClientRect();
      const ratio = window.devicePixelRatio || 1;
      const width = Math.max(320, Math.round(rect.width * ratio));
      const height = Math.max(320, Math.round(rect.height * ratio));
      if (canvas.width !== width || canvas.height !== height) {
        canvas.width = width;
        canvas.height = height;
      }
    }

    function pointOnCircle(cx, cy, radius, angleDeg) {
      const angle = (angleDeg - 90) * DEG;
      return {
        x: cx + radius * Math.cos(angle),
        y: cy + radius * Math.sin(angle)
      };
    }

    function drawTick(ctx, cx, cy, radius, angle, color, label, longTick) {
      const outer = pointOnCircle(cx, cy, radius, angle);
      const inner = pointOnCircle(cx, cy, radius - (longTick ? 26 : 15), angle);
      ctx.strokeStyle = color;
      ctx.lineWidth = longTick ? 2.5 : 1.4;
      ctx.beginPath();
      ctx.moveTo(inner.x, inner.y);
      ctx.lineTo(outer.x, outer.y);
      ctx.stroke();

      if (label) {
        const textPoint = pointOnCircle(cx, cy, radius - (longTick ? 46 : 34), angle);
        ctx.fillStyle = color;
        ctx.font = `${longTick ? 14 : 11}px Aptos, Segoe UI, sans-serif`;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.fillText(label, textPoint.x, textPoint.y);
      }
    }

    function drawCompass(state, results) {
      resizeCanvas();
      const canvas = els.compass;
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);

      const cx = width / 2;
      const cy = height / 2;
      const radius = Math.max(120, Math.min(width, height) * 0.38);

      ctx.fillStyle = "#fbfcfb";
      ctx.fillRect(0, 0, width, height);

      ctx.strokeStyle = "#cdd8d4";
      ctx.lineWidth = 1.5;
      ctx.beginPath();
      ctx.arc(cx, cy, radius, 0, Math.PI * 2);
      ctx.stroke();

      for (let angle = 0; angle < 360; angle += 30) {
        const major = angle % 90 === 0;
        const p1 = pointOnCircle(cx, cy, radius, angle);
        const p2 = pointOnCircle(cx, cy, radius - (major ? 16 : 9), angle);
        ctx.strokeStyle = major ? "#7f918c" : "#d7e0dd";
        ctx.lineWidth = major ? 1.4 : 1;
        ctx.beginPath();
        ctx.moveTo(p1.x, p1.y);
        ctx.lineTo(p2.x, p2.y);
        ctx.stroke();
        if (major) {
          const labelPoint = pointOnCircle(cx, cy, radius + 20, angle);
          ctx.fillStyle = "#60706d";
          ctx.font = "12px Aptos, Segoe UI, sans-serif";
          ctx.textAlign = "center";
          ctx.textBaseline = "middle";
          ctx.fillText(`${angle}`, labelPoint.x, labelPoint.y);
        }
      }

      for (const result of results) {
        const sample = PAYLOAD.samples[result.sampleKey];
        const offset = result.sampleKey === "001" ? state.offset001 : state.offset111;
        const trim = state.deflx * state.deflxScale;
        const baseRadius = result.sampleKey === "001" ? radius : radius - 34;
        for (const axis of result.axes) {
          const stageAngle = mod(axis.angle + offset - trim, 180);
          const major = axis.maxAbs <= 1 || axis.indexSum <= 2;
          const label = major ? axis.label : "";
          drawTick(ctx, cx, cy, baseRadius, stageAngle, sample.color, label, major);
          drawTick(ctx, cx, cy, baseRadius, stageAngle + 180, sample.color, "", major);
        }
      }

      const current = mod(state.rotation, 360);
      const lineA = pointOnCircle(cx, cy, radius + 10, current);
      const lineB = pointOnCircle(cx, cy, 34, current);
      ctx.strokeStyle = "#17201f";
      ctx.lineWidth = 3;
      ctx.beginPath();
      ctx.moveTo(lineB.x, lineB.y);
      ctx.lineTo(lineA.x, lineA.y);
      ctx.stroke();

      ctx.fillStyle = "#17201f";
      ctx.beginPath();
      ctx.arc(cx, cy, 5, 0, Math.PI * 2);
      ctx.fill();

      ctx.fillStyle = "#17201f";
      ctx.font = "700 16px Aptos, Segoe UI, sans-serif";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(`${current.toFixed(1)} deg`, cx, cy + radius + 44);
    }

    function render() {
      const state = readState();
      syncRotationRange(state.rotation);
      els.rotationMetric.textContent = formatDegree(mod(state.rotation, 360));
      els.azTrimMetric.textContent = formatDegree(state.deflx * state.deflxScale);
      const incidence = state.baseIncidence + state.defly * state.deflyScale;
      els.incMetric.textContent = formatDegree(incidence, 2);
      const deflyTarget = state.deflyScale === 0 ? null : (state.targetIncidence - state.baseIncidence) / state.deflyScale;
      const deflyText = deflyTarget === null ? "deflY target n/a" : `deflY target ${deflyTarget.toFixed(2)}`;

      const results = [];
      let result001 = null;
      let result111 = null;
      if (state.use001) {
        result001 = computeSample("001", state);
        results.push(result001);
      }
      if (state.use111) {
        result111 = computeSample("111", state);
        results.push(result111);
      }

      const allNearest = results.flatMap(result => result.matches)
        .sort((a, b) => a.miss - b.miss);
      const nearest = allNearest[0];
      if (nearest) {
        els.axisBig.textContent = `${nearest.sampleLabel} ${nearest.label}`;
        els.axisBig.style.color = nearest.color;
        els.axisMeta.innerHTML = `
          Miss ${nearest.miss.toFixed(2)} deg. Rotate to ${nearest.targetRotation.toFixed(1)} deg
          (${deltaText(nearest.deltaRotation)}). ${deflyText}
        `;
      } else {
        els.axisBig.textContent = "No sample";
        els.axisBig.style.color = "#17201f";
        els.axisMeta.textContent = "";
      }

      els.beamReadout.textContent = [
        result001 ? `(001) az ${result001.azimuth.toFixed(1)} deg` : null,
        result111 ? `(111) az ${result111.azimuth.toFixed(1)} deg` : null,
        deflyTarget === null ? "deflY target n/a" : `deflY target ${deflyTarget.toFixed(2)}`
      ].filter(Boolean).join(" | ");

      renderNearestList(results);
      renderTable(els.table001, result001 ? result001.matches : []);
      renderTable(els.table111, result111 ? result111.matches : []);
      renderOverlap(state, result001, result111);
      drawCompass(state, results);

      lastRows = allNearest.map(row => ({
        sample: row.sampleLabel,
        axis: row.label,
        miss_deg: row.miss.toFixed(4),
        target_rotation_deg: row.targetRotation.toFixed(4),
        delta_rotation_deg: row.deltaRotation.toFixed(4)
      }));
    }

    function downloadCsv() {
      if (!lastRows.length) return;
      const headers = Object.keys(lastRows[0]);
      const lines = [headers.join(",")];
      for (const row of lastRows) {
        lines.push(headers.map(header => JSON.stringify(row[header])).join(","));
      }
      const blob = new Blob([lines.join("\n") + "\n"], { type: "text/csv" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = "mbe_zone_axis_candidates.csv";
      anchor.click();
      URL.revokeObjectURL(url);
    }

    function bindControls() {
      for (const id of stateKeys) {
        els[id].addEventListener("input", render);
      }
      els.use001.addEventListener("input", render);
      els.use111.addEventListener("input", render);
      els.rotationRange.addEventListener("input", () => {
        els.rotation.value = els.rotationRange.value;
        render();
      });
      els.resetButton.addEventListener("click", () => {
        setDefaults();
        render();
      });
      els.csvButton.addEventListener("click", downloadCsv);
      window.addEventListener("resize", render);
    }

    els.title.textContent = PAYLOAD.title;
    document.title = PAYLOAD.title;
    setDefaults();
    bindControls();
    render();
  </script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
