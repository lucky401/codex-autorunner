from __future__ import annotations

INJECTED_CONTEXT_START = "<injected context>"
INJECTED_CONTEXT_END = "</injected context>"


def wrap_injected_context(text: str) -> str:
    """Wrap prompt hints in injected context blocks."""
    return f"{INJECTED_CONTEXT_START}\n{text}\n{INJECTED_CONTEXT_END}"
