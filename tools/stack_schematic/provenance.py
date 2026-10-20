"""Deterministic fingerprints. Never serializes input paths or input contents."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

ROLES = {"config", "registry", "style", "renderer", "provenance"}


def fingerprint(path):
    data = Path(path).read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_sidecar(output, *, page_number, inputs):
    if set(inputs) != ROLES:
        raise ValueError("Provenance requires the five documented input roles")
    if type(page_number) is not int or page_number < 1:
        raise ValueError("Page number must be a positive integer")
    output = Path(output)
    record = {"schema_version": 1, "page_number": page_number,
              "output": fingerprint(output),
              "inputs": {role: fingerprint(inputs[role]) for role in sorted(ROLES)}}
    # No filenames, paths, timestamps, environment, arguments, source descriptions,
    # registry keys, Git state, or arbitrary extra fields are copied into this record.
    sidecar = output.with_name(output.name + ".provenance.json")
    with sidecar.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
    return sidecar
