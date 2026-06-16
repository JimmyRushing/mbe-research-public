#!/usr/bin/env python3
"""
Extract/digitize Schmid et al. PRB 2022 Fig. 3(a) from the local PDF.

This script has two modes:
  render  - render PDF pages to PNG for visual inspection
  overlay - write an approximate Schmid Fig. 3(a) overlay dataset and plot it

The overlay dataset is built from the explicitly reported Fig. 2/Table I
checkpoints plus the Fig. 3(a) phase-boundary statements in the paper. If a
manually digitized CSV is later supplied, the plotting path can use that instead.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pypdfium2 as pdfium
from PIL import Image


SCHMID_FIG3A_POINTS = [
    # d1_nm, Egap_meV, source
    # The 8.0/10.0/10.75 values are explicitly reported in Fig. 2/Table I.
    # 9.1 and 11.6 are explicitly reported phase boundaries from the text.
    # 13.5 is the semimetal sample and is plotted gapless in Fig. 3(a).
    (8.0, 22.6, "reported sample: triv"),
    (9.1, 0.0, "reported trivial-to-TI boundary"),
    (10.0, 11.0, "reported sample: hyb1"),
    (10.75, 6.7, "reported sample: hyb2"),
    (11.6, 0.0, "reported TI-to-SM boundary"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="mode", required=True)

    render = sub.add_parser("render")
    render.add_argument("pdf", type=Path)
    render.add_argument("--out-dir", type=Path, required=True)
    render.add_argument("--scale", type=float, default=3.0)
    render.add_argument("--pages", type=int, nargs="*", default=None, help="1-based pages to render")

    overlay = sub.add_parser("overlay")
    overlay.add_argument("cadtronics_csv", type=Path)
    overlay.add_argument("--out", type=Path, required=True)
    overlay.add_argument("--schmid-csv", type=Path, required=True)
    overlay.add_argument("--title", default="Cadtronics 5 K vs Schmid Fig. 3(a)")
    overlay.add_argument("--no-anchors", action="store_true", help="Do not plot reported Schmid anchor points.")
    overlay.add_argument("--no-phase-blocks", action="store_true", help="Do not draw gray phase-region backgrounds.")

    crop = sub.add_parser("crop")
    crop.add_argument("page_png", type=Path)
    crop.add_argument("--out", type=Path, required=True)
    crop.add_argument("--box", type=int, nargs=4, required=True, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))

    digitize = sub.add_parser("digitize")
    digitize.add_argument("page_png", type=Path)
    digitize.add_argument("--out-csv", type=Path, required=True)
    digitize.add_argument("--out-debug", type=Path, default=None)
    digitize.add_argument("--box", type=int, nargs=4, required=True, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    digitize.add_argument("--xlim", type=float, nargs=2, default=(7.5, 13.0))
    digitize.add_argument("--ylim", type=float, nargs=2, default=(-30.0, 90.0))
    return parser.parse_args()


def render_pages(pdf_path: Path, out_dir: Path, scale: float, pages: list[int] | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = pdfium.PdfDocument(pdf_path)
    indices = [p - 1 for p in pages] if pages else list(range(len(doc)))
    for idx in indices:
        page = doc[idx]
        bitmap = page.render(scale=scale)
        image = bitmap.to_pil()
        out = out_dir / f"{pdf_path.stem}_page_{idx + 1:02d}.png"
        image.save(out)
        print(out)


def write_schmid_csv(path: Path) -> pd.DataFrame:
    df = pd.DataFrame(SCHMID_FIG3A_POINTS, columns=["d1_nm", "gap_mev", "source"])
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return df


def plot_overlay(cadtronics_csv: Path, out: Path, schmid_csv: Path, title: str, show_anchors: bool = True, show_phase_blocks: bool = True) -> None:
    cad = pd.read_csv(cadtronics_csv).sort_values("d1_nm")
    if schmid_csv.exists():
        schmid = pd.read_csv(schmid_csv).sort_values("d1_nm")
    else:
        schmid = write_schmid_csv(schmid_csv)

    fig, ax = plt.subplots(figsize=(9.5, 5.8))

    ax.axhline(0, color="black", linewidth=1.2)
    if show_phase_blocks:
        ax.axvspan(7.75, 9.1, color="0.88", zorder=0)
        ax.axvspan(9.1, 11.6, color="0.74", zorder=0)
        ax.axvspan(11.6, 13.75, color="1.0", zorder=0)
        ax.axvline(9.1, color="0.25", linestyle="--", linewidth=1.5)
        ax.axvline(11.6, color="0.25", linestyle="--", linewidth=1.5)

    ax.plot(
        cad["d1_nm"],
        cad["gap_mev"],
        color="#114477",
        marker="o",
        markersize=7,
        markerfacecolor="white",
        markeredgewidth=1.8,
        linewidth=2.4,
        label="Cadtronics 5 K extracted gap",
        zorder=3,
    )
    schmid_curve = schmid[schmid["source"].astype(str).str.contains("digitized", case=False, na=False)]
    schmid_anchors = schmid[~schmid["source"].astype(str).str.contains("digitized", case=False, na=False)]
    if schmid_curve.empty:
        schmid_curve = schmid
        schmid_anchors = schmid.iloc[0:0]

    ax.plot(
        schmid_curve["d1_nm"],
        schmid_curve["gap_mev"],
        color="#B22222",
        marker=".",
        markersize=4,
        linewidth=2.0,
        linestyle="--",
        label="Schmid Fig. 3(a) digitized curve",
        zorder=4,
    )
    if show_anchors and not schmid_anchors.empty:
        ax.scatter(
            schmid_anchors["d1_nm"],
            schmid_anchors["gap_mev"],
            color="#B22222",
            marker="x",
            s=80,
            linewidths=2.2,
            label="Schmid reported anchors",
            zorder=5,
        )

    for _, row in cad.iterrows():
        ax.text(float(row["d1_nm"]), float(row["gap_mev"]) + 0.8, f"{row['gap_mev']:.1f}", ha="center", va="bottom", fontsize=8)
    if show_anchors:
        for _, row in schmid_anchors.iterrows():
            ax.text(float(row["d1_nm"]) + 0.04, float(row["gap_mev"]) - 1.2, f"{row['gap_mev']:.1f}", color="#B22222", ha="left", va="top", fontsize=8)

    if show_phase_blocks:
        ax.text(8.45, 0.95, "trivial", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=11)
        ax.text(10.35, 0.95, "TI", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=11)
        ax.text(12.55, 0.95, "SM", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=11)

    ax.set_title(title, fontsize=15, pad=14)
    ax.set_xlabel("InAs thickness d1 (nm)", fontsize=13)
    ax.set_ylabel("Extracted band gap Egap (meV)", fontsize=13)
    ax.set_xlim(7.75, 13.75)
    ymin = min(-5.0, float(cad["gap_mev"].min()) - 4.0, float(schmid["gap_mev"].min()) - 4.0)
    ymax = max(30.0, float(cad["gap_mev"].max()) + 5.0, float(schmid["gap_mev"].max()) + 5.0)
    ax.set_ylim(ymin, ymax)
    ax.grid(True, color="0.86", linewidth=0.8)
    ax.legend(loc="upper right", frameon=True, fontsize=10)

    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=300, bbox_inches="tight")
    print(out)
    print(schmid_csv)


def crop_image(page_png: Path, out: Path, box: list[int]) -> None:
    image = Image.open(page_png).convert("RGB")
    crop = image.crop(tuple(box))
    out.parent.mkdir(parents=True, exist_ok=True)
    crop.save(out)
    print(out)


def digitize_fig3a(page_png: Path, out_csv: Path, out_debug: Path | None, box: list[int], xlim: tuple[float, float], ylim: tuple[float, float]) -> None:
    """Digitize the black Fig. 3(a) E_gap curve from a cropped PDF render.

    The panel is small, so the goal is a faithful overlay, not metrology-grade
    extraction. We threshold dark pixels, discard axes/text/phase labels by
    keeping pixels near the curve y-range, and take a vertical median per x-bin.
    """
    image = Image.open(page_png).convert("RGB")
    crop = image.crop(tuple(box))
    arr = np.asarray(crop)
    h, w = arr.shape[:2]

    # Approximate plot area within the panel crop; these are fractions of the
    # cropped panel, not page coordinates.
    plot_left = int(round(0.215 * w))
    plot_right = int(round(0.965 * w))
    plot_top = int(round(0.145 * h))
    plot_bottom = int(round(0.905 * h))

    plot = arr[plot_top:plot_bottom, plot_left:plot_right]
    gray = plot.mean(axis=2)
    dark = gray < 80

    yy, xx = np.where(dark)
    # Remove axes/ticks/text/phase-region boundaries by accepting only the
    # main curve band. In pixel space this tracks roughly -18 to 34 meV.
    x_data = xlim[0] + (xx / max(1, plot.shape[1] - 1)) * (xlim[1] - xlim[0])
    y_data = ylim[1] - (yy / max(1, plot.shape[0] - 1)) * (ylim[1] - ylim[0])
    keep = (x_data >= 7.85) & (x_data <= 12.95) & (y_data >= -18) & (y_data <= 35)
    x_data = x_data[keep]
    y_data = y_data[keep]
    yy = yy[keep]
    xx = xx[keep]

    # Bin in physical x. Median is robust to markers, dotted joins, and text.
    bins = np.arange(7.9, 13.05, 0.1)
    records = []
    for left, right in zip(bins[:-1], bins[1:]):
        m = (x_data >= left) & (x_data < right)
        if int(m.sum()) < 3:
            continue
        x_mid = (left + right) / 2
        # Use lower-half dark pixels when a marker circle thickens the curve.
        ys = y_data[m]
        y_med = float(np.median(ys))
        records.append({"d1_nm": round(x_mid, 3), "gap_mev": y_med, "source": "digitized from Fig. 3(a)"})

    df = pd.DataFrame(records)
    # Add exact values explicitly reported in Table I/figure text as anchors.
    anchors = pd.DataFrame(SCHMID_FIG3A_POINTS, columns=["d1_nm", "gap_mev", "source"])
    # The lower-left legend line in Fig. 3(a) is also black; discard those
    # false detections and keep the explicitly reported 8 nm point instead.
    df = df[df["d1_nm"] >= 8.35]
    df = df[~((df["d1_nm"] < 8.6) & (df["gap_mev"] < 0.0))]
    df = pd.concat([df, anchors], ignore_index=True).sort_values("d1_nm")
    df = df.drop_duplicates(subset=["d1_nm"], keep="last")

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_csv, index=False)
    print(out_csv)

    if out_debug is not None:
        fig, ax = plt.subplots(figsize=(6, 4.5))
        ax.imshow(crop)
        rect_x = [plot_left, plot_right, plot_right, plot_left, plot_left]
        rect_y = [plot_top, plot_top, plot_bottom, plot_bottom, plot_top]
        ax.plot(rect_x, rect_y, color="red", linewidth=1.5)
        for _, row in df.iterrows():
            px = plot_left + (float(row["d1_nm"]) - xlim[0]) / (xlim[1] - xlim[0]) * (plot_right - plot_left)
            py = plot_top + (ylim[1] - float(row["gap_mev"])) / (ylim[1] - ylim[0]) * (plot_bottom - plot_top)
            ax.scatter([px], [py], s=12, color="cyan")
        ax.set_axis_off()
        out_debug.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(out_debug, dpi=250, bbox_inches="tight")
        plt.close(fig)
        print(out_debug)


def main() -> None:
    args = parse_args()
    if args.mode == "render":
        render_pages(args.pdf, args.out_dir, args.scale, args.pages)
    elif args.mode == "overlay":
        plot_overlay(
            args.cadtronics_csv,
            args.out,
            args.schmid_csv,
            args.title,
            show_anchors=not args.no_anchors,
            show_phase_blocks=not args.no_phase_blocks,
        )
    elif args.mode == "crop":
        crop_image(args.page_png, args.out, args.box)
    elif args.mode == "digitize":
        digitize_fig3a(args.page_png, args.out_csv, args.out_debug, args.box, tuple(args.xlim), tuple(args.ylim))


if __name__ == "__main__":
    main()
