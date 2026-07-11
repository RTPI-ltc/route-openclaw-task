from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class GitignoreTest(unittest.TestCase):
    def test_sensitive_local_paths_are_ignored(self) -> None:
        ignored = (
            ".env",
            ".env.production",
            ".envrc",
            "secrets/provider.txt",
            "credentials.json",
            "client_secret_local.json",
            "server.pem",
            "production.tfvars",
            "terraform.tfstate.backup",
            ".openclaw/config.json",
            ".codex/auth.json",
            ".claude/settings.local.json",
            ".aws/credentials",
            "runtime.log",
        )
        for relative in ignored:
            result = subprocess.run(
                ["git", "check-ignore", "--no-index", "-q", relative],
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 0, relative)

    def test_sanitized_templates_and_plugin_manifests_remain_trackable(self) -> None:
        trackable = (
            ".env.example",
            ".env.production.example",
            "integrations/codex/.codex-plugin/plugin.json",
            "integrations/claude-code/.claude-plugin/plugin.json",
        )
        for relative in trackable:
            result = subprocess.run(
                ["git", "check-ignore", "--no-index", "-q", relative],
                cwd=ROOT,
                check=False,
            )
            self.assertEqual(result.returncode, 1, relative)


if __name__ == "__main__":
    unittest.main()
