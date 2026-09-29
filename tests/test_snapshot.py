from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "lucima-bridge" / "src"))

from ark_recode_bridge.snapshot import (
    SnapshotCache,
    assert_no_secret_keys,
    lucima_equipment_score,
    sanitize_account_state,
)
from ark_recode_bridge.config import data_root


class SnapshotTests(unittest.TestCase):
    def test_installer_pointer_selects_custom_data_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            local_app_data = Path(temporary)
            custom_root = local_app_data / "portable-data"
            state_dir = local_app_data / "ArkReCodeAssist"
            state_dir.mkdir()
            (state_dir / "install.json").write_text(
                json.dumps({"schema_version": 1, "data_root": str(custom_root)}),
                encoding="utf-8",
            )
            environment = {"LOCALAPPDATA": str(local_app_data)}
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual(data_root(), custom_root.resolve())

    def test_sanitize_keeps_analysis_data_only(self) -> None:
        state = {
            "Info": {"Name": "测试团长", "LV": 67, "LeaderSID": 1001},
            "RoleDataContainer": {"Roles": [{"StaticID": 1001}]},
            "EquipmentContainer": {"Datas": [{"StaticID": 2001}]},
            "Artifacts": {"Datas": []},
            "ItemContainer": {"Items": [{"StaticID": 3001, "Count": 2, "Private": "drop"}]},
            "Teams": {"Settings": []},
            "AccessToken": "must-not-copy",
        }
        snapshot = sanitize_account_state(state)
        self.assertEqual(snapshot["profile"]["level"], 67)
        self.assertNotIn("AccessToken", snapshot)
        self.assertEqual(snapshot["items"], [{"StaticID": 3001, "Count": 2}])

    def test_secret_key_guard(self) -> None:
        with self.assertRaises(RuntimeError):
            assert_no_secret_keys({"refresh_token": "secret"})

    def test_cache_is_fresh_for_thirty_minutes(self) -> None:
        snapshot = {
            "profile": {"name": "角色", "level": 1, "leader": 1},
            "roles": [],
            "equipment": [],
            "artifacts": [],
            "items": [],
            "teams": [],
        }
        with tempfile.TemporaryDirectory() as temporary:
            cache = SnapshotCache(Path(temporary))
            with patch("ark_recode_bridge.snapshot.time.time", return_value=1000):
                cache.write(snapshot, "abc")
            with patch("ark_recode_bridge.snapshot.time.time", return_value=2799):
                self.assertTrue(cache.status()["fresh"])
            with patch("ark_recode_bridge.snapshot.time.time", return_value=2800):
                self.assertFalse(cache.status()["fresh"])
            saved = json.loads((Path(temporary) / "account-cache" / "abc" / "latest.json").read_text(encoding="utf-8"))
            self.assertEqual(saved["profile"]["name"], "角色")

    def test_lucima_score_is_kept_separate(self) -> None:
        equipment = {
            "SubProps": {
                "SourceValues": [
                    {"PropertyType": "SpeedValue", "Value": 4},
                    {"PropertyType": "CriticalRate", "Value": 0.05},
                ]
            }
        }
        self.assertEqual(lucima_equipment_score(equipment), 24)


if __name__ == "__main__":
    unittest.main()
