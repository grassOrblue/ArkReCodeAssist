from __future__ import annotations

import hashlib
import json
import math
import os
import time
from pathlib import Path
from typing import Any

from .config import CACHE_MINUTES, data_root, lucima_data_dir


SECRET_KEY_FRAGMENTS = (
    "password",
    "passwd",
    "access_token",
    "refresh_token",
    "session",
    "authorization",
    "cookie",
    "email",
)


def oid(value: Any) -> str:
    if isinstance(value, dict):
        return str(value.get("$oid") or "")
    return str(value or "")


def assert_no_secret_keys(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).lower().replace("-", "_")
            if any(fragment in normalized for fragment in SECRET_KEY_FRAGMENTS):
                raise RuntimeError(f"快照包含禁止字段：{path}.{key}")
            assert_no_secret_keys(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            assert_no_secret_keys(child, f"{path}[{index}]")


def sanitize_account_state(state: dict[str, Any]) -> dict[str, Any]:
    info = state.get("Info") or {}
    items = [
        {"StaticID": item.get("StaticID"), "Count": item.get("Count", 0)}
        for item in (state.get("ItemContainer") or {}).get("Items", [])
    ]
    snapshot = {
        "schema_version": 1,
        "profile": {
            "name": info.get("Name"),
            "level": info.get("LV"),
            "leader": info.get("LeaderSID"),
        },
        "roles": (state.get("RoleDataContainer") or {}).get("Roles", []),
        "equipment": (state.get("EquipmentContainer") or {}).get("Datas", []),
        "artifacts": (state.get("Artifacts") or {}).get("Datas", []),
        "items": items,
        "teams": (state.get("Teams") or {}).get("Settings", []),
    }
    assert_no_secret_keys(snapshot)
    return snapshot


class SnapshotCache:
    def __init__(self, root: Path | None = None) -> None:
        self.root = (root or data_root()) / "account-cache"

    def _paths(self, account_hash_value: str = "default") -> tuple[Path, Path]:
        directory = self.root / account_hash_value
        return directory / "latest.json", directory / "metadata.json"

    def write(self, snapshot: dict[str, Any], account_hash_value: str) -> dict[str, Any]:
        assert_no_secret_keys(snapshot)
        snapshot_path, metadata_path = self._paths(account_hash_value)
        snapshot_path.parent.mkdir(parents=True, exist_ok=True)
        now = int(time.time())
        metadata = {
            "schema_version": 1,
            "account_hash": account_hash_value,
            "created_at": now,
            "expires_at": now + CACHE_MINUTES * 60,
            "counts": snapshot_counts(snapshot),
        }
        atomic_json(snapshot_path, snapshot)
        atomic_json(metadata_path, metadata)
        atomic_json(self.root / "current.json", {"account_hash": account_hash_value})
        return metadata

    def read(self) -> tuple[dict[str, Any], dict[str, Any]]:
        current = json.loads((self.root / "current.json").read_text(encoding="utf-8"))
        snapshot_path, metadata_path = self._paths(current["account_hash"])
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert_no_secret_keys(snapshot)
        return snapshot, metadata

    def status(self) -> dict[str, Any]:
        try:
            snapshot, metadata = self.read()
        except (FileNotFoundError, KeyError, json.JSONDecodeError):
            return {"available": False, "fresh": False, "cache_minutes": CACHE_MINUTES}
        now = int(time.time())
        return {
            "available": True,
            "fresh": now < int(metadata["expires_at"]),
            "age_seconds": max(0, now - int(metadata["created_at"])),
            "expires_at": metadata["expires_at"],
            "profile": snapshot.get("profile", {}),
            "counts": metadata.get("counts", snapshot_counts(snapshot)),
            "cache_minutes": CACHE_MINUTES,
        }


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(temporary, path)


def snapshot_counts(snapshot: dict[str, Any]) -> dict[str, int]:
    return {
        "roles": len(snapshot.get("roles") or []),
        "equipment": len(snapshot.get("equipment") or []),
        "artifacts": len(snapshot.get("artifacts") or []),
        "items": len(snapshot.get("items") or []),
        "teams": len(snapshot.get("teams") or []),
    }


def account_hash(account: str) -> str:
    return hashlib.sha256(account.strip().lower().encode("utf-8")).hexdigest()[:16]


class LucimaSnapshotProvider:
    def __init__(
        self,
        lucima_dir: str | None = None,
        cache: SnapshotCache | None = None,
        root: Path | None = None,
    ) -> None:
        self.lucima_dir = lucima_data_dir(lucima_dir, root)
        self.cache = cache or SnapshotCache(root)

    def refresh(self, account: str | None = None) -> dict[str, Any]:
        os.environ["ARK_DATA_DIR"] = str(self.lucima_dir)
        os.environ.setdefault("ARK_PLATFORM", "windows")
        try:
            from backend import config as lucima_config
            from backend.game_client import GameClient
            from backend.portal import access_token_needs_refresh, portal_refresh_v2
        except ImportError as exc:
            raise RuntimeError("桥接程序缺少LucimaTools运行组件，请重新安装Release") from exc

        saved = lucima_config.load_accounts()
        if account:
            record = saved.get(account)
            if not record:
                raise RuntimeError("指定账号没有本地登录令牌")
            selected_account = account
        else:
            if len(saved) != 1:
                raise RuntimeError("本地保存账号数量不是1，请通过 --account 指定")
            selected_account, record = next(iter(saved.items()))
        if record.get("auth_error") or not record.get("auth"):
            raise RuntimeError("本地登录令牌不可用，请先在LucimaTools中重新登录")
        auth = dict(record["auth"])

        def refresh_auth(force: bool = False) -> dict[str, Any]:
            nonlocal auth
            if force or access_token_needs_refresh(str(auth.get("access_token") or "")):
                auth = portal_refresh_v2(auth)
                lucima_config.save_account(selected_account, auth=auth)
            return auth

        client = GameClient(
            auth["access_token"],
            login_id=auth["user_id"],
            login_common=lucima_config.android_login_common(auth["device_id"]),
            auth_refresher=refresh_auth,
        )
        try:
            snapshot = sanitize_account_state(client.bootstrap())
        finally:
            client.close()
        metadata = self.cache.write(snapshot, account_hash(selected_account))
        return {"snapshot": snapshot, "metadata": metadata}


LUCIMA_SCORE_FACTORS = {
    "AttackValue": 0.17,
    "AttackRate": 1.8,
    "DefenceValue": 0.2,
    "DefenceRate": 1.8,
    "HPValue": 0.05,
    "HPRate": 1.5,
    "SpeedValue": 3.5,
    "CriticalRate": 2.0,
    "CriticalDamageRate": 1.8,
    "EffectHitRate": 1.25,
    "ResistanceRate": 1.25,
}


def lucima_equipment_score(equipment: dict[str, Any]) -> int:
    total = 0.0
    values = (equipment.get("SubProps") or {}).get("SourceValues") or []
    for prop in values:
        kind = str(prop.get("PropertyType") or "")
        value = float(prop.get("Value") or 0)
        if kind.endswith("Rate"):
            value *= 100
        total += value * LUCIMA_SCORE_FACTORS.get(kind, 0)
    return int(math.ceil(total - 0.5))
