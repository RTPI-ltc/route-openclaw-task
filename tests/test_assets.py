from __future__ import annotations

import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AssetTest(unittest.TestCase):
    def test_models_are_json_without_raw_evaluation_examples(self) -> None:
        for name in ("profile-policy-model.json", "tool-family-model.json"):
            payload = json.loads((ROOT / "assets" / name).read_text(encoding="utf-8"))
            self.assertTrue(payload["model_type"].startswith("multinomial_naive_bayes"))
            self.assertNotIn("evaluation", payload)

    def test_profile_model_has_release_privacy_metadata(self) -> None:
        payload = json.loads((ROOT / "assets/profile-policy-model.json").read_text(encoding="utf-8"))
        self.assertFalse(payload["release_metadata"]["raw_examples_included"])
        self.assertNotIn("terminalworld_safe_network", payload["training_summary"]["source_counts"])

    def test_model_assets_have_no_sensitive_literals(self) -> None:
        patterns = [
            re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
            re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b"),
            re.compile(r"BEGIN [A-Z ]*PRIVATE KEY"),
            re.compile(r"(^|[^A-Za-z])sk-[A-Za-z0-9_\-]{16,}"),
        ]
        for path in (ROOT / "assets").glob("*.json"):
            text = path.read_text(encoding="utf-8")
            for pattern in patterns:
                self.assertIsNone(pattern.search(text), f"{pattern.pattern} found in {path.name}")


if __name__ == "__main__":
    unittest.main()
