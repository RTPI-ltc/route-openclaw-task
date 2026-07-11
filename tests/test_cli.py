from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROUTER = ROOT / "scripts" / "route_task.py"
VALIDATOR = ROOT / "scripts" / "validate_route.py"


class CliTest(unittest.TestCase):
    def test_single_goal_cli(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROUTER), "--goal", "Run pytest in the current repository.", "--pretty"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["schema_version"], "1.0")
        self.assertIn("command_runner", payload["execution_tools"])

    def test_batch_cli_and_validator(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "routes.jsonl"
            subprocess.run(
                [
                    sys.executable,
                    str(ROUTER),
                    "--input-jsonl",
                    str(ROOT / "examples" / "tasks.jsonl"),
                    "--output-jsonl",
                    str(output),
                ],
                cwd=ROOT,
                check=True,
            )
            rows = [json.loads(line) for line in output.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(rows), 6)
            self.assertEqual([row["task_id"] for row in rows], [
                "readonly-audit",
                "local-repair",
                "production-deploy",
                "catalog-contact",
                "catalog-distance",
                "catalog-missing-dependency",
            ])
            subprocess.run([sys.executable, str(VALIDATOR), str(output)], cwd=ROOT, check=True)

    def test_empty_goal_fails_without_traceback(self) -> None:
        result = subprocess.run(
            [sys.executable, str(ROUTER), "--goal", ""],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("goal must not be empty", result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()

