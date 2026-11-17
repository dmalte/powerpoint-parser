"""Stable, non-revealing categories for local conversion errors."""
from __future__ import annotations

def classify_failure(file_type: str, reason: str) -> str:
    """Fixed codes only. Never put the raw private exception in state/UI."""
    message = reason.casefold()
    if any(token in message for token in ("password", "encrypt", "authenticate", "cryptography", "needs_pass")):
        return "password_or_encrypted"
    if any(token in message for token in (
        "permission", "access denied", "access not allowed", "access to", "not permitted",
        "operation not permitted", "-1743",
    )):
        return "permission_or_access"
    if any(token in message for token in ("timeout", "timed out", "time limit")):
        return "timeout"
    if file_type == "pptx" and any(token in message for token in (
        "powerpoint", "applescript", "osascript", "-9074", "pdf export", "automati", "office export",
    )):
        return "powerpoint_automation"
    if any(token in message for token in (
        "invalid", "corrupt", "zero page", "zero-page", "failed to open",
        "cannot open", "file format", "xref",
    )):
        return "invalid_or_unreadable"
    return "unclassified"
