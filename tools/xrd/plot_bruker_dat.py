from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_xrd_dat(path: Path) -> tuple[str, np.ndarray, np.ndarray, np.ndarray]:
    header_lines: list[str] = []
    xs: list[float] = []
    ys: list[float] = []
    es: list[float] = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            if line.startswith("#"):
                header_lines.append(line)
                continue
            parts = line.split()
            if len(parts) < 3:
                continue
            xs.append(float(parts[0]))
            ys.append(float(parts[1]))
            es.append(float(parts[2]))

    if not xs:
        raise ValueError(f"No numeric rows found in {path}")

    title = Path(path).stem
    for h in header_lines:
        if "Scantype:" in h:
            title = f"{Path(path).stem} ({h.split('Scantype:')[-1].split()[0].strip('\"')})"
            break

    return title, np.array(xs), np.array(ys), np.array(es)


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot Bruker-style XRD .dat files.")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--linear-out", type=Path, default=None)
    parser.add_argument("--title", type=str, default=None)
    parser.add_argument("--xmin", type=float, default=None)
    parser.add_argument("--xmax", type=float, default=None)
    args = parser.parse_args()

    title, x, y, e = load_xrd_dat(args.input_path)
    if args.title:
        title = args.title

    args.out.parent.mkdir(parents=True, exist_ok=True)

    mask = np.ones_like(x, dtype=bool)
    if args.xmin is not None:
        mask &= x >= args.xmin
    if args.xmax is not None:
        mask &= x <= args.xmax
    x = x[mask]
    y = y[mask]
    e = e[mask]

    plt.rcParams.update(
        {
            "font.size": 13,
            "axes.titlesize": 20,
            "axes.labelsize": 16,
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
            "legend.fontsize": 12,
        }
    )

    fig, ax = plt.subplots(figsize=(13.5, 7.5), dpi=160, constrained_layout=True)
    ax.semilogy(x, y, color="black", lw=0.8, label="ExpCPS")
    ax.set_title(title)
    ax.set_xlabel(r"2$\theta$ (deg)")
    ax.set_ylabel("Intensity (CPS)")
    ax.grid(True, which="major", color="#d9d9d9", lw=0.6)
    ax.grid(True, which="minor", color="#efefef", lw=0.4)
    ax.legend(loc="upper right", frameon=False)
    fig.savefig(args.out, dpi=220)
    plt.close(fig)

    if args.linear_out is not None:
        fig, ax = plt.subplots(figsize=(13.5, 7.5), dpi=160, constrained_layout=True)
        ax.plot(x, y, color="black", lw=0.8, label="ExpCPS")
        ax.set_title(title + " (linear scale)")
        ax.set_xlabel(r"2$\theta$ (deg)")
        ax.set_ylabel("Intensity (CPS)")
        ax.grid(True, which="major", color="#d9d9d9", lw=0.6)
        ax.legend(loc="upper right", frameon=False)
        fig.savefig(args.linear_out, dpi=220)
        plt.close(fig)


if __name__ == "__main__":
    main()
