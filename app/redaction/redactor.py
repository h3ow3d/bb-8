from __future__ import annotations

import re
from typing import Any

_SECRET_PATTERN = re.compile(
    r"""(?ix)
    (?:
        password|passwd|secret|token|bearer|api[_-]?key|private[_-]?key|
        auth|credential|credentials|access[_-]?key|
        connection[_-]?string|connstr|jdbc|dsn|
        private_key_data|client_secret
    )
    """,
    re.IGNORECASE,
)

_VALUE_PATTERN = re.compile(
    r"""(?x)
    (?:
        eyJ[A-Za-z0-9_-]{10,}|                   # JWT token
        [A-Za-z0-9+/]{40,}={0,2}|                # base64 blob
        -----BEGIN\s+[A-Z ]+KEY-----|             # PEM key header
        [a-z0-9]{32,}                             # long hex/alphanumeric string
    )
    """,
    re.VERBOSE,
)

REDACTED = "[REDACTED]"


def _looks_sensitive_key(key: str) -> bool:
    return bool(_SECRET_PATTERN.search(key))


def _looks_sensitive_value(value: str) -> bool:
    if len(value) < 8:
        return False
    return bool(_VALUE_PATTERN.search(value))


def redact_string(value: str) -> tuple[str, int]:
    """Redact the string if it looks like a secret. Returns (result, count)."""
    if _looks_sensitive_value(value):
        return REDACTED, 1
    return value, 0


def redact_dict(d: dict[str, Any], *, key_check: bool = True) -> tuple[dict[str, Any], int]:
    """Recursively redact a dict. Returns (redacted_dict, total_redaction_count)."""
    count = 0
    result: dict[str, Any] = {}
    for k, v in d.items():
        if key_check and _looks_sensitive_key(str(k)):
            result[k] = REDACTED
            count += 1
        elif isinstance(v, dict):
            result[k], sub_count = redact_dict(v, key_check=key_check)
            count += sub_count
        elif isinstance(v, list):
            new_list, sub_count = redact_list(v, key_check=key_check)
            result[k] = new_list
            count += sub_count
        elif isinstance(v, str):
            redacted_v, sub_count = redact_string(v)
            result[k] = redacted_v
            count += sub_count
        else:
            result[k] = v
    return result, count


def redact_list(items: list[Any], *, key_check: bool = True) -> tuple[list[Any], int]:
    """Recursively redact a list."""
    count = 0
    result: list[Any] = []
    for item in items:
        if isinstance(item, dict):
            new_item, sub_count = redact_dict(item, key_check=key_check)
            result.append(new_item)
            count += sub_count
        elif isinstance(item, list):
            new_item_list, sub_count = redact_list(item, key_check=key_check)
            result.append(new_item_list)
            count += sub_count
        elif isinstance(item, str):
            redacted, sub_count = redact_string(item)
            result.append(redacted)
            count += sub_count
        else:
            result.append(item)
    return result, count


def redact_text(text: str) -> tuple[str, int]:
    """Redact secrets that appear inline in plain text."""
    count = 0
    lines = text.split("\n")
    out: list[str] = []
    for line in lines:
        new_line, n = _redact_line(line)
        out.append(new_line)
        count += n
    return "\n".join(out), count


def _redact_line(line: str) -> tuple[str, int]:
    count = 0
    # Limit key and value lengths to prevent catastrophic backtracking
    for match in re.finditer(r"(\w[\w\-_.]{0,200})\s*[=:]\s*(\S{1,1024})", line):
        key = match.group(1)
        value = match.group(2)
        if _looks_sensitive_key(key) and value not in ("true", "false", "null", "None", REDACTED) or _looks_sensitive_value(value):
            line = line.replace(match.group(0), f"{key}={REDACTED}", 1)
            count += 1
    return line, count
