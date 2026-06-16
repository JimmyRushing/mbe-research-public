#!/usr/bin/env python3
"""
Print double-mounted MBE RHEED setpoints for low-index reflection/zone-axis candidates.

Double-mounted workflow encoded here:
1. Find the manipulator rotation where the major flat points at the beam.
2. Center the (001) sample and record deflX/deflY.
3. Because the major flats are mounted parallel, scan only in deflY to the
   (111) sample and record the signed offset from the (001) center as deltaY.
4. Run this script to get rotation, deflX, and deflY setpoints for candidate
   in-plane axes of both mounted samples.
"""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


SAMPLES = {
    "001": {
        "label": "(001)",
        "normal": (0, 0, 1),
        "zero": (1, 1, 0),
        "zero_label": "[110]",
    },
    "111": {
        "label": "(111)",
        "normal": (1, 1, 1),
        "zero": (1, -1, 0),
        "zero_label": "[1 -1 0]",
    },
}

MAJOR_AXES = {
    "001": [
        (1, 1, 0),
        (0, 1, 0),
        (1, -1, 0),
        (1, 0, 0),
    ],
    "111": [
        (1, -1, 0),
        (2, -1, -1),
        (1, 0, -1),
        (1, 1, -2),
        (0, 1, -1),
        (1, -2, 1),
    ],
}


@dataclass(frozen=True)
class Axis:
    sample: str
    vector: tuple[int, int, int]
    angle_deg: float
    max_abs_index: int
    index_sum: int

    @property
    def label(self) -> str:
        return "[" + " ".join(str(value) for value in self.vector) + "]"


@dataclass(frozen=True)
class Setpoint:
    sample: str
    axis: str
    angle_from_flat_deg: float
    rotation_deg: float
    deflx: float
    defly: float
    offset_x: float
    offset_y: float
    index_rank: int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compute rotation, deflX, and deflY setpoints for double-mounted (001)/(111) RHEED reflection candidates."
    )
    parser.add_argument("--flat-rotation", type=float, help="Rotation where the major flat points at the beam.")
    parser.add_argument("--center-deflx", type=float, help="deflX for the centered (001) sample.")
    parser.add_argument("--center-defly", type=float, help="deflY for the centered (001) sample.")
    parser.add_argument(
        "--delta-y",
        "--delta",
        dest="delta_y",
        type=float,
        help="Signed deflY offset from centered (001) to centered (111) at the flat rotation.",
    )
    parser.add_argument(
        "--center-111-defly",
        type=float,
        help="deflY for the centered (111) sample at the flat rotation. Used to compute deltaY.",
    )
    parser.add_argument(
        "--delta-x",
        type=float,
        default=0.0,
        help="Signed deflX offset from centered (001) to centered (111) at the flat rotation. Leave at 0 for parallel flats.",
    )
    parser.add_argument(
        "--delta-rotation-sense",
        choices=("ccw", "cw"),
        default="ccw",
        help="How the measured 111 center offset rotates when manipulator rotation is increased.",
    )
    parser.add_argument("--max-index", type=int, default=2, choices=range(1, 7), metavar="N")
    parser.add_argument(
        "--axis-set",
        choices=("major", "all"),
        default="major",
        help="Use practical major reflections, or enumerate all low-index in-plane directions.",
    )
    parser.add_argument("--sample", choices=("both", "001", "111"), default="both")
    parser.add_argument(
        "--include-opposite",
        dest="include_opposite",
        action="store_true",
        default=True,
        help="Include the same zone axis 180 degrees away on the manipulator.",
    )
    parser.add_argument(
        "--no-include-opposite",
        dest="include_opposite",
        action="store_false",
        help="Do not include the same zone axis 180 degrees away on the manipulator.",
    )
    parser.add_argument(
        "--dedupe-deg",
        type=float,
        default=0.05,
        help="Rotation tolerance used to suppress duplicate low-index aliases.",
    )
    parser.add_argument("--csv", type=Path, help="Optional CSV output path.")
    parser.add_argument("--self-test", action="store_true", help="Run sanity checks and exit.")
    return parser.parse_args()


def gcd3(values: Iterable[int]) -> int:
    result = 0
    for value in values:
        result = math.gcd(result, abs(value))
    return result


def dot(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return sum(a_item * b_item for a_item, b_item in zip(a, b))


def cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def normalize(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(dot(vector, vector))
    if length == 0:
        raise ValueError("Cannot normalize a zero vector.")
    return tuple(value / length for value in vector)


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


def mod(value: float, period: float) -> float:
    return ((value % period) + period) % period


def close_rotation(a: float, b: float, tolerance: float) -> bool:
    delta = mod(a - b + 180.0, 360.0) - 180.0
    return abs(delta) <= tolerance


def build_basis(sample_key: str) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    sample = SAMPLES[sample_key]
    normal = normalize(tuple(float(value) for value in sample["normal"]))
    zero = normalize(tuple(float(value) for value in sample["zero"]))
    projected_zero = tuple(zero_item - dot(zero, normal) * normal_item for zero_item, normal_item in zip(zero, normal))
    u_axis = normalize(projected_zero)
    v_axis = normalize(cross(normal, u_axis))
    return u_axis, v_axis


def surface_axes(sample_key: str, max_index: int) -> list[Axis]:
    sample = SAMPLES[sample_key]
    normal = sample["normal"]
    u_axis, v_axis = build_basis(sample_key)
    axes: dict[tuple[int, int, int], Axis] = {}
    for h in range(-max_index, max_index + 1):
        for k in range(-max_index, max_index + 1):
            for l in range(-max_index, max_index + 1):
                raw = (h, k, l)
                if raw == (0, 0, 0):
                    continue
                if gcd3(raw) != 1:
                    continue
                if h * normal[0] + k * normal[1] + l * normal[2] != 0:
                    continue
                canonical = canonical_line(raw)
                if canonical in axes:
                    continue
                unit = normalize(tuple(float(value) for value in canonical))
                angle = mod(math.degrees(math.atan2(dot(unit, v_axis), dot(unit, u_axis))), 180.0)
                axes[canonical] = Axis(
                    sample=sample_key,
                    vector=canonical,
                    angle_deg=angle,
                    max_abs_index=max(abs(value) for value in canonical),
                    index_sum=sum(abs(value) for value in canonical),
                )
    return sorted(axes.values(), key=lambda item: (item.max_abs_index, item.index_sum, item.angle_deg, item.vector))


def major_axes(sample_key: str) -> list[Axis]:
    u_axis, v_axis = build_basis(sample_key)
    axes: list[Axis] = []
    for vector in MAJOR_AXES[sample_key]:
        canonical = canonical_line(vector)
        unit = normalize(tuple(float(value) for value in canonical))
        angle = mod(math.degrees(math.atan2(dot(unit, v_axis), dot(unit, u_axis))), 180.0)
        axes.append(
            Axis(
                sample=sample_key,
                vector=canonical,
                angle_deg=angle,
                max_abs_index=max(abs(value) for value in canonical),
                index_sum=sum(abs(value) for value in canonical),
            )
        )
    return sorted(axes, key=lambda item: item.angle_deg)


def axes_for_sample(sample_key: str, axis_set: str, max_index: int) -> list[Axis]:
    if axis_set == "major":
        return major_axes(sample_key)
    return surface_axes(sample_key, max_index)


def rotated_offset(delta_x: float, delta_y: float, delta_rotation_deg: float, sense: str) -> tuple[float, float]:
    sign = 1.0 if sense == "ccw" else -1.0
    theta = math.radians(sign * delta_rotation_deg)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    return (
        delta_x * cos_t - delta_y * sin_t,
        delta_x * sin_t + delta_y * cos_t,
    )


def setpoints(args: argparse.Namespace) -> list[Setpoint]:
    sample_keys = ["001", "111"] if args.sample == "both" else [args.sample]
    rows: list[Setpoint] = []
    seen: set[tuple[str, int]] = set()
    center_111_defly = getattr(args, "center_111_defly", None)
    delta_y = args.delta_y if args.delta_y is not None else center_111_defly - args.center_defly
    axis_set = getattr(args, "axis_set", "major")
    for sample_key in sample_keys:
        for axis in axes_for_sample(sample_key, axis_set, args.max_index):
            rotations = [mod(args.flat_rotation + axis.angle_deg, 360.0)]
            if args.include_opposite:
                rotations.append(mod(rotations[0] + 180.0, 360.0))
            for rotation in rotations:
                key = (sample_key, round(rotation / args.dedupe_deg))
                if key in seen:
                    continue
                if any(row.sample == sample_key and close_rotation(row.rotation_deg, rotation, args.dedupe_deg) for row in rows):
                    continue
                seen.add(key)
                if sample_key == "001":
                    offset_x = 0.0
                    offset_y = 0.0
                else:
                    offset_x, offset_y = rotated_offset(
                        args.delta_x,
                        delta_y,
                        rotation - args.flat_rotation,
                        args.delta_rotation_sense,
                    )
                rows.append(
                    Setpoint(
                        sample=sample_key,
                        axis=axis.label,
                        angle_from_flat_deg=axis.angle_deg,
                        rotation_deg=rotation,
                        deflx=args.center_deflx + offset_x,
                        defly=args.center_defly + offset_y,
                        offset_x=offset_x,
                        offset_y=offset_y,
                        index_rank=axis.index_sum,
                    )
                )
    return sorted(rows, key=lambda row: (row.rotation_deg, row.sample, row.index_rank, row.axis))


def write_csv(path: Path, rows: list[Setpoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "sample",
        "axis",
        "angle_from_flat_deg",
        "rotation_deg",
        "deflx",
        "defly",
        "offset_x",
        "offset_y",
        "index_rank",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: getattr(row, field) for field in fieldnames})


def format_rows(rows: list[Setpoint]) -> str:
    headers = ["sample", "axis", "angle", "rotation", "deflX", "deflY", "dX", "dY"]
    body = [
        [
            SAMPLES[row.sample]["label"],
            row.axis,
            f"{row.angle_from_flat_deg:7.2f}",
            f"{row.rotation_deg:8.2f}",
            f"{row.deflx:8.3f}",
            f"{row.defly:8.3f}",
            f"{row.offset_x:8.3f}",
            f"{row.offset_y:8.3f}",
        ]
        for row in rows
    ]
    widths = [len(header) for header in headers]
    for line in body:
        widths = [max(width, len(value)) for width, value in zip(widths, line)]
    header_line = "  ".join(header.ljust(width) for header, width in zip(headers, widths))
    rule = "  ".join("-" * width for width in widths)
    data_lines = ["  ".join(value.rjust(width) for value, width in zip(line, widths)) for line in body]
    return "\n".join([header_line, rule, *data_lines])


def run_self_test() -> None:
    class Args:
        flat_rotation = 10.0
        center_deflx = 100.0
        center_defly = 200.0
        delta_x = 0.0
        delta_y = -5.0
        delta_rotation_sense = "ccw"
        max_index = 1
        axis_set = "major"
        sample = "both"
        include_opposite = True
        dedupe_deg = 0.05

    axes_001 = {axis.vector for axis in surface_axes("001", 1)}
    axes_111 = {axis.vector for axis in surface_axes("111", 1)}
    assert (1, 1, 0) in axes_001
    assert (1, -1, 0) in axes_111
    rows = setpoints(Args)
    row_001 = next(row for row in rows if row.sample == "001" and abs(row.rotation_deg - 10.0) < 0.01)
    row_111 = next(row for row in rows if row.sample == "111" and abs(row.rotation_deg - 10.0) < 0.01)
    assert row_001.deflx == 100.0
    assert row_001.defly == 200.0
    assert row_111.deflx == 100.0
    assert row_111.defly == 195.0
    print("Self-test passed: axes and controller setpoint geometry look sane.")


def main() -> None:
    args = parse_args()
    if args.self_test:
        run_self_test()
        return
    missing = [
        name
        for name in ("flat_rotation", "center_deflx", "center_defly")
        if getattr(args, name) is None
    ]
    if args.delta_y is None and args.center_111_defly is None:
        missing.append("delta_y or center_111_defly")
    if missing:
        names = ", ".join("--" + name.replace("_", "-") for name in missing)
        raise SystemExit(f"Missing required calibration value(s): {names}")
    rows = setpoints(args)
    print(format_rows(rows))
    if args.csv:
        write_csv(args.csv, rows)
        print(f"\nWrote CSV: {args.csv}")


if __name__ == "__main__":
    main()
