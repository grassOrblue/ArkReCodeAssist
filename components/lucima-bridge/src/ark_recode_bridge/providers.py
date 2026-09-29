from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class AccountSnapshotProvider(Protocol):
    def refresh(self, account: str | None = None) -> dict[str, Any]: ...


class AnalyzerProvider(Protocol):
    def analyze(self, snapshot: dict[str, Any], query: str = "") -> dict[str, Any]: ...


class KnowledgeSourceProvider(Protocol):
    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]: ...


class GameActionProvider(Protocol):
    def plan(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]: ...

    def execute(self, confirmation_id: str) -> dict[str, Any]: ...


class DisabledGameActionProvider:
    """首版明确禁用所有游戏写操作。"""

    def plan(self, action: str, parameters: dict[str, Any]) -> dict[str, Any]:
        return {
            "supported": False,
            "action": action,
            "reason": "首版只读；尚未验证强化或合成的真实协议与幂等性",
        }

    def execute(self, confirmation_id: str) -> dict[str, Any]:
        raise RuntimeError("首版禁止执行游戏写操作")


def provider_inventory(executable: Path) -> dict[str, Any]:
    return {
        "account_snapshot": {"name": "LucimaTools", "mode": "read-only"},
        "analyzers": ["LucimaTools equipment score", "G8 equipment score"],
        "knowledge": ["public JSON", "local SQLite", "pending review"],
        "game_actions": {"enabled": False, "provider": "DisabledGameActionProvider"},
        "runtime": str(executable),
    }
