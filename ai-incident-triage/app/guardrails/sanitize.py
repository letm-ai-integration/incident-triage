"""HTML sanitization for LLM-drafted content that leaves the system as real
HTML (currently: the notification email body sent via Resend).

Plain allowlist transform, not a ``GuardrailCheckType`` -- it doesn't pass or
fail, it rewrites. Lives alongside the guardrails package because it guards
the same boundary (LLM output -> real external system).
"""
from __future__ import annotations

import re

_ALLOWED_TAGS = {"h1", "h2", "h3", "p", "b", "strong", "i", "em", "ul", "ol", "li", "br", "a"}
_TAG_RE = re.compile(r"</?([a-zA-Z0-9]+)((?:\s+[^<>]*)?)/?>")
_HREF_RE = re.compile(r'href\s*=\s*"(https?://[^"]*)"', re.IGNORECASE)


def sanitize_html_email_body(html: str) -> str:
    """Strip any tag not in the allowlist and any attribute other than a
    safe ``href`` on ``<a>`` tags (drops ``on*`` event handlers, ``style``,
    ``javascript:`` links, etc.).
    """

    def _replace(match: re.Match[str]) -> str:
        full_tag = match.group(0)
        tag_name = match.group(1).lower()
        attrs = match.group(2) or ""
        if tag_name not in _ALLOWED_TAGS:
            return ""
        is_closing = full_tag.startswith("</")
        if is_closing:
            return f"</{tag_name}>"
        if tag_name == "a":
            href_match = _HREF_RE.search(attrs)
            if href_match:
                return f'<a href="{href_match.group(1)}">'
            return "<a>"
        return f"<{tag_name}>"

    return _TAG_RE.sub(_replace, html)
