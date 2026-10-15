"""PII masking. Models and rules read text_norm; people read only text_masked."""
import re

_PHONE = re.compile(r'(?<!\d)(?:\+?91[\s-]?)?[6-9]\d{9}(?!\d)')
_EMAIL = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
_URL = re.compile(r'https?://\S+')


def mask_pii(t):
    t = _EMAIL.sub('[EMAIL]', t)
    t = _URL.sub('[URL]', t)
    return _PHONE.sub('[PHONE]', t)
