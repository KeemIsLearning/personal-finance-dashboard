import re

_NOISE_PREFIXES = re.compile(
    r'^(POS PURCHASE|INTERNET TRF(?: TO)?|IMMEDIATE PMT|DEBIT ORDER|'
    r'PAYMENT TO|PAYMENT FROM|STO |EFT CREDIT|EFT DEBIT)\s*',
    re.IGNORECASE
)
_CARD_NUMBER = re.compile(r'\*{4}\d{4}|\d{6}\*\d{4}')
_LONG_REF = re.compile(r'\b\d{6,}\b')
_TRAILING_DATE = re.compile(r'\s+\d{1,2}\s+[A-Za-z]{3}\s*$')
_MULTI_SPACE = re.compile(r'[ \t]{2,}')
# FNB prepends original-currency amount to description: "23.00 CLAUDE.AI SUB"
_LEADING_AMOUNT = re.compile(r'^\d[\d,]*\.\d+\s+')


def clean_transaction_description(raw: str) -> str:
    s = raw.strip()
    # Strip leading # (FNB bank fee rows)
    s = s.lstrip('#').strip()
    # Normalize newlines from multi-line PDF cells to spaces
    s = s.replace('\n', ' ').replace('\r', ' ')
    s = _NOISE_PREFIXES.sub('', s)
    s = _LEADING_AMOUNT.sub('', s)
    s = _CARD_NUMBER.sub('', s)
    s = _LONG_REF.sub('', s)
    s = _TRAILING_DATE.sub('', s)
    s = _MULTI_SPACE.sub(' ', s).strip()
    return s.title()


_INCOME_KEYWORDS = {
    'Salary':        ['salary', 'payroll', 'remuneration', 'investec', 'magtape credit'],
    'Transfer In':   ['transfer', 'trf', 'payment received', 'payment from', 'pmt from',
                      'ob pmt', 'payshap credit', 'rtc credit', 'int-banking pmt frm',
                      'fnb app payment from', 'cash deposit', 'adt cash deposit',
                      'payshap account on-us', 'fnb app transfer from'],
    'Rental Income': ['rent', 'rental'],
}

_FIXED_KEYWORDS = [
    'debit order', 'subscription', 'insurance', 'dstv', 'netflix', 'spotify',
    'medical aid', 'municipal', 'rates', 'levy', 'bond', 'loan repayment',
]

_VARIABLE_KEYWORDS = {
    'Food & Drink': ['woolworths', 'pick n pay', 'pnp', 'checkers', 'spar', 'restaurant',
                     'kfc', 'mcdonalds', 'mcdonald', 'mcd ', 'uber eats', 'mr d', 'nando',
                     'steers', 'debonairs', 'kauai', 'federal', 'spicy world', 'kingsley',
                     'all spicy', 'hpy*', 'yoco', 'ons winkel', 'ccn*'],
    'Fuel':         ['fuel', 'engen', 'shell', 'bp', 'total', 'caltex', 'sasol'],
    'Transport':    ['uber', 'bolt', 'taxi', 'gautrain', 'metrobus', 'indrive'],
    'Shopping':     ['zara', 'h&m', 'mr price', 'mrd', 'edgars', 'superbalist', 'takealot',
                     'exclusive books', 'postnet', 'greenside', 'kwekery', 'paygate'],
    'Gaming':       ['steam', 'playstation', 'xbox', 'psn', 'nintendo', 'apple.com',
                     'claude.ai'],
    'Clothing':     ['clothing', 'sneakers', 'shoes', 'fashion', 'cotton on', 'fancy face'],
    'ATM Cash':     ['atm cash'],
    'Airtime':      ['prepaid airtime', 'airtime'],
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
    amt_idx = column_positions.get('amount')
    if amt_idx is not None:
        has_cr = False
        has_dr = False
        for row in rows[:20]:
            if amt_idx < len(row):
                val = str(row[amt_idx] or '').strip().upper()
                if val.endswith('CR'):
                    has_cr = True
                elif val.endswith('DR'):
                    has_dr = True
        if has_cr and has_dr:
            return 'dr_cr_suffix'
        if has_cr:
            # Credits marked Cr, debits are plain numbers (FNB style)
            return 'cr_suffix_only'
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


_DATE_FMTS = ('%d %b %Y', '%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d %b', '%d %B')
_DR_CR = re.compile(r'-?\d[\d,.]*\s*(DR|CR)$', re.IGNORECASE)


def _looks_like_date(s: str) -> bool:
    from datetime import datetime
    s = (s or '').strip()
    for fmt in _DATE_FMTS:
        try:
            datetime.strptime(s, fmt)
            return True
        except ValueError:
            continue
    return False


def _extract_table_rows(pages: list):
    """
    Return all rows from pages that have a usable table, or None.
    Handles both headed tables (with Date/Description header row) and
    headerless tables where the column labels are outside the table border.
    """
    all_rows = []
    for page in pages:
        table = page.extract_table()
        if not table or len(table) < 1 or len(table[0]) < 3:
            continue

        header_lower = [str(c or '').lower() for c in table[0]]
        has_date = any('date' in h for h in header_lower)
        has_desc = any(h in header_lower
                       for h in ('description', 'details', 'particulars', 'narrative'))

        if has_date and has_desc:
            # Headed table — validate amount column isn't crammed into one cell
            amt_idx = next((i for i, h in enumerate(header_lower) if 'amount' in h), None)
            if amt_idx is not None:
                data_rows = table[1:]
                non_none = sum(
                    1 for row in data_rows
                    if amt_idx < len(row) and row[amt_idx] is not None
                )
                if non_none < max(1, len(data_rows) * 0.1):
                    continue
            all_rows.extend(table)

        else:
            # Possibly headerless: column labels are outside the table border.
            # Detect by checking whether col 0 of most rows looks like a date
            # and col 3 (or last-1) contains DR/CR amounts.
            n_cols = len(table[0])
            date_hits = sum(1 for row in table[:5] if _looks_like_date(str(row[0] or '')))
            if date_hits < 2:
                continue
            amt_col = n_cols - 2  # second-to-last column is typically amount
            dr_cr_hits = sum(
                1 for row in table[:5]
                if amt_col < len(row) and _DR_CR.search(str(row[amt_col] or ''))
            )
            if dr_cr_hits < 1:
                continue
            # Build synthetic header matching detect_column_positions keywords
            synth = ['date', 'description'] + ['fee'] * (n_cols - 4) + ['amount', 'balance']
            all_rows.append(synth)
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


_AMOUNT_LIKE = re.compile(r'^[\d,]+\.\d+(Cr|Dr)?$', re.IGNORECASE)
_MONTH_ABBR = re.compile(
    r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)$', re.IGNORECASE
)


def _extract_positional_table_rows(pages: list):
    """
    Heuristic positional row parser for bank statements that lack PDF table borders.

    For each word-row:
      - Date  : first two words matching <digit> <month-abbr>
      - Balance: last amount-like word ending with Cr or Dr
      - Amount : the amount-like word immediately before the balance
      - Description: everything in between

    Returns column-aligned string rows (like _extract_table_rows), or None.
    """
    # Collect all word rows (sorted by X within each Y bucket)
    all_rows = []
    for page in pages:
        words = page.extract_words()
        if not words:
            continue
        buckets = {}
        for w in words:
            y_key = round(w['top'] / 3) * 3
            buckets.setdefault(y_key, []).append(w)
        for y_key in sorted(buckets):
            row_words = sorted(buckets[y_key], key=lambda w: w['x0'])
            all_rows.append([w['text'] for w in row_words])

    if not all_rows:
        return None

    result = [['date', 'description', 'amount', 'balance']]

    for texts in all_rows:
        # Row must start with a day number followed by a month abbreviation
        if len(texts) < 4:
            continue
        if not texts[0].isdecimal() or not _MONTH_ABBR.match(texts[1]):
            continue

        date_str = f'{texts[0]} {texts[1]}'
        remaining = texts[2:]

        # Find balance: last token ending with Cr or Dr
        balance_idx = None
        for j in range(len(remaining) - 1, -1, -1):
            val = remaining[j]
            if _AMOUNT_LIKE.match(val) and re.search(r'(Cr|Dr)$', val, re.IGNORECASE):
                balance_idx = j
                break

        if balance_idx is None:
            continue

        # Amount: the token immediately before balance that looks like an amount
        if balance_idx > 0 and _AMOUNT_LIKE.match(remaining[balance_idx - 1]):
            amount_idx = balance_idx - 1
        else:
            continue  # can't identify a distinct amount column

        balance = remaining[balance_idx]
        amount = remaining[amount_idx]
        description = ' '.join(remaining[:amount_idx]).strip()

        result.append([date_str, description, amount, balance])

    return result if len(result) > 1 else None


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

    if convention in ('dr_cr_suffix', 'cr_suffix_only'):
        amount = _parse_num(raw)
        if convention == 'dr_cr_suffix':
            is_debit = raw.endswith('DR')
        else:  # cr_suffix_only: Cr = credit, no suffix = debit
            is_debit = not raw.endswith('CR')
        return amount, is_debit

    # signed_amount
    try:
        val = float(re.sub(r'[R$£€,\s]', '', raw))
    except ValueError:
        return 0.0, None
    return abs(val), val < 0


def _parse_date(raw: str) -> str:
    """Normalise various date formats to YYYY-MM-DD. Returns raw string on failure."""
    from datetime import datetime
    raw = (raw or '').strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y', '%Y/%m/%d', '%d %b %Y', '%d %B %Y'):
        try:
            return datetime.strptime(raw, fmt).strftime('%Y-%m-%d')
        except ValueError:
            continue
    # FNB style: '06 Feb' with no year — default to current year
    for fmt in ('%d %b', '%d %B'):
        try:
            dt = datetime.strptime(raw, fmt)
            return dt.replace(year=datetime.now().year).strftime('%Y-%m-%d')
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

        # Skip repeated page-header rows (e.g. "Date" / "Description" at top of each page)
        if not _looks_like_date(str(raw_date)):
            continue

        # Skip FNB bank fee rows (description starts with #)
        if str(raw_desc).strip().startswith('#'):
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

            # Fall back to positional extraction if table extraction failed or
            # produced an unusable result (e.g. amounts crammed into one cell)
            if pdf_type != 'table' or not rows:
                rows = _extract_positional_table_rows(pages) or _extract_positional_rows(pages)

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
