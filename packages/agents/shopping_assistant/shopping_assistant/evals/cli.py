"""CLI: list datasets and run shopping eval suites (no API / Langfuse)."""

from __future__ import annotations

import argparse
import json
import sys

from shopping_assistant.evals.runner import list_local_datasets, run_eval_suite


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Shopping assistant offline eval (local JSON datasets).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser(
        "list",
        help="List dataset files in evals/datasets/",
    )
    p_list.set_defaults(func=_cmd_list)

    p_run = sub.add_parser(
        "run",
        help="Run a suite by stem (e.g. smoke → smoke.json)",
    )
    p_run.add_argument("stem", help="Dataset filename stem without .json")
    p_run.add_argument(
        "--json",
        action="store_true",
        help="Emit full JSON result instead of concise text summary.",
    )
    p_run.set_defaults(func=_cmd_run)

    args = parser.parse_args(argv)
    return int(args.func(args))


def _cmd_list(_args: argparse.Namespace) -> int:
    paths = list_local_datasets()
    for p in paths:
        print(p.stem, "\t", p, sep="")
    return 0


def _cmd_run(args: argparse.Namespace) -> int:
    out = run_eval_suite(args.stem)
    if args.json:
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0 if out.get("ok") else 1

    if not out.get("ok") and out.get("error"):
        print(f"error: {out['error']}")
        return 1

    print(f"dataset: {out.get('dataset_stem')}")
    desc = str(out.get("description") or "").strip()
    if desc:
        print(f"description: {desc}")
    print(f"total: {out.get('total', 0)}")
    print(f"passed: {out.get('passed', 0)}")
    print(f"failed: {out.get('failed', 0)}")
    print("cases:")
    for case in out.get("cases", []):
        cid = case.get("id", "unknown")
        status = "PASS" if case.get("ok") else "FAIL"
        mode = case.get("mode", "")
        mq = case.get("match_quality", "")
        products = case.get("products", [])
        detail = case.get("detail", "")
        print(
            f"- [{status}] {cid} | mode={mode} | match_quality={mq} "
            f"| products={products} | {detail}"
        )
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
