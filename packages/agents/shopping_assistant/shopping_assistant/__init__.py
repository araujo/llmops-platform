"""Shopping assistant agent plugin (self-contained; lives only in this package)."""

from shopping_assistant.constants import AGENT_ID

__all__ = ["AGENT_ID", "ShoppingAssistantPlugin", "register"]


def __getattr__(name: str):
    """Lazy imports so CLIs (e.g. evals) avoid loading the full plugin/router stack."""
    if name == "ShoppingAssistantPlugin":
        from shopping_assistant.plugin import ShoppingAssistantPlugin as _C

        return _C
    if name == "register":
        from shopping_assistant.plugin import register as _r

        return _r
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
