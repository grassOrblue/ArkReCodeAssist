from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
IGNORED_PARTS = {".git", ".deps", ".venv", "build", "dist", "artifacts", "__pycache__"}
FORBIDDEN_FILES = {"settings.local.json", "snapshot.json", "latest.json", "knowledge.db"}
SECRET_VALUE = re.compile(
    r'(?i)"(?:access_token|refresh_token|password|session|authorization)"\s*:\s*"(?!example|redacted|<)[^"\r\n]{8,}"'
)
JWT_VALUE = re.compile(r"\beyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")


def main() -> int:
    failures: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or any(part in IGNORED_PARTS for part in path.parts):
            continue
        if path.name.lower() in FORBIDDEN_FILES:
            failures.append(f"禁止提交的文件：{path.relative_to(ROOT)}")
            continue
        if path.suffix.lower() in {".exe", ".dll", ".zip", ".png", ".ico"}:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        if SECRET_VALUE.search(text) or JWT_VALUE.search(text):
            failures.append(f"疑似凭据：{path.relative_to(ROOT)}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print("隐私扫描通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
