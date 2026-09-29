from __future__ import annotations

import importlib.resources
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from g8_analyzer import calculate_sub_score, evaluate_gear_tier, predict_potential

from .snapshot import lucima_equipment_score, oid, snapshot_counts


PROPERTY_NAMES = {
    "AttackValue": "攻击力",
    "AttackRate": "攻击力",
    "DefenceValue": "防御力",
    "DefenceRate": "防御力",
    "HPValue": "生命力",
    "HPRate": "生命力",
    "SpeedValue": "速度",
    "CriticalRate": "暴击率",
    "CriticalDamageRate": "暴击伤害",
    "EffectHitRate": "状态命中",
    "ResistanceRate": "状态抗性",
}


def stat_value(property_type: str, value: float) -> dict[str, str]:
    is_rate = property_type.endswith("Rate")
    number = value * 100 if is_rate else value
    return {
        "name": PROPERTY_NAMES.get(property_type, property_type),
        "value": f"{number:g}" + ("%" if is_rate else ""),
    }


def g8_equipment_score(equipment: dict[str, Any]) -> float:
    total = 0.0
    for prop in (equipment.get("SubProps") or {}).get("SourceValues") or []:
        stat = stat_value(str(prop.get("PropertyType") or ""), float(prop.get("Value") or 0))
        total += calculate_sub_score(stat["name"], stat["value"])
    return round(total, 1)


def role_skills(role: dict[str, Any]) -> str:
    return "/".join(
        str(skill.get("Level") or 0)
        for skill in (role.get("Skills") or {}).get("Skills", [])
    )


class AccountAnalyzer:
    def __init__(self) -> None:
        import backend

        backend_root = Path(next(iter(backend.__path__)))
        self.names = json.loads((backend_root / "item_names.json").read_text(encoding="utf-8"))
        self.equip_ref = json.loads((backend_root / "equip_ref.json").read_text(encoding="utf-8"))
        self.character_db = self._load_character_db()

    @staticmethod
    def _load_character_db() -> dict[str, Any]:
        try:
            resource = importlib.resources.files("g8_analyzer").joinpath("data/characters.json")
            return json.loads(resource.read_text(encoding="utf-8"))
        except (FileNotFoundError, ModuleNotFoundError):
            return {}

    def equipment_rows(self, snapshot: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for equipment in snapshot.get("equipment") or []:
            ref = self.equip_ref.get(str(equipment.get("StaticID"))) or {}
            g8_score = g8_equipment_score(equipment)
            grade = "传说" if int(equipment.get("ClassLV") or 0) == 4 else "史诗"
            sub_stats = [
                stat_value(str(prop.get("PropertyType") or ""), float(prop.get("Value") or 0))
                for prop in (equipment.get("SubProps") or {}).get("SourceValues") or []
            ]
            expected, maximum = predict_potential(
                g8_score, int(equipment.get("LV") or 0), sub_stats, grade
            )
            rows.append(
                {
                    "id": oid(equipment.get("_id")),
                    "static_id": equipment.get("StaticID"),
                    "slot": ref.get("slot", "未知"),
                    "level": ref.get("level"),
                    "set": equipment.get("Set"),
                    "enhance": int(equipment.get("LV") or 0),
                    "equipped_role_id": oid(equipment.get("EquipRole")),
                    "lucima_score": lucima_equipment_score(equipment),
                    "g8_score": g8_score,
                    "g8_tier": evaluate_gear_tier(g8_score),
                    "g8_expected_at_15": expected,
                    "g8_limit_at_15": maximum,
                    "sub_stats": sub_stats,
                }
            )
        rows.sort(key=lambda row: (-row["lucima_score"], -row["g8_score"]))
        return rows

    def role_rows(
        self,
        snapshot: dict[str, Any],
        gear_rows: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        gear_rows = gear_rows if gear_rows is not None else self.equipment_rows(snapshot)
        equipment_by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in gear_rows:
            equipment_by_role[row["equipped_role_id"]].append(row)
        artifacts_by_role: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for artifact in snapshot.get("artifacts") or []:
            artifacts_by_role[oid(artifact.get("EquipRole"))].append(artifact)

        roles = []
        for role in snapshot.get("roles") or []:
            role_id = oid(role.get("_id"))
            name = self.names.get(str(role.get("StaticID")), str(role.get("StaticID")))
            gear = equipment_by_role.get(role_id, [])
            artifact = (artifacts_by_role.get(role_id) or [{}])[0]
            guide_available = name in self.character_db
            roles.append(
                {
                    "name": name,
                    "static_id": role.get("StaticID"),
                    "level": int(role.get("LV") or 0),
                    "star": int(role.get("Star") or 0),
                    "awaken": int(role.get("AwakenLV") or 0),
                    "imprint": int(role.get("ImprintLV") or 0),
                    "skills": role_skills(role),
                    "gear_count": len(gear),
                    "gear_plus15": sum(item["enhance"] == 15 for item in gear),
                    "lucima_gear_score": sum(item["lucima_score"] for item in gear),
                    "g8_gear_score": round(sum(item["g8_score"] for item in gear), 1),
                    "artifact": self.names.get(
                        str(artifact.get("StaticID")), artifact.get("StaticID") or None
                    ),
                    "artifact_level": int(artifact.get("LV") or 0),
                    "guide_available": guide_available,
                }
            )
        roles.sort(
            key=lambda row: (
                -row["level"],
                -row["awaken"],
                -row["gear_plus15"],
                -row["lucima_gear_score"],
                row["name"],
            )
        )
        return roles

    def account(self, snapshot: dict[str, Any], query: str = "") -> dict[str, Any]:
        gear_rows = self.equipment_rows(snapshot)
        roles = self.role_rows(snapshot, gear_rows)
        missing_guides = [
            role["name"]
            for role in roles
            if role["level"] >= 50 and not role["guide_available"]
        ]
        return {
            "query": query,
            "profile": snapshot.get("profile", {}),
            "counts": snapshot_counts(snapshot),
            "trained_roles": roles[:10],
            "top_equipment": gear_rows[:8],
            "guide_coverage": {
                "available_for_owned": sum(role["guide_available"] for role in roles),
                "owned": len(roles),
                "missing_high_level": sorted(set(missing_guides))[:10],
            },
            "score_notice": "lucima_score与g8_score是独立算法，不可直接互换",
        }

    def character(self, snapshot: dict[str, Any], name: str, query: str = "") -> dict[str, Any]:
        matches = [row for row in self.role_rows(snapshot) if row["name"] == name]
        if not matches:
            raise KeyError(f"账号快照中没有找到角色：{name}")
        role = matches[0]
        role_data = next(
            item for item in snapshot["roles"] if item.get("StaticID") == role["static_id"]
        )
        role_id = oid(role_data.get("_id"))
        gear = [item for item in self.equipment_rows(snapshot) if item["equipped_role_id"] == role_id]
        return {
            "query": query,
            "role": role,
            "equipment": gear,
            "guide": self.character_db.get(name),
            "guide_status": "available" if name in self.character_db else "insufficient",
            "score_notice": "lucima_score与g8_score是独立算法，不可直接互换",
        }

    def equipment(self, snapshot: dict[str, Any], limit: int = 20, query: str = "") -> dict[str, Any]:
        return {
            "query": query,
            "equipment": self.equipment_rows(snapshot)[: max(1, min(100, limit))],
            "score_notice": "lucima_score与g8_score是独立算法，不可直接互换",
        }
