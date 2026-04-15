"""CLI: seed shopping prompts into MongoDB (uses core Mongo repository)."""

from __future__ import annotations

import argparse
import os

from shopping_assistant.bootstrap.seed_prompts import seed_shopping_prompts_to_mongo


def main(argv: list[str] | None = None) -> int:
    desc = "Seed shopping_assistant prompts into MongoDB via llmops-core."
    parser = argparse.ArgumentParser(description=desc)
    mongo_help = (
        "Mongo URI, or set SHOPPING_ASSISTANT_MONGO_URI / MONGO_URI / LLMOPS_MONGO_URI."
    )
    parser.add_argument(
        "--mongo-uri",
        default=(
            os.environ.get("SHOPPING_ASSISTANT_MONGO_URI")
            or os.environ.get("MONGO_URI")
            or os.environ.get("LLMOPS_MONGO_URI")
        ),
        help=mongo_help,
    )
    parser.add_argument(
        "--database",
        default=(
            os.environ.get("SHOPPING_ASSISTANT_MONGO_DATABASE")
            or os.environ.get("LLMOPS_MONGO_DATABASE")
            or "llmops"
        ),
        help="Database name (default llmops or LLMOPS_MONGO_DATABASE).",
    )
    parser.add_argument(
        "--collection",
        default=(
            os.environ.get("SHOPPING_ASSISTANT_MONGO_PROMPT_COLLECTION")
            or os.environ.get("LLMOPS_MONGO_PROMPT_COLLECTION")
            or "llmops_prompt_versions"
        ),
        help="Prompt versions collection name.",
    )
    parser.add_argument(
        "--no-activate",
        action="store_true",
        help="Upsert rows but do not mark revisions active.",
    )
    args = parser.parse_args(argv)

    if not args.mongo_uri:
        parser.error(
            "Pass --mongo-uri or set SHOPPING_ASSISTANT_MONGO_URI / MONGO_URI / "
            "LLMOPS_MONGO_URI"
        )

    records = seed_shopping_prompts_to_mongo(
        args.mongo_uri,
        args.database,
        collection=args.collection,
        activate=not args.no_activate,
    )
    for r in records:
        qn = (r.metadata or {}).get("qualified_name", f"{r.agent_id}.{r.name}")
        print(f"seeded: {qn} v{r.version} status={r.status.value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
