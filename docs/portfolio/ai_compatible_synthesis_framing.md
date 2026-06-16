# AI-Compatible Synthesis Framing

This public note summarizes how the MBE workflow is organized for future AI-guided or closed-loop materials discovery.

## Core Idea

Treat each epitaxial growth run as a structured information object rather than only a completed fabrication step.

## What Makes The Workflow AI-Compatible

- Growth parameters, observations, characterization outcomes, and interpretation can be captured as structured records.
- Sidecar records and database views preserve provenance across growth, characterization, analysis, and next-step planning.
- Mechanism-guided comparisons make it easier to define the experimental variables that matter.
- Information-gain framing helps prioritize which growth should be done next when sample capacity is limited.

## Public Boundary

This public note describes the workflow strategy. Raw growth notes, private sample histories, full databases, and facility-specific operational records are not included.
