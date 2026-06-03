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


def _parse_num(s: str) -> float:
    """Strip currency symbols, commas, spaces, DR/CR suffixes; return float."""
    raw = str(s or '').strip().upper()
    # Remove DR/CR suffix first (before stripping R which is in DR/CR)
    raw = re.sub(r'\s*(DR|CR)\s*$', '', raw)
    # Now strip currency symbols, commas, whitespace
    cleaned = re.sub(r'[R$£€,\s]', '', raw)
    try:
        return abs(float(cleaned))
    except ValueError:
        return 0.0


def _parse_amount_cell(row: list, cols: dict, convention: str):
    """Return (amount: float, is_debit: bool | None)."""
    if convention == 'split_columns':
        debit_idx = cols.get('debit')
        credit_idx = cols.get('credit')
        debit_val = _parse_num(row[debit_idx]) if debit_idx is not None and debit_idx < len(row) else 0.0
        credit_val = _parse_num(row[credit_idx]) if credit_idx is not None and credit_idx < len(row) else 0.0
        if debit_val > 0:
            return debit_val, True
        if credit_val > 0:
            return credit_val, False
        return 0.0, None

    amt_idx = cols.get('amount')
    raw = str(row[amt_idx]).strip().upper() if amt_idx is not None and amt_idx < len(row) else ''

    if convention == 'dr_cr_suffix':
        amount = _parse_num(raw)
        is_debit = raw.endswith('DR')
        return amount, is_debit

    # signed_amount
    try:
        val = float(re.sub(r'[R$£€,\s]', '', raw))
    except ValueError:
        return 0.0, None
    return abs(val), val < 0


def _parse_date(raw: str) -> str:
    """Normalise various date formats to YYYY-MM-DD. Returns raw string on failure."""
    raw = (raw or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
        try:
            from datetime import datetime
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    return raw


def _rows_to_transactions(rows: list) -> list:
    """Convert raw row list (with header) into transaction dicts."""
    if not rows:
        return []

    header_idx = 0
    cols = None
    for i, row in enumerate(rows):
        candidate = detect_column_positions([str(c) for c in row])
        if candidate['date'] is not None and candidate['description'] is not None:
            cols = candidate
            header_idx = i
            break

    if cols is None:
        return []

    data_rows = rows[header_idx + 1:]
    convention = detect_amount_convention(data_rows, cols)

    transactions = []
    for row in data_rows:
        if not row or all((c or '').strip() == '' for c in row):
            continue

        date_idx = cols.get('date')
        desc_idx = cols.get('description')
        raw_date = row[date_idx] if date_idx is not None and date_idx < len(row) else ''
        raw_desc = row[desc_idx] if desc_idx is not None and desc_idx < len(row) else ''

        if not raw_date or not raw_desc:
            continue

        amount, is_debit = _parse_amount_cell(row, cols, convention)
        if amount == 0.0 and is_debit is None:
            continue

        clean_desc = clean_transaction_description(str(raw_desc))
        classification = classify_transaction(clean_desc, amount, is_debit)

        transactions.append({
            'date': _parse_date(str(raw_date)),
            'description': clean_desc,
            'raw_description': str(raw_desc),
            'amount': amount,
            'is_debit': is_debit,
            'suggested_type': classification['type'],
            'suggested_category': classification['category'],
            'confidence': classification['confidence'],
        })

    return transactions


def parse_bank_statement(pdf_file_stream) -> dict:
    """Entry point. Accepts a file-like stream. Never writes to disk."""
    try:
        with pdfplumber.open(pdf_file_stream) as pdf:
            pages = pdf.pages
            pdf_type = detect_pdf_type(pages)

            if pdf_type == 'image':
                return {
                    'success': False,
                    'error': (
                        'This PDF appears to be a scanned document. '
                        'Text extraction is not supported for scanned statements yet. '
                        'Try downloading your statement directly from your bank\'s online portal as a digital PDF.'
                    ),
                    'error_type': 'image_pdf',
                    'transactions': [],
                    'summary': {},
                }

            if pdf_type == 'table':
                rows = _extract_table_rows(pages)
            else:
                rows = _extract_positional_rows(pages)

            transactions = _rows_to_transactions(rows or [])

            if not transactions:
                return {
                    'success': False,
                    'error': (
                        'No transactions could be found in this document. '
                        'The format may be unsupported. Check that you\'re uploading a bank '
                        'statement or transaction history, not a general account summary.'
                    ),
                    'error_type': 'no_transactions_found',
                    'transactions': [],
                    'summary': {},
                }

            high = sum(1 for t in transactions if t['confidence'] == 'high')
            medium = sum(1 for t in transactions if t['confidence'] == 'medium')
            low = sum(1 for t in transactions if t['confidence'] == 'low')

            return {
                'success': True,
                'error': None,
                'error_type': None,
                'transactions': transactions,
                'summary': {
                    'total_transactions': len(transactions),
                    'high_confidence': high,
                    'medium_confidence': medium,
                    'low_confidence': low,
                    'total_credits': round(sum(t['amount'] for t in transactions if not t['is_debit']), 2),
                    'total_debits': round(sum(t['amount'] for t in transactions if t['is_debit']), 2),
                },
            }

    except Exception as exc:
        return {
            'success': False,
            'error': f'Could not read this PDF: {exc}',
            'error_type': 'parse_error',
            'transactions': [],
            'summary': {},
        }
