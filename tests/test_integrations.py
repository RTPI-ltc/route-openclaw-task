from __future__ import annotations

import hashlib
import json
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from benchmark_integrations import benchmark  # noqa: E402
from build_integrations import build_integrations  # noqa: E402
from validate_integrations import validate_integrations  # noqa: E402


class IntegrationTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="route-integrations-")
        self.output = Path(self.temp.name)
        self.result = build_integrations(ROOT, self.output)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_all_bundles_validate(self) -> None:
        self.assertEqual(validate_integrations(ROOT, self.output), [])

    def test_contract_benchmark_has_exact_parity(self) -> None:
        result = benchmark(ROOT, self.output)
        self.assertEqual(result["case_generation"]["cases"], 240)
        for metrics in result["hosts"].values():
            self.assertEqual(metrics["exact_core_parity"], 1.0)
            self.assertEqual(metrics["schema_valid_rate"], 1.0)
            self.assertEqual(metrics["safety_invariant_rate"], 1.0)

    def test_archives_are_reproducible(self) -> None:
        second = self.output / "second"
        other = build_integrations(ROOT, second)
        for name, first_bundle in self.result["bundles"].items():
            self.assertEqual(first_bundle["sha256"], other["bundles"][name]["sha256"])

    def test_archives_have_portable_metadata(self) -> None:
        for bundle in self.result["bundles"].values():
            archive = Path(bundle["archive"])
            with tarfile.open(archive, "r:gz") as handle:
                members = handle.getmembers()
            self.assertTrue(members)
            self.assertTrue(all(member.uid == 0 and member.gid == 0 for member in members))
            self.assertTrue(all(member.mtime == 0 for member in members))
            self.assertFalse(any("__pycache__" in member.name or member.name.endswith(".pyc") for member in members))

    def test_behavioral_core_matches_v01_lock(self) -> None:
        contract = json.loads((ROOT / "integrations/compatibility.json").read_text(encoding="utf-8"))
        for relative, expected in contract["core_skill"]["locked_files"].items():
            actual = hashlib.sha256((ROOT / relative).read_bytes()).hexdigest()
            self.assertEqual(actual, expected, relative)

    def test_openclaw_adapter_does_not_log_raw_subprocess_errors(self) -> None:
        index = (ROOT / "integrations/openclaw-native/index.mjs").read_text(encoding="utf-8")
        self.assertNotIn("error.message", index)
        self.assertNotIn("String(error)", index)
        self.assertIn("errorCategory(error)", index)

    def test_canonical_and_legacy_skill_names_are_packaged(self) -> None:
        version = "0.3.0"
        for host in ("openclaw-native", "codex", "claude-code"):
            bundle = self.output / f"task-compass-{host}-v{version}"
            self.assertTrue((bundle / "skills/task-compass/SKILL.md").is_file())
            self.assertTrue((bundle / "skills/route-openclaw-task/SKILL.md").is_file())


if __name__ == "__main__":
    unittest.main()
