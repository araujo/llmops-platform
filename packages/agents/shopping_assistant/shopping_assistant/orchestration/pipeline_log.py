"""Single-line operational logs for the shopping pipeline.

Not tracing output and not hidden reasoning.
"""

from __future__ import annotations

import json
import logging
from typing import Any

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
