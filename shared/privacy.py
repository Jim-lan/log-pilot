"""Best-effort outbound content redaction, not a comprehensive DLP boundary."""
import re

from shared.utils.pii_masker import PIIMasker

_MASKER = PIIMasker()
_PRIVATE_KEY = re.compile(r'-----BEGIN ([A-Z ]*PRIVATE KEY)-----.*?-----END \1-----', re.DOTALL)
_URL_CREDENTIALS = re.compile(r'(https?://)[^\s/@]+:[^\s/@]+@', re.IGNORECASE)
_BEARER = re.compile(r'\bBearer\s+[A-Za-z0-9._~+/-]+=*', re.IGNORECASE)
_ASSIGNMENT = re.compile(
    r'''(\b(?:password|passwd|api[_-]?key|access[_-]?token|secret)["']?\s*[:=]\s*)(?:"[^"\n]*"|'[^'\n]*'|[^\s,;}]+)''',
    re.IGNORECASE,
)


def redact_outbound(text: str) -> str:
    """Redact supported credentials and PII from model/search request content."""
    text = _PRIVATE_KEY.sub('<PRIVATE_KEY_REDACTED>', text)
    text = _URL_CREDENTIALS.sub(r'\1<CREDENTIALS_REDACTED>@', text)
    text = _BEARER.sub('Bearer <TOKEN_REDACTED>', text)
    text = _ASSIGNMENT.sub(r'\1<SECRET_REDACTED>', text)
    return _MASKER.mask_text(text)
