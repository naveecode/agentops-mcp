"""Checks that run before the agent is allowed to call a tool."""
import re

MAX_QUESTION_LENGTH = 2000
REFUSAL = "I can't help with that request."

_BLOCKED = (
    re.compile(r"\bignore\b.{0,40}\binstructions\b", re.IGNORECASE),
    re.compile(r"\bdisregard\b.{0,40}\binstructions\b", re.IGNORECASE),
    re.compile(r"\breveal\b.{0,40}\b(system prompt|hidden prompt)\b", re.IGNORECASE),
)


def refusal(question: str) -> str | None:
    """Return a refusal message, or None when the question may proceed."""
    text = question.strip()
    if not text:
        return "Ask a question first."
    if len(text) > MAX_QUESTION_LENGTH:
        return "That question is too long."
    for pattern in _BLOCKED:
        if pattern.search(text):
            return REFUSAL
    return None
