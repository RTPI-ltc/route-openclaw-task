from __future__ import annotations

import sys
import tempfile
import subprocess
import tarfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from validate_skill import validate  # noqa: E402
from verify_release import verify  # noqa: E402


class ReleaseTest(unittest.TestCase):
    def test_skill_schema(self) -> None:
        self.assertEqual(validate(ROOT), [])

    def test_release_verifier(self) -> None:
        self.assertEqual(verify(ROOT), [])

    def test_raw_benchmark_rows_are_not_packaged(self) -> None:
        forbidden_names = {"tasks.json", "tasks.jsonl", "train.json", "holdout.json"}
        benchmark_files = {path.name for path in (ROOT / "benchmarks").rglob("*") if path.is_file()}
        self.assertFalse(forbidden_names.intersection(benchmark_files))

    def test_openclaw_metadata_is_single_line_json(self) -> None:
        lines = (ROOT / "SKILL.md").read_text(encoding="utf-8").splitlines()
        metadata_lines = [line for line in lines if line.startswith("metadata:")]
        self.assertEqual(len(metadata_lines), 1)
        self.assertTrue(metadata_lines[0].startswith("metadata: {"))

    def test_validator_rejects_multiline_metadata(self) -> None:
        with tempfile.TemporaryDirectory(prefix="route-openclaw-task-") as temp_dir:
            root = Path(temp_dir) / "route-openclaw-task"
            root.mkdir()
            (root / "SKILL.md").write_text(
                "---\n"
                "name: route-openclaw-task\n"
                "description: Test routing skill.\n"
                "license: MIT\n"
                "metadata:\n"
                "  openclaw: {}\n"
                "---\n",
                encoding="utf-8",
            )
            errors = validate(root)
            self.assertTrue(any("multiline YAML" in error for error in errors))

    def test_validator_accepts_declared_repository_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "Task-Compass-Skill"
            root.mkdir()
            (root / "SKILL.md").write_text(
                "---\n"
                "name: task-compass\n"
                "description: Test routing skill.\n"
                "license: MIT\n"
                'metadata: {"repository_names":["Task-Compass-Skill"],"openclaw":{"requires":{"bins":["python3"]}}}\n'
                "---\n",
                encoding="utf-8",
            )
            self.assertEqual(validate(root), [])

    def test_release_archive_has_portable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            command = [
                sys.executable,
                str(ROOT / "scripts/build_archive.py"),
                "--output-dir",
                temp_dir,
            ]
            subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
            archive = Path(temp_dir) / "task-compass-v0.3.0.tar.gz"
            with tarfile.open(archive, "r:gz") as handle:
                members = handle.getmembers()
            self.assertGreater(len(members), 30)
            self.assertTrue(all(member.uid == 0 and member.gid == 0 for member in members))
            self.assertTrue(all(member.mtime == 0 for member in members))
            for member in members:
                expected_mode = (
                    0o755
                    if member.isdir() or ("/scripts/" in member.name and member.name.endswith(".py"))
                    else 0o644
                )
                self.assertEqual(member.mode, expected_mode, member.name)

    def test_release_archive_excludes_gitignored_environment_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            output = Path(temp_dir) / "output"
            root.mkdir()
            (root / ".gitignore").write_text(".env\n", encoding="utf-8")
            (root / "README.md").write_text("safe\n", encoding="utf-8")
            (root / ".env").write_text("LOCAL_ONLY=true\n", encoding="utf-8")
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_archive.py"),
                    "--root",
                    str(root),
                    "--output-dir",
                    str(output),
                    "--version",
                    "0.3.0",
                ],
                check=True,
                capture_output=True,
                text=True,
            )
            with tarfile.open(output / "task-compass-v0.3.0.tar.gz", "r:gz") as handle:
                names = {member.name for member in handle.getmembers()}
            self.assertIn("task-compass/README.md", names)
            self.assertNotIn("task-compass/.env", names)

    def test_release_archive_blocks_nonignored_secret_without_echoing_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "source"
            output = Path(temp_dir) / "output"
            root.mkdir()
            sample = "sk-" + "not-safe.with/slash+padding123456"
            (root / "config.txt").write_text(f"api_key={sample}\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts/build_archive.py"),
                    "--root",
                    str(root),
                    "--output-dir",
                    str(output),
                    "--version",
                    "0.3.0",
                ],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("release archive secret scan failed", result.stderr)
            self.assertNotIn(sample, result.stderr)

    def test_release_archive_is_reproducible(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "first"
            second = Path(temp_dir) / "second"
            for output in (first, second):
                subprocess.run(
                    [
                        sys.executable,
                        str(ROOT / "scripts/build_archive.py"),
                        "--output-dir",
                        str(output),
                    ],
                    cwd=ROOT,
                    check=True,
                    capture_output=True,
                    text=True,
                )
            self.assertEqual(
                (first / "task-compass-v0.3.0.tar.gz").read_bytes(),
                (second / "task-compass-v0.3.0.tar.gz").read_bytes(),
            )


if __name__ == "__main__":
    unittest.main()
