from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import uuid
from contextlib import contextmanager
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .config import data_root, public_knowledge_dir


class KnowledgeStore:
    def __init__(self, root: Path | None = None, public_dir: Path | None = None) -> None:
        self.root = (root or data_root()) / "knowledge"
        self.database = self.root / "knowledge.db"
        self.public_dir = public_dir or public_knowledge_dir()
        self.root.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    content TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT,
                    source_uri TEXT NOT NULL,
                    source_title TEXT,
                    retrieved_at INTEGER NOT NULL,
                    license TEXT,
                    confidence REAL NOT NULL,
                    status TEXT NOT NULL,
                    content_hash TEXT NOT NULL UNIQUE
                )
                """
            )

    @staticmethod
    def _content_hash(title: str, content: str, source_uri: str) -> str:
        normalized = "\n".join(part.strip() for part in (title, content, source_uri))
        return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

    def ingest(
        self,
        *,
        title: str,
        content: str,
        source_uri: str,
        entity_type: str = "guide",
        entity_id: str = "",
        source_title: str = "",
        license_name: str = "",
        confidence: float = 0.7,
    ) -> dict[str, Any]:
        if not title.strip() or not content.strip() or not source_uri.strip():
            raise ValueError("title、content和source_uri不能为空")
        digest = self._content_hash(title, content, source_uri)
        with self._connect() as connection:
            existing = connection.execute(
                "SELECT * FROM records WHERE content_hash = ?", (digest,)
            ).fetchone()
            if existing:
                return {"created": False, "record": dict(existing)}
            conflict = None
            if entity_id:
                conflict = connection.execute(
                    "SELECT id FROM records WHERE entity_type = ? AND entity_id = ? AND status != 'rejected'",
                    (entity_type, entity_id),
                ).fetchone()
            record_id = uuid.uuid4().hex
            status = "pending" if conflict else "local"
            connection.execute(
                "INSERT INTO records VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    record_id,
                    title.strip(),
                    content.strip(),
                    entity_type.strip(),
                    entity_id.strip(),
                    source_uri.strip(),
                    source_title.strip(),
                    int(time.time()),
                    license_name.strip(),
                    min(1.0, max(0.0, float(confidence))),
                    status,
                    digest,
                ),
            )
            record = connection.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        return {"created": True, "conflict": bool(conflict), "record": dict(record)}

    def review(self, record_id: str, decision: str) -> dict[str, Any]:
        if decision not in {"accepted", "rejected"}:
            raise ValueError("decision必须是accepted或rejected")
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE records SET status = ? WHERE id = ?", (decision, record_id)
            )
            if cursor.rowcount != 1:
                raise KeyError("没有找到知识记录")
            row = connection.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        return dict(row)

    def pending(self) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM records WHERE status = 'pending' ORDER BY retrieved_at DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def search(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        words = [word for word in query.strip().split() if word]
        pattern = "%" + "%".join(words or [query.strip()]) + "%"
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM records
                WHERE status != 'rejected' AND (title LIKE ? OR content LIKE ? OR entity_id LIKE ?)
                ORDER BY confidence DESC, retrieved_at DESC LIMIT ?
                """,
                (pattern, pattern, pattern, int(limit)),
            ).fetchall()
        local_records = [dict(row) | {"scope": "local"} for row in rows]
        public_records = self._search_public(query, limit)
        combined = local_records + public_records
        combined.sort(key=lambda item: float(item.get("confidence", 0)), reverse=True)
        return combined[:limit]

    def _search_public(self, query: str, limit: int) -> list[dict[str, Any]]:
        if not self.public_dir.exists():
            return []
        terms = [item.lower() for item in query.split() if item]
        matches: list[dict[str, Any]] = []
        for path in sorted(self.public_dir.glob("*.json")):
            if path.name == "schema.json":
                continue
            payload = json.loads(path.read_text(encoding="utf-8"))
            records = payload if isinstance(payload, list) else [payload]
            for record in records:
                haystack = f"{record.get('title', '')} {record.get('content', '')} {record.get('entity_id', '')}".lower()
                if not terms or all(term in haystack for term in terms):
                    matches.append(dict(record) | {"scope": "public"})
        return matches[:limit]

    def promote(self, record_id: str, repo_root: Path, confirm_public: bool) -> Path:
        if not confirm_public:
            raise ValueError("必须显式传入 --confirm-public")
        with self._connect() as connection:
            row = connection.execute("SELECT * FROM records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            raise KeyError("没有找到知识记录")
        record = dict(row)
        if record["status"] != "accepted":
            raise ValueError("只有已审核通过的记录可以进入公共知识库")
        if not record["license"] or not record["source_uri"].startswith(("http://", "https://")):
            raise ValueError("公共记录必须填写许可证和HTTP(S)来源")
        expected_root = (
            repo_root / "plugins" / "ark-recode-assist" / "knowledge" / "public"
        ).resolve()
        destination = (expected_root / f"{record_id}.json").resolve()
        if destination.parent != expected_root:
            raise RuntimeError("公共知识路径越界")
        destination.parent.mkdir(parents=True, exist_ok=True)
        public_record = {
            key: value for key, value in record.items() if key not in {"status", "content_hash"}
        }
        destination.write_text(
            json.dumps(public_record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        return destination
