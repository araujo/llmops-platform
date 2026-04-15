"""HTTP-facing surfaces for this agent (routers, request/response models)."""

from shopping_assistant.app.router import build_agent_router
from shopping_assistant.app.schemas import ShoppingChatRequest, ShoppingChatResponse

__all__ = [
    "ShoppingChatRequest",
    "ShoppingChatResponse",
    "build_agent_router",
]
