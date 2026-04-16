"""Single-line operational logs for the shopping pipeline.

Not tracing output and not hidden reasoning.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Mapping

PIPELINE_LOGGER = logging.getLogger("shopping_assistant.pipeline")


def _fmt(value: Any, max_len: int = 220) -> str:
    if value is None:
        return "none"
    if isinstance(value, (dict, list, tuple)):
        s = json.dumps(value, default=str, ensure_ascii=False)
    else:
        s = str(value)
    s = s.replace("\n", " ")
    if len(s) > max_len:
        return s[: max_len - 3] + "..."
    return s


def pipeline_event(
    logger: logging.Logger,
    stage: str,
    request_id: str,
    **fields: Any,
) -> None:
    """Emit one readable line with ``[shopping][stage]`` prefix."""
    parts: list[str] = [f"[shopping][{stage}]", f"request_id={request_id}"]
    for key, val in fields.items():
        parts.append(f"{key}={_fmt(val)}")
    logger.info(" ".join(parts))


def compact_state_summary(state: Mapping[str, Any]) -> str:
    """Short summary for error context (no catalog dumps, no long blobs)."""
    prefs = dict(state.get("preferences") or {})
    sp = dict(state.get("search_plan") or {})
    msg = (state.get("user_message") or "").strip().replace("\n", " ")
    if len(msg) > 160:
        msg = msg[:157] + "..."
    return (
        f"msg={msg!r}; "
        f"{compact_preferences(prefs)}; "
        f"catalog_n={len(state.get('shopping_catalog') or [])}; "
        f"candidates_n={len(state.get('shopping_candidates') or [])}; "
        f"ranked_n={len(state.get('shopping_ranked') or [])}; "
        f"relaxed={state.get('shopping_relaxed', 'n/a')}; "
        f"match_quality={sp.get('match_quality', 'n/a')}"
    )


def pipeline_stage_error(
    logger: logging.Logger,
    failed_stage: str,
    request_id: str,
    exc: BaseException,
    *,
    state_summary: str | None = None,
    **extra: Any,
) -> None:
    """Readable error line plus stack trace on the same logger (not silent)."""
    parts: list[str] = [
        f"[shopping][stage_error]",
        f"failed_stage={failed_stage}",
        f"request_id={request_id}",
        f"error={_fmt(str(exc), max_len=320)}",
    ]
    if state_summary is not None:
        parts.append(f"state_summary={_fmt(state_summary, max_len=400)}")
    for key, val in extra.items():
        parts.append(f"{key}={_fmt(val)}")
    logger.error(" ".join(parts), exc_info=True)


def compact_preferences(prefs: dict[str, Any]) -> str:
    """Trimmed preference summary for logs."""
    keys = (
        "max_price",
        "min_price",
        "product_types",
        "categories",
        "brands",
        "colors",
        "use_cases",
        "gift_intent",
        "brand_relaxed",
    )
    bits: list[str] = []
    for k in keys:
        v = prefs.get(k)
        if v is None or v is False or v == []:
            continue
        bits.append(f"{k}={v}")
    return ";".join(bits) if bits else "default"
