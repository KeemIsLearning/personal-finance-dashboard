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


_INCOME_KEYWORDS = {
    'Salary':        ['salary', 'payroll', 'remuneration'],
    'Transfer In':   ['transfer', 'trf', 'payment received'],
    'Rental Income': ['rent', 'rental'],
}

_FIXED_KEYWORDS = [
    'debit order', 'subscription', 'insurance', 'dstv', 'netflix', 'spotify',
    'medical aid', 'municipal', 'rates', 'levy', 'bond', 'loan repayment',
]

_VARIABLE_KEYWORDS = {
    'Food & Drink': ['woolworths', 'pick n pay', 'checkers', 'spar', 'restaurant',
                     'kfc', 'mcdonalds', 'mcdonald', 'uber eats', 'mr d', 'nando'],
    'Fuel':         ['fuel', 'engen', 'shell', 'bp', 'total', 'caltex', 'sasol'],
    'Transport':    ['uber', 'bolt', 'taxi', 'gautrain', 'metrobus'],
    'Shopping':     ['zara', 'h&m', 'mr price', 'edgars', 'superbalist', 'takealot'],
    'Gaming':       ['steam', 'playstation', 'xbox', 'psn', 'nintendo'],
    'Clothing':     ['clothing', 'sneakers', 'shoes', 'fashion'],
}


def classify_transaction(description: str, amount: float, is_debit) -> dict:
    if is_debit is None:
        return {'type': 'unclassified', 'category': 'Unknown', 'confidence': 'low'}

    desc_lower = description.lower()

    if not is_debit:
        for category, keywords in _INCOME_KEYWORDS.items():
            if any(kw in desc_lower for kw in keywords):
                return {'type': 'income', 'category': category, 'confidence': 'high'}
        return {'type': 'income', 'category': 'Other Income', 'confidence': 'high'}

    # is_debit = True — check fixed first
    for kw in _FIXED_KEYWORDS:
        if kw in desc_lower:
            return {'type': 'fixed_expense', 'category': 'Subscription', 'confidence': 'high'}

    # variable expense
    for category, keywords in _VARIABLE_KEYWORDS.items():
        if any(kw in desc_lower for kw in keywords):
            return {'type': 'variable_expense', 'category': category, 'confidence': 'high'}

    return {'type': 'variable_expense', 'category': 'Other', 'confidence': 'medium'}


_COLUMN_PATTERNS = {
    'date':        ['date', 'transaction date', 'value date', 'posted'],
    'description': ['description', 'details', 'narrative', 'reference',
                    'particulars', 'trans description'],
    'debit':       ['debit', 'dr', 'withdrawal', 'payments out', 'money out'],
    'credit':      ['credit', 'cr', 'deposit', 'payments in', 'money in'],
    'amount':      ['amount', 'value'],
    'balance':     ['balance', 'running balance', 'available'],
}


def detect_column_positions(header_row: list) -> dict:
    result = {k: None for k in _COLUMN_PATTERNS}
    for idx, cell in enumerate(header_row):
        cell_lower = (cell or '').lower().strip()
        for role, keywords in _COLUMN_PATTERNS.items():
            if result[role] is not None:
                continue
            if any(kw in cell_lower for kw in keywords):
                result[role] = idx
                break
    return result


def detect_amount_convention(rows: list, column_positions: dict) -> str:
    if column_positions.get('debit') is not None and column_positions.get('credit') is not None:
        return 'split_columns'
    # single amount column — check for DR/CR suffix first
    amt_idx = column_positions.get('amount')
    if amt_idx is not None:
        for row in rows[:5]:
            if amt_idx < len(row):
                val = str(row[amt_idx]).strip().upper()
                if val.endswith('DR') or val.endswith('CR'):
                    return 'dr_cr_suffix'
        return 'signed_amount'
    return 'split_columns'


import pdfplumber


def detect_pdf_type(pages: list) -> str:
    """Returns 'table', 'positional', or 'image'."""
    has_text = False
    for page in pages:
        words = page.extract_words()
        if words:
            has_text = True
        table = page.extract_table()
        if table and len(table) > 1 and len(table[0]) >= 3:
            return 'table'
    return 'positional' if has_text else 'image'


def _extract_table_rows(pages: list):
    """Return all rows from pages that have a table, or None."""
    all_rows = []
    for page in pages:
        table = page.extract_table()
        if table and len(table) > 1 and len(table[0]) >= 3:
            all_rows.extend(table)
    return all_rows if all_rows else None


def _extract_positional_rows(pages: list) -> list:
    """Reconstruct rows by grouping words with same Y coordinate (±3px)."""
    all_words = []
    for page in pages:
        all_words.extend(page.extract_words())

    if not all_words:
        return []

    buckets = {}
    for w in all_words:
        y_key = round(w['top'] / 3) * 3
        buckets.setdefault(y_key, []).append(w)

    rows = []
    for y_key in sorted(buckets):
        row_words = sorted(buckets[y_key], key=lambda w: w['x0'])
        rows.append([w['text'] for w in row_words])
    return rows
