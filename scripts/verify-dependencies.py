from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    payload = json.loads((ROOT / "dependencies.lock.json").read_text(encoding="utf-8"))
    assert payload["schema_version"] == 1
    assert set(payload["dependencies"]) == {"lucima-tools", "g8-plugins"}
    for name, dependency in payload["dependencies"].items():
        assert dependency["repository"].startswith("https://github.com/")
        assert re.fullmatch(r"[0-9a-f]{40}", dependency["commit"]), name
        assert dependency["license"] in {"GPL-3.0-only", "MIT"}
    print("依赖锁定文件校验通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
