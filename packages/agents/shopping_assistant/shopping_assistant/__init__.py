"""Shopping assistant agent plugin (self-contained; lives only in this package)."""

from shopping_assistant.constants import AGENT_ID
from shopping_assistant.plugin import ShoppingAssistantPlugin, register

__all__ = ["AGENT_ID", "ShoppingAssistantPlugin", "register"]
