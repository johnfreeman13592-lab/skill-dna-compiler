from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"


class SensitiveDataFinding(BaseModel):
    """A location-only finding that never stores the matched secret value."""

    model_config = ConfigDict(frozen=True)

    kind: str
    severity: Severity
    line: int = Field(ge=1)
    replacement: str


class ScanResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    sanitized_text: str
    findings: list[SensitiveDataFinding]


@dataclass(frozen=True)
class _Pattern:
    kind: str
    severity: Severity
    regex: re.Pattern[str]
    value_group: str | None = None


_PATTERNS = (
    _Pattern(
        "private_key",
        Severity.HIGH,
        re.compile(
            r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?"
            r"-----END [A-Z0-9 ]*PRIVATE KEY-----",
            re.DOTALL,
        ),
    ),
    _Pattern(
        "openai_api_key",
        Severity.HIGH,
        re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{16,}\b"),
    ),
    _Pattern(
        "github_token",
        Severity.HIGH,
        re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    ),
    _Pattern(
        "aws_access_key",
        Severity.HIGH,
        re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b"),
    ),
    _Pattern(
        "jwt",
        Severity.HIGH,
        re.compile(r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b"),
    ),
    _Pattern(
        "assigned_secret",
        Severity.HIGH,
        re.compile(
            r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|"
            r"client[_-]?secret|password|secret)\b[\"']?\s*[:=]\s*"
            r"(?!\[REDACTED:)"
            r"(?P<value>\"[^\"\r\n]{8,}\"|'[^'\r\n]{8,}'|[^\s,;]{8,})"
        ),
        value_group="value",
    ),
    _Pattern(
        "bearer_token",
        Severity.HIGH,
        re.compile(
            r"(?i)\b(?:authorization\s*:\s*)?bearer\s+"
            r"(?P<value>[A-Za-z0-9._~+/=-]{16,})"
        ),
        value_group="value",
    ),
    _Pattern(
        "email_address",
        Severity.MEDIUM,
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    _Pattern(
        "phone_number",
        Severity.MEDIUM,
        re.compile(r"(?<!\d)(?:\+81[- ]?|0\d{1,4}[- ])\d{1,4}[- ]\d{3,4}(?!\d)"),
    ),
    _Pattern(
        "local_path",
        Severity.MEDIUM,
        re.compile(
            r"(?P<value>(?:\b[A-Za-z]:\\|\\\\[^\\\s`\"']+\\)[^`\"'\r\n]+)"
        ),
        value_group="value",
    ),
)


class SensitiveDataScanner:
    """Detect and redact common credentials and direct contact details locally."""

    def scan(self, text: str) -> ScanResult:
        spans: list[tuple[int, int, _Pattern]] = []
        occupied: list[tuple[int, int]] = []

        for pattern in _PATTERNS:
            for match in pattern.regex.finditer(text):
                start, end = (
                    match.span(pattern.value_group)
                    if pattern.value_group is not None
                    else match.span()
                )
                overlaps = any(
                    start < existing_end and end > existing_start
                    for existing_start, existing_end in occupied
                )
                if overlaps:
                    continue
                occupied.append((start, end))
                spans.append((start, end, pattern))

        findings: list[SensitiveDataFinding] = []
        sanitized = text
        for start, end, pattern in sorted(spans, key=lambda item: item[0], reverse=True):
            replacement = f"[REDACTED:{pattern.kind}]"
            line = text.count("\n", 0, start) + 1
            findings.append(
                SensitiveDataFinding(
                    kind=pattern.kind,
                    severity=pattern.severity,
                    line=line,
                    replacement=replacement,
                )
            )
            preserved_newlines = "\n" * text[start:end].count("\n")
            sanitized = sanitized[:start] + replacement + preserved_newlines + sanitized[end:]

        findings.reverse()
        return ScanResult(sanitized_text=sanitized, findings=findings)
