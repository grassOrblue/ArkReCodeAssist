from __future__ import annotations

import json
import os
import sys
from pathlib import Path


APP_NAME = "ArkReCodeAssist"
CACHE_MINUTES = 30


def data_root() -> Path:
    overridden = os.environ.get("ARK_RECODE_ASSIST_DATA")
    if overridden:
        return Path(overridden).expanduser().resolve()
    local_app_data = os.environ.get("LOCALAPPDATA")
    if not local_app_data:
        raise RuntimeError("找不到 LOCALAPPDATA，请设置 ARK_RECODE_ASSIST_DATA")
    install_state = Path(local_app_data) / APP_NAME / "install.json"
    if install_state.is_file():
        configured = json.loads(install_state.read_text(encoding="utf-8-sig")).get("data_root")
        if configured:
            return Path(configured).expanduser().resolve()
    return (Path(local_app_data) / APP_NAME / "data").resolve()


def settings_path(root: Path | None = None) -> Path:
    return (root or data_root()) / "config" / "settings.local.json"


def load_settings(root: Path | None = None) -> dict:
    path = settings_path(root)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def plugin_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent.parent
    return Path(__file__).resolve().parents[4] / "plugins" / "ark-recode-assist"


def public_knowledge_dir() -> Path:
    override = os.environ.get("ARK_RECODE_ASSIST_PUBLIC_KNOWLEDGE")
    if override:
        return Path(override).expanduser().resolve()
    return plugin_root() / "knowledge" / "public"


def lucima_data_dir(explicit: str | None = None, root: Path | None = None) -> Path:
    if explicit:
        candidate = Path(explicit).expanduser().resolve()
    elif os.environ.get("LUCIMA_TOOLS_DATA_DIR"):
        candidate = Path(os.environ["LUCIMA_TOOLS_DATA_DIR"]).expanduser().resolve()
    else:
        configured = load_settings(root).get("lucima_tools_data_dir")
        if not configured:
            raise RuntimeError("尚未配置 LucimaTools 数据目录，请运行 scripts\\install.ps1")
        candidate = Path(configured).expanduser().resolve()
    if not (candidate / "settings.json").is_file():
        raise RuntimeError(f"LucimaTools 数据目录无效：{candidate}")
    return candidate
