from __future__ import annotations

import re
from typing import Any


SECRET_VALUE_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9]{16,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z\-_]{20,}\b"),
    re.compile(r"-----BEGIN (?:RSA|EC|OPENSSH|PRIVATE) KEY-----"),
]

SECRET_REQUEST_PATTERNS = [
    re.compile(r"paste\s+your\s+(api\s*key|token|private\s*key|seed\s*phrase)", re.IGNORECASE),
    re.compile(r"share\s+your\s+\.env", re.IGNORECASE),
    re.compile(r"copy\s+your\s+credentials?\s+here", re.IGNORECASE),
]

PII_PATTERNS = [
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),  # SSN-like
    re.compile(r"\b[\w\.-]+@[\w\.-]+\.\w{2,}\b"),  # email
]

RAW_LOG_PATTERNS = [
    re.compile(r"\b(full\s+logs?|raw\s+logs?)\b", re.IGNORECASE),
]


def is_secret_like_text(text: str) -> bool:
    for pattern in SECRET_VALUE_PATTERNS:
        if pattern.search(text):
            return True
    return False


def is_secret_request_text(text: str) -> bool:
    for pattern in SECRET_REQUEST_PATTERNS:
        if pattern.search(text):
            return True
    return False


def payload_contains_secrets(payload: Any) -> bool:
    if isinstance(payload, str):
        return is_secret_like_text(payload) or is_secret_request_text(payload)
    if isinstance(payload, list):
        return any(payload_contains_secrets(item) for item in payload)
    if isinstance(payload, dict):
        return any(payload_contains_secrets(value) for value in payload.values())
    return False


def payload_contains_pii(payload: Any) -> bool:
    if isinstance(payload, str):
        for pattern in PII_PATTERNS:
            if pattern.search(payload):
                return True
        return False
    if isinstance(payload, list):
        return any(payload_contains_pii(item) for item in payload)
    if isinstance(payload, dict):
        return any(payload_contains_pii(value) for value in payload.values())
    return False


def payload_requests_raw_logs(payload: Any) -> bool:
    if isinstance(payload, str):
        for pattern in RAW_LOG_PATTERNS:
            if pattern.search(payload):
                return True
        return False
    if isinstance(payload, list):
        return any(payload_requests_raw_logs(item) for item in payload)
    if isinstance(payload, dict):
        return any(payload_requests_raw_logs(value) for value in payload.values())
    return False
