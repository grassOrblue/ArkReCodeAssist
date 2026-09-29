from __future__ import annotations

import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "g8-analyzer" / "src"))
sys.path.insert(0, str(ROOT / "components" / "lucima-bridge" / "src"))

from ark_recode_bridge.analyzer import AccountAnalyzer


class AccountAnalyzerTests(unittest.TestCase):
    def test_account_output_keeps_both_scores(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            backend_root = Path(temporary)
            (backend_root / "item_names.json").write_text(
                json.dumps({"100": "测试角色"}, ensure_ascii=False), encoding="utf-8"
            )
            (backend_root / "equip_ref.json").write_text(
                json.dumps({"200": {"slot": "武器", "level": 85}}, ensure_ascii=False),
                encoding="utf-8",
            )
            backend = types.ModuleType("backend")
            backend.__path__ = [str(backend_root)]
            snapshot = {
                "profile": {"name": "团长", "level": 67},
                "roles": [
                    {
                        "_id": {"$oid": "r1"},
                        "StaticID": 100,
                        "LV": 60,
                        "Star": 6,
                        "AwakenLV": 6,
                        "Skills": {"Skills": []},
                    }
                ],
                "equipment": [
                    {
                        "_id": {"$oid": "e1"},
                        "StaticID": 200,
                        "EquipRole": {"$oid": "r1"},
                        "ClassLV": 4,
                        "LV": 15,
                        "Set": "速度",
                        "SubProps": {
                            "SourceValues": [
                                {"PropertyType": "SpeedValue", "Value": 4},
                                {"PropertyType": "CriticalRate", "Value": 0.05},
                            ]
                        },
                    }
                ],
                "artifacts": [],
                "items": [],
                "teams": [],
            }
            with patch.dict(sys.modules, {"backend": backend}):
                result = AccountAnalyzer().account(snapshot)
            equipment = result["top_equipment"][0]
            self.assertEqual(equipment["lucima_score"], 24)
            self.assertEqual(equipment["g8_score"], 16.0)
            self.assertIn("不可直接互换", result["score_notice"])


if __name__ == "__main__":
    unittest.main()
