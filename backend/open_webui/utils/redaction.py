"""Pseudonymise identifiers before content leaves for an external provider (Group 6 PIA).

Findings B1, B2/B4 and B3: when the lab connects an OpenAI-compatible provider, Open WebUI sends
the whole chat with its retrieved passages (B1), every chunk of an uploaded document for
embedding (B2/B4) and the chat again for titles, tags and follow-ups (B3). Interviewees' names,
e-mail addresses and phone numbers in those texts reach a company they never chose.

Every such request now passes through `Redactor` first. It replaces
  * names listed in the lab's participant register  -> [PERSON_1], [PERSON_2], ...
  * e-mail addresses (by pattern)                   -> [EMAIL_1], ...
  * phone numbers in international or national form -> [PHONE_1], ...
The same value gets the same placeholder within one request, so the model can still tell two
people apart. Nothing is changed in what Open WebUI stores locally.

Limits, stated in the report: a name that is not in the register is not found (automatic name
detection is the next step); the placeholders are not mapped back in the model's answer.
Settings: ENABLE_PROVIDER_REDACTION (default True), PROVIDER_REDACTION_REGISTER (default
DATA_DIR/privacy/participants.txt).
"""

from __future__ import annotations

import logging
import re
from typing import Any

from open_webui.env import ENABLE_PROVIDER_REDACTION, PROVIDER_REDACTION_REGISTER

log = logging.getLogger(__name__)

EMAIL = re.compile(r'(?<![\w.+-])[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}')
# International numbers (+32 470 12 34 56, 0032 ...), and national numbers that use spaces,
# dashes or slashes (0470 12 34 56). Dotted numbers are left alone so dates such as 07.11.2026
# are not mistaken for phones, and so are numbers shaped like a date (07/11/2026, see DATE).
# A match must hold 8 to 15 digits.
PHONE = re.compile(r'(?<![\w+])(?:(?:\+|00)\d[\d \t().\-/]{6,20}\d|0\d{1,3}[ \t\-/]\d[\d \t\-/]{5,14}\d)(?!\w)')

# Day/month/year written with spaces, dashes or slashes. It has the digits of a phone number,
# so it is checked separately and left unchanged.
DATE = re.compile(r'\d{1,2}[ /\-]\d{1,2}[ /\-]\d{2,4}')

# Keys whose values are not free text and must reach the provider unchanged.
_SKIP_KEYS = {
    'model',
    'tools',
    'tool_choice',
    'response_format',
    'stream_options',
    'image_url',
    'url',
    'id',
    'tool_call_id',
    'role',
    'type',
}

_register_cache: tuple[float, list[re.Pattern]] | None = None
_warned_no_register = False


def _register_patterns() -> list[re.Pattern]:
    """Names from the participant register, longest first, re-read when the file changes."""
    global _register_cache, _warned_no_register
    try:
        mtime = PROVIDER_REDACTION_REGISTER.stat().st_mtime
    except OSError:
        if not _warned_no_register:
            _warned_no_register = True
            log.warning(
                'redaction: no participant register at %s, so only e-mail addresses and phone numbers are replaced',
                PROVIDER_REDACTION_REGISTER,
            )
        return []
    if _register_cache and _register_cache[0] == mtime:
        return _register_cache[1]
    names = []
    for line in PROVIDER_REDACTION_REGISTER.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if line and not line.startswith('#'):
            names.append(line)
    patterns = [
        re.compile(r'(?<!\w)' + re.escape(n) + r'(?!\w)', re.IGNORECASE)
        for n in sorted(set(names), key=len, reverse=True)
    ]
    _register_cache = (mtime, patterns)
    return patterns


class Redactor:
    """Replaces identifiers in the texts of one outgoing request."""

    def __init__(self) -> None:
        self._names = _register_patterns()
        self._seen: dict[tuple[str, str], str] = {}
        self._count: dict[str, int] = {}

    def _placeholder(self, kind: str, value: str) -> str:
        key = (kind, value.casefold())
        if key not in self._seen:
            self._count[kind] = self._count.get(kind, 0) + 1
            self._seen[key] = f'[{kind}_{self._count[kind]}]'
        return self._seen[key]

    def text(self, value: str) -> str:
        if not value or value.startswith('data:'):
            return value
        for pattern in self._names:
            value = pattern.sub(lambda m: self._placeholder('PERSON', m.group(0)), value)
        value = EMAIL.sub(lambda m: self._placeholder('EMAIL', m.group(0)), value)

        def phone(m: re.Match) -> str:
            digits = sum(ch.isdigit() for ch in m.group(0))
            if DATE.fullmatch(m.group(0)) or not 8 <= digits <= 15:
                return m.group(0)
            return self._placeholder('PHONE', m.group(0))

        return PHONE.sub(phone, value)

    def payload(self, value: Any, key: str | None = None) -> Any:
        if key in _SKIP_KEYS:
            return value
        if isinstance(value, str):
            return self.text(value)
        if isinstance(value, list):
            return [self.payload(item) for item in value]
        if isinstance(value, dict):
            return {k: self.payload(v, k) for k, v in value.items()}
        return value

    @property
    def replaced(self) -> int:
        return len(self._seen)


def redact_payload(payload: Any) -> Any:
    """Pseudonymise a JSON-like request body (chat completion, responses or embeddings)."""
    if not ENABLE_PROVIDER_REDACTION:
        return payload
    redactor = Redactor()
    result = redactor.payload(payload)
    if redactor.replaced:
        log.info('redaction: replaced %d identifier(s) in a provider request', redactor.replaced)
    return result


def redact_texts(texts: list[str]) -> list[str]:
    """Pseudonymise the texts of one embedding request."""
    if not ENABLE_PROVIDER_REDACTION:
        return texts
    redactor = Redactor()
    return [redactor.text(t) if isinstance(t, str) else t for t in texts]
