"""One-off setup: migrations, index bootstrap, local dev helpers for this agent."""

from shopping_assistant.bootstrap.seed_prompts import seed_shopping_prompts_to_mongo

__all__ = ["seed_shopping_prompts_to_mongo"]
