# Growth-Day Assistant Public Summary

Status: `Public summary`

The growth-day assistant is a private workflow for planning and executing MBE growth runs. The public version documents the transferable research pattern without exposing facility-specific procedures.

## Public Scope

- turn run goals into checklists
- separate known values from assumptions
- preserve recipe provenance and growth-day observations
- summarize database-parsed historical, user-written notes on debugging and calibrating in situ monitoring, including RHEED observations and thermometry landmarks
- use calibration scripts to estimate growth rate (GR) and effusion-cell temperature targets from sourced context
- use zone-axis and RHEED-geometry scripts to identify crystal zone-axis locations for growths involving spatially separated samples with disparate symmetries
- support public-safe recipe-scripting logic reviews without exporting facility-specific recipe code
- connect database infrastructure to recipe-step drafting, translating planned run logic into machine-specific recipe syntax patterns for the local MBE control environment
- record deviations and post-run interpretation
- connect growth parameters to characterization and database records

## Private Boundary

The private assistant may reference lab-specific recipe names, facility procedures, raw growth notes, database-parsed historical notes, calibration scripts, in situ monitoring context, and operator context. Those details are not exported here.

## Why It Matters

The assistant reflects a larger research design principle: each synthesis run should become a structured information object that can be reviewed, queried, converted into safe recipe-step logic, and used in future experiment planning.
