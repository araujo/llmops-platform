"""Catalog pipeline CLI: download, enrich, load (scaffold)."""

from __future__ import annotations

import argparse
import sys

from shopping_assistant.paths import (
    data_enriched_dir,
    data_raw_dir,
    ensure_operational_dirs,
)


def _cmd_download(_: argparse.Namespace) -> int:
    ensure_operational_dirs()
    out = data_raw_dir()
    # Placeholder: vendor/API download into ``out`` later.
    print(f"[catalog download] target directory (canonical): {out}")
    return 0


def _cmd_enrich(_: argparse.Namespace) -> int:
    ensure_operational_dirs()
    src = data_raw_dir()
    dst = data_enriched_dir()
    print(f"[catalog enrich] read from: {src}")
    print(f"[catalog enrich] write to:  {dst}")
    return 0


def _cmd_load(_: argparse.Namespace) -> int:
    ensure_operational_dirs()
    src = data_enriched_dir()
    print(f"[catalog load] source (canonical): {src}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="shopping-assistant-catalog",
        description="Shopping catalog ops (package-local data paths only).",
    )
    sub = p.add_subparsers(dest="command", required=True)

    p_dl = sub.add_parser(
        "download",
        help="Fetch raw catalog assets into data/raw/ (package-local).",
    )
    p_dl.set_defaults(func=_cmd_download)

    p_en = sub.add_parser(
        "enrich",
        help="Transform raw → enriched under data/enriched/ (package-local).",
    )
    p_en.set_defaults(func=_cmd_enrich)

    p_ld = sub.add_parser(
        "load",
        help="Load enriched catalog into runtime stores (placeholder).",
    )
    p_ld.set_defaults(func=_cmd_load)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help()
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
