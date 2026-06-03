import re

_NOISE_PREFIXES = re.compile(
    r'^(POS PURCHASE|INTERNET TRF(?: TO)?|IMMEDIATE PMT|DEBIT ORDER|'
    r'PAYMENT TO|PAYMENT FROM|STO |EFT CREDIT|EFT DEBIT)\s*',
    re.IGNORECASE
)
_CARD_NUMBER = re.compile(r'\*{4}\d{4}')
_LONG_REF = re.compile(r'\b\d{6,}\b')
_MULTI_SPACE = re.compile(r' {2,}')


def clean_transaction_description(raw: str) -> str:
    s = raw.strip()
    s = _NOISE_PREFIXES.sub('', s)
    s = _CARD_NUMBER.sub('', s)
    s = _LONG_REF.sub('', s)
    s = _MULTI_SPACE.sub(' ', s).strip()
    return s.title()
