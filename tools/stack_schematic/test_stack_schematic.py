"""Public release regressions; synthetic fixtures only. Run with unittest."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
import build_stack_schematic as stack
from provenance import write_sidecar

HERE = Path(__file__).resolve().parent


class StackTests(unittest.TestCase):
    def setUp(self):
        self.config = stack.read_json(HERE / "examples/stacks.json")
        self.registry = stack.read_json(HERE / "examples/registry.json")
        self.style = stack.read_json(HERE / "stack_style.json")

    def render(self):
        return [stack.svg(p) for p in stack.layout(self.config, self.registry, self.style)]

    def test_basis_and_synthetic_warning_always_visible(self):
        self.config["slides"][0]["mode"] = "nominal"
        svg = self.render()[0]
        for text in ["(nominal)", "(measured)", "? nm", "not experimental data", "not to scale"]:
            self.assertIn(text, svg)
        ET.fromstring(svg)

    def test_invalid_scientific_values(self):
        layer = self.config["slides"][0]["samples"][0]["layers"][0]
        original = copy.deepcopy(layer)
        for patch in [{"thickness": 0}, {"thickness": -1}, {"thickness": float("nan")},
                      {"thickness": True}, {"thickness": None}, {"basis": "unknown"},
                      {"uncertainty": -1}, {"source_ref": "missing"}, {"unit": "seconds"}]:
            with self.subTest(patch=patch):
                layer.clear(); layer.update(original); layer.update(patch)
                with self.assertRaises(ValueError): self.render()

    def test_unknown_thickness_cannot_claim_precision(self):
        layer = self.config["slides"][0]["samples"][2]["layers"][0]
        for key, value in [("uncertainty", 1), ("approximate", True)]:
            layer[key] = value
            with self.assertRaises(ValueError): self.render()
            del layer[key]

    def test_substrate_order_and_layer_limit(self):
        layers = self.config["slides"][0]["samples"][0]["layers"]
        layers.reverse()
        with self.assertRaises(ValueError): self.render()
        layers.reverse()
        layers[:] = [copy.deepcopy(layers[0]) for _ in range(9)]
        with self.assertRaises(ValueError): self.render()

    def test_registry_rejects_extra_fields_and_duplicate_labels(self):
        self.registry["samples"][0]["unrecognized"] = "sentinel"
        with self.assertRaises(ValueError): self.render()
        del self.registry["samples"][0]["unrecognized"]
        self.registry["samples"][1]["public_label"] = "Synthetic A"
        with self.assertRaises(ValueError): self.render()

    def test_pagination_and_escaping(self):
        self.config["title"] = "Synthetic <A> & B"
        self.registry["samples"].append({"key": "example-d", "public_label": "Synthetic D"})
        sample = copy.deepcopy(self.config["slides"][0]["samples"][0])
        sample["sample_key"] = "example-d"
        self.config["slides"][0]["samples"].append(sample)
        pages = self.render()
        self.assertEqual(len(pages), 2)
        for svg in pages:
            root = ET.fromstring(svg)
            self.assertIn("Synthetic <A> & B", "".join(root.itertext()))
            self.assertNotIn("<A>", svg)

    def test_long_labels_fail_instead_of_overflow(self):
        self.registry["samples"][0]["public_label"] = "W" * 23
        with self.assertRaises(ValueError): self.render()

    def test_contrast(self):
        for color in [*self.style["materials"].values(), self.style["substrate"]]:
            self.assertGreaterEqual(stack.contrast_ratio(color, stack.foreground(color)), 4.5)

    def test_sidecar_has_only_fixed_roles_hashes_and_sizes(self):
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp)
            sensitive = folder / "synthetic-sentinel-input.txt"
            sensitive.write_text("SENTINEL_DO_NOT_COPY /home/example/private C:\\Example\\hidden", encoding="utf-8")
            output = folder / "synthetic-sentinel-output.svg"
            output.write_text("<svg/>", encoding="utf-8")
            roles = {name: sensitive for name in ["config", "registry", "style", "renderer", "provenance"]}
            sidecar = write_sidecar(output, page_number=1, inputs=roles)
            raw = sidecar.read_text(encoding="utf-8")
            for token in ["SENTINEL", "synthetic-sentinel", str(folder), "/home", "C:"]:
                self.assertNotIn(token, raw)
            record = json.loads(raw)
            self.assertEqual(set(record), {"schema_version", "page_number", "output", "inputs"})
            for entry in [record["output"], *record["inputs"].values()]:
                self.assertEqual(set(entry), {"bytes", "sha256"})
            self.assertEqual(record["output"]["sha256"], hashlib.sha256(output.read_bytes()).hexdigest())
            with self.assertRaises(FileExistsError): write_sidecar(output, page_number=1, inputs=roles)

    def test_cli_reproducible_without_site_packages_and_create_only(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cmd = [sys.executable, "-S", str(HERE / "build_stack_schematic.py"),
                   "--config", str(HERE / "examples/stacks.json"),
                   "--registry", str(HERE / "examples/registry.json")]
            for name in ["first", "second"]:
                result = subprocess.run(cmd + ["--out-dir", str(root / name)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            for name in ["stack-01.svg", "stack-01.svg.provenance.json"]:
                self.assertEqual((root / "first" / name).read_bytes(), (root / "second" / name).read_bytes())
            result = subprocess.run(cmd + ["--out-dir", str(root / "first")], capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exists", result.stderr)


if __name__ == "__main__":
    unittest.main()
