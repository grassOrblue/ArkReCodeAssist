from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    plugin_root = ROOT / "plugins" / "ark-recode-assist"
    manifest = json.loads((plugin_root / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8"))
    marketplace = json.loads((ROOT / ".agents" / "plugins" / "marketplace.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "ark-recode-assist"
    assert re.fullmatch(r"\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?", manifest["version"])
    assert manifest["interface"]["displayName"] == "星陨助手"
    assert (plugin_root / "skills" / "ark-recode-assist" / "SKILL.md").is_file()
    metadata = (plugin_root / "skills" / "ark-recode-assist" / "agents" / "openai.yaml").read_text(encoding="utf-8")
    assert "allow_implicit_invocation: false" in metadata
    entries = {item["name"]: item for item in marketplace["plugins"]}
    entry = entries["ark-recode-assist"]
    assert entry["source"]["path"] == "./plugins/ark-recode-assist"
    assert entry["policy"] == {"installation": "AVAILABLE", "authentication": "ON_INSTALL"}
    print("插件结构校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
