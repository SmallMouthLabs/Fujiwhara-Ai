"""Loads `.env` once, at process start.

Provider adapters themselves never touch this file or read env vars directly.
They rely on the Anthropic and OpenAI SDKs each resolving their own API key
(`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`) from the environment. All this module
does is make sure `.env` has been read into that environment before any
adapter is constructed. Call `load()` once, early, from whatever entry point
starts the app (the CLI, a test fixture, and so on).
"""

from __future__ import annotations

from dotenv import load_dotenv

_loaded = False


def load() -> None:
    """Load `.env` into the process environment. Safe to call more than once."""
    global _loaded
    if _loaded:
        return
    load_dotenv()
    _loaded = True
