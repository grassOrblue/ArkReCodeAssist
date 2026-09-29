from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class PluginContractTests(unittest.TestCase):
    def test_explicit_invocation_only(self) -> None:
        plugin = ROOT / "plugins" / "ark-recode-assist"
        manifest = json.loads((plugin / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
        metadata = (plugin / "skills" / "ark-recode-assist" / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertEqual(manifest["interface"]["displayName"], "星陨助手")
        self.assertIn("allow_implicit_invocation: false", metadata)

    def test_repository_marketplace_uses_distinct_name(self) -> None:
        marketplace = json.loads(
            (ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8")
        )
        self.assertEqual(marketplace["name"], "ark-recode-assist-marketplace")

    def test_private_files_are_ignored(self) -> None:
        ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
        for value in ("settings.local.json", "account-cache/", "*.snapshot.json"):
            self.assertIn(value, ignore)


if __name__ == "__main__":
    unittest.main()
