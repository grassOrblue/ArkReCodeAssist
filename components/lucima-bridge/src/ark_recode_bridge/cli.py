from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from .analyzer import AccountAnalyzer
from .config import data_root
from .knowledge import KnowledgeStore
from .providers import DisabledGameActionProvider, provider_inventory
from .snapshot import LucimaSnapshotProvider, SnapshotCache


def parser() -> argparse.ArgumentParser:
    root_parser = argparse.ArgumentParser(prog="ark-recode-bridge")
    root_parser.add_argument("--data-dir", help="覆盖本地数据目录")
    groups = root_parser.add_subparsers(dest="group", required=True)

    snapshot = groups.add_parser("snapshot")
    snapshot_sub = snapshot.add_subparsers(dest="action", required=True)
    refresh = snapshot_sub.add_parser("refresh")
    refresh.add_argument("--account")
    refresh.add_argument("--lucima-data-dir")
    snapshot_sub.add_parser("show")

    analyze = groups.add_parser("analyze")
    analyze_sub = analyze.add_subparsers(dest="action", required=True)
    analyze_account = analyze_sub.add_parser("account")
    analyze_account.add_argument("--query", default="")
    analyze_character = analyze_sub.add_parser("character")
    analyze_character.add_argument("--name", required=True)
    analyze_character.add_argument("--query", default="")
    analyze_equipment = analyze_sub.add_parser("equipment")
    analyze_equipment.add_argument("--limit", type=int, default=20)
    analyze_equipment.add_argument("--query", default="")

    knowledge = groups.add_parser("knowledge")
    knowledge_sub = knowledge.add_subparsers(dest="action", required=True)
    ingest = knowledge_sub.add_parser("ingest")
    ingest.add_argument("--title", required=True)
    ingest.add_argument("--content", required=True)
    ingest.add_argument("--source-uri", required=True)
    ingest.add_argument("--source-title", default="")
    ingest.add_argument("--entity-type", default="guide")
    ingest.add_argument("--entity-id", default="")
    ingest.add_argument("--license", default="")
    ingest.add_argument("--confidence", type=float, default=0.7)
    search = knowledge_sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    review = knowledge_sub.add_parser("review")
    review.add_argument("--id")
    review.add_argument("--decision", choices=["accepted", "rejected"])
    promote = knowledge_sub.add_parser("promote")
    promote.add_argument("--id", required=True)
    promote.add_argument("--repo-root", type=Path, required=True)
    promote.add_argument("--confirm-public", action="store_true")

    providers = groups.add_parser("providers")
    providers.add_argument("action", choices=["list"])
    game_action = groups.add_parser("game-action", help=argparse.SUPPRESS)
    game_action.add_argument("action")
    return root_parser


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    root = Path(args.data_dir).expanduser().resolve() if args.data_dir else data_root()
    cache = SnapshotCache(root)
    try:
        if args.group == "snapshot":
            if args.action == "show":
                print_json(cache.status())
                return 0
            provider = LucimaSnapshotProvider(args.lucima_data_dir, cache, root)
            result = provider.refresh(args.account)
            print_json({"refreshed": True, "metadata": result["metadata"]})
            return 0

        if args.group == "analyze":
            snapshot, metadata = cache.read()
            analyzer = AccountAnalyzer()
            if args.action == "account":
                result = analyzer.account(snapshot, args.query)
            elif args.action == "character":
                result = analyzer.character(snapshot, args.name, args.query)
            else:
                result = analyzer.equipment(snapshot, args.limit, args.query)
            result["knowledge"] = KnowledgeStore(root=root).search(args.query, 5) if args.query else []
            result["snapshot_created_at"] = metadata["created_at"]
            print_json(result)
            return 0

        if args.group == "knowledge":
            store = KnowledgeStore(root=root)
            if args.action == "ingest":
                print_json(
                    store.ingest(
                        title=args.title,
                        content=args.content,
                        source_uri=args.source_uri,
                        source_title=args.source_title,
                        entity_type=args.entity_type,
                        entity_id=args.entity_id,
                        license_name=args.license,
                        confidence=args.confidence,
                    )
                )
            elif args.action == "search":
                print_json({"results": store.search(args.query, args.limit)})
            elif args.action == "review":
                if args.id and args.decision:
                    print_json(store.review(args.id, args.decision))
                else:
                    print_json({"pending": store.pending()})
            else:
                path = store.promote(args.id, args.repo_root, args.confirm_public)
                print_json({"promoted": str(path)})
            return 0

        if args.group == "providers":
            print_json(provider_inventory(Path(sys.executable)))
            return 0

        if args.group == "game-action":
            print_json(DisabledGameActionProvider().plan(args.action, {}))
            return 2
    except Exception as exc:
        print_json({"error": type(exc).__name__, "message": str(exc)})
        return 1
    return 1
