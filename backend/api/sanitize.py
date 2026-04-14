"""
Input sanitization for buyer-supplied free-text fields.

Strips characters that are commonly exploited in prompt injection attacks:
  - Control characters (newlines, carriage returns, null bytes, etc.) that
    enable role-injection via "\\nSystem: ignore previous instructions"
  - Angle brackets that could escape an XML-tag wrapper in the prompt
"""

import re

# Control chars U+0000–U+001F, DEL U+007F, and XML angle brackets
_UNSAFE_CHARS = re.compile(r"[\x00-\x1f\x7f<>]")
_MULTI_SPACE = re.compile(r" {2,}")


def sanitize_buyer_context(text: str) -> str:
    """Return *text* with injection-risky characters replaced by spaces.

    Safe characters (letters, digits, punctuation, spaces) are preserved
    verbatim. The result is stripped of leading/trailing whitespace and has
    runs of spaces collapsed to a single space.
    """
    cleaned = _UNSAFE_CHARS.sub(" ", text)
    cleaned = _MULTI_SPACE.sub(" ", cleaned)
    return cleaned.strip()
