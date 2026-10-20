# RHEED Geometry Visualizer

Status: `Interactive geometry demonstration`

Explore how sample position, beam steering, and holder rotation affect RHEED alignment for co-mounted (001) and (111) samples.

These tools currently serve as pedagogical and conceptual aids to in situ characterization. Formalizing their underlying geometry, assumptions, and decision logic in scripts makes that reasoning explicit, testable, and reproducible, laying a foundation for integrating automated workflows into experimental materials research.

## Interactive Demo

[Open the RHEED geometry visualizer](geometry-visualizer.html)

Start with the reference geometry, scan the beam onto the offset sample, then compare the corrected holder rotation. The display shows beam azimuth, beam footprint, and alignment with candidate crystal zone axes. Advanced controls provide zone-axis candidates and CSV export.

The self-contained HTML uses illustrative sample offsets and example calibration values. It is a geometry and planning demonstration; the displayed values are not calibrated equipment setpoints.

## Historical Demo and Planning Tools

- [Historical zone-axis finder](zone-axis-finder.html)
- [Historical example setpoint table](example-setpoints.csv)
- [`zone_axis_finder.py`](../../../tools/rheed/zone_axis_finder.py)
- [`double_mount_setpoints.py`](../../../tools/rheed/double_mount_setpoints.py)

These historical tools remain available for reference and use their own assumed geometry and calibration. Their tables are illustrative, not calibrated equipment commands. The current interactive geometry visualizer is the primary demonstration.

## Public Scope

This page publishes a standalone geometry model with non-sensitive example inputs. It includes no raw growth records, private instrument exports, or facility operating procedures.
