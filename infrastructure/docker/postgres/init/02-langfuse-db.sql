-- Separate DB for Langfuse (app uses llmops DB with pgvector).
CREATE DATABASE langfuse OWNER llmops;
