from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "components" / "lucima-bridge" / "src"))

from ark_recode_bridge.knowledge import KnowledgeStore


class KnowledgeStoreTests(unittest.TestCase):
    def test_deduplicate_and_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            store = KnowledgeStore(root=root, public_dir=root / "public")
            first = store.ingest(
                title="角色A攻略",
                content="优先速度。",
                source_uri="https://example.com/a",
                entity_type="character",
                entity_id="1001",
            )
            duplicate = store.ingest(
                title="角色A攻略",
                content="优先速度。",
                source_uri="https://example.com/a",
                entity_type="character",
                entity_id="1001",
            )
            conflict = store.ingest(
                title="角色A另一攻略",
                content="优先攻击。",
                source_uri="https://example.com/b",
                entity_type="character",
                entity_id="1001",
            )
            self.assertTrue(first["created"])
            self.assertFalse(duplicate["created"])
            self.assertTrue(conflict["conflict"])
            self.assertEqual(conflict["record"]["status"], "pending")

    def test_public_search_and_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            public = root / "public"
            public.mkdir()
            (public / "seed.json").write_text(
                json.dumps([{"id": "x", "title": "装备评分", "content": "两套评分分开", "confidence": 1.0}], ensure_ascii=False),
                encoding="utf-8",
            )
            store = KnowledgeStore(root=root / "data", public_dir=public)
            self.assertEqual(store.search("装备评分")[0]["scope"], "public")
            record = store.ingest(
                title="公开摘要",
                content="只保留简短事实。",
                source_uri="https://example.com/source",
                entity_id="guide-1",
                license_name="CC-BY-4.0",
            )["record"]
            store.review(record["id"], "accepted")
            repo = root / "repo"
            promoted = store.promote(record["id"], repo, True)
            self.assertTrue(promoted.is_file())
            self.assertIn("公开摘要", promoted.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
