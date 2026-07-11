from __future__ import annotations

import sys
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from scan_secrets import scan_filesystem, scan_repository  # noqa: E402


class SecretScanTest(unittest.TestCase):
    def test_repository_and_history_are_clean(self) -> None:
        self.assertEqual(scan_repository(ROOT, history=True), [])

    def test_detects_extended_api_key_shape_without_echoing_value(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            secret = "sk-" + "example.with/slash+and=padding123456"
            (root / "config.txt").write_text(f"api_key={secret}\n", encoding="utf-8")
            findings = scan_filesystem(root)
            rendered = repr(findings)
            self.assertTrue(findings)
            self.assertNotIn(secret, rendered)
            self.assertIn("openai_style_key", rendered)

    def test_detects_sensitive_filename(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env").write_text("SAFE_PLACEHOLDER=true\n", encoding="utf-8")
            findings = scan_filesystem(root)
            self.assertTrue(any(item.kind == "sensitive_filename" for item in findings))

    def test_detects_untracked_nonignored_secret(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            secret = "sk-" + "untracked.with/slash+padding123456"
            (root / "pending.txt").write_text(f"api_key={secret}\n", encoding="utf-8")
            findings = scan_repository(root)
            self.assertTrue(any(item.path == "pending.txt" for item in findings))
            self.assertNotIn(secret, repr(findings))

    def test_does_not_follow_symlink_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "root"
            root.mkdir()
            target = Path(temp_dir) / "outside.txt"
            secret = "sk-" + "outside.with/slash+padding123456"
            target.write_text(secret, encoding="utf-8")
            (root / "linked.txt").symlink_to(target)
            findings = scan_filesystem(root)
            self.assertTrue(any(item.kind == "symlink" for item in findings))
            self.assertNotIn(secret, repr(findings))

    def test_detects_sensitive_filename_removed_from_git_history(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=root, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=root, check=True)
            env_file = root / ".env"
            env_file.write_text("SAFE_PLACEHOLDER=true\n", encoding="utf-8")
            subprocess.run(["git", "add", ".env"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "add fixture"], cwd=root, check=True)
            env_file.unlink()
            subprocess.run(["git", "add", "-u"], cwd=root, check=True)
            subprocess.run(["git", "commit", "-qm", "remove fixture"], cwd=root, check=True)
            findings = scan_repository(root, history=True)
            self.assertTrue(
                any(item.kind == "sensitive_filename" and item.source == "git-history-name" for item in findings)
            )


if __name__ == "__main__":
    unittest.main()
