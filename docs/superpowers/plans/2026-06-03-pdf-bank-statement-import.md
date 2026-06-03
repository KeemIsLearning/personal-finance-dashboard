# PDF Bank Statement Import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a PDF bank statement upload → parse → preview → confirm import flow to the existing Flask/SQLite finance dashboard, with zero DB writes until the user explicitly clicks Confirm.

**Architecture:** A new `pdf_parser.py` handles all pdfplumber extraction and rule-based classification in pure Python with no external API calls. Two new Flask routes (`/api/pdf/preview` and `/api/pdf/confirm`) wire the parser to the existing `database.py` insert functions. The frontend adds an Import Statement button, a full-screen preview modal with editable dropdowns per row, and a confirm step that POSTs the user's final choices.

**Tech Stack:** Python 3, pdfplumber 0.11.4, Flask (existing), SQLite via database.py (existing), vanilla JS (existing), CSS custom properties (existing dark-industrial amber theme).

---

## Schema Reference (actual columns — use these, not the PRD table)

| Table | Columns used on insert |
|---|---|
| `income` | `source`, `amount_original`, `currency='ZAR'`, `amount_zar`, `rate_used=None`, `date_received`, `notes` |
| `fixed_expenses` | `category`, `person='Kai'`, `amount_zar`, `description`, `is_recurring=0`, `due_day=None`, `date_logged` |
| `variable_expenses` | `category`, `amount_zar`, `description`, `date_logged` |

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `pdf_parser.py` | **Create** | All PDF extraction + classification logic |
| `server.py` | **Modify** | Add `/api/pdf/preview` and `/api/pdf/confirm` routes |
| `index.html` | **Modify** | Import button + modal HTML skeleton |
| `app.js` | **Modify** | Upload flow, preview renderer, confirm handler |
| `style.css` | **Modify** | Modal + confidence indicator styling |
| `requirements.txt` | **Create** | Pin pdfplumber==0.11.4 + existing deps |
| `tests/test_pdf_parser.py` | **Create** | Unit tests for all parser functions |

---

## Task 1: Project Dependencies

**Files:**
- Create: `requirements.txt`

- [ ] **Step 1: Check installed packages and create requirements.txt**

```
Flask==3.1.0
flask-cors==5.0.1
requests==2.32.3
pdfplumber==0.11.4
pytest==8.3.5
```

*(Adjust Flask/requests versions to match what's already installed — run `pip freeze` first and copy the pinned versions for Flask, flask-cors, and requests. Add pdfplumber and pytest.)*

- [ ] **Step 2: Install pdfplumber**

```
pip install pdfplumber==0.11.4
```

Expected: installs cleanly with pdfminer.six as a dependency.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add requirements.txt with pdfplumber dependency"
```

---

## Task 2: Description Cleaning (`pdf_parser.py`)

**Files:**
- Create: `pdf_parser.py`
- Create: `tests/test_pdf_parser.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/__init__.py` (empty file), then create `tests/test_pdf_parser.py`:

```python
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pdf_parser import clean_transaction_description

def test_strips_pos_prefix():
    assert clean_transaction_description('POS PURCHASE WOOLWORTHS JHB 123456 ****4521') == 'Woolworths JHB'

def test_strips_internet_trf_prefix():
    assert clean_transaction_description('INTERNET TRF TO NETFLIX') == 'Netflix'

def test_strips_immediate_pmt_prefix():
    assert clean_transaction_description('IMMEDIATE PMT SPOTIFY') == 'Spotify'

def test_strips_card_number():
    assert clean_transaction_description('ENGEN FUEL ****9912') == 'Engen Fuel'

def test_strips_long_ref_number():
    assert clean_transaction_description('WOOLWORTHS 12345678 JHB') == 'Woolworths JHB'

def test_collapses_whitespace():
    assert clean_transaction_description('  PICK  N  PAY  ') == 'Pick N Pay'

def test_passthrough_clean_description():
    assert clean_transaction_description('Checkers Fourways') == 'Checkers Fourways'
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_pdf_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'pdf_parser'`

- [ ] **Step 3: Create `pdf_parser.py` with `clean_transaction_description`**

```python
import re

_NOISE_PREFIXES = re.compile(
    r'^(POS PURCHASE|INTERNET TRF(?: TO)?|IMMEDIATE PMT|DEBIT ORDER|'
    r'PAYMENT TO|PAYMENT FROM|STO |EFT CREDIT|EFT DEBIT)\s*',
    re.IGNORECASE
)
_CARD_NUMBER = re.compile(r'\*{4}\d{4}')
_LONG_REF = re.compile(r'\b\d{8,}\b')
_MULTI_SPACE = re.compile(r' {2,}')


def clean_transaction_description(raw: str) -> str:
    s = raw.strip()
    s = _NOISE_PREFIXES.sub('', s)
    s = _CARD_NUMBER.sub('', s)
    s = _LONG_REF.sub('', s)
    s = _MULTI_SPACE.sub(' ', s).strip()
    return s.title()
```

- [ ] **Step 4: Run tests to confirm they pass**

```
pytest tests/test_pdf_parser.py -v
```

Expected: 7 PASSED.

- [ ] **Step 5: Commit**

```bash
git add pdf_parser.py tests/__init__.py tests/test_pdf_parser.py
git commit -m "feat(parser): add clean_transaction_description"
```

---

## Task 3: Transaction Classification (`pdf_parser.py`)

**Files:**
- Modify: `pdf_parser.py`
- Modify: `tests/test_pdf_parser.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pdf_parser.py`:

```python
from pdf_parser import classify_transaction

def test_classifies_salary_as_income():
    r = classify_transaction('Salary April', 28000.0, is_debit=False)
    assert r['type'] == 'income'
    assert r['category'] == 'Salary'
    assert r['confidence'] == 'high'

def test_classifies_transfer_in_as_income():
    r = classify_transaction('Payment Received John', 5000.0, is_debit=False)
    assert r['type'] == 'income'
    assert r['category'] == 'Transfer In'

def test_classifies_fixed_insurance():
    r = classify_transaction('Discovery Health Insurance', 1200.0, is_debit=True)
    assert r['type'] == 'fixed_expense'
    assert r['confidence'] == 'high'

def test_classifies_fixed_debit_order():
    r = classify_transaction('Debit Order Netflix', 199.0, is_debit=True)
    assert r['type'] == 'fixed_expense'

def test_classifies_woolworths_as_food():
    r = classify_transaction('Woolworths JHB', 420.0, is_debit=True)
    assert r['type'] == 'variable_expense'
    assert r['category'] == 'Food & Drink'
    assert r['confidence'] == 'high'

def test_classifies_uber_fuel_as_fuel():
    r = classify_transaction('Engen Fuel Station', 850.0, is_debit=True)
    assert r['type'] == 'variable_expense'
    assert r['category'] == 'Fuel'

def test_classifies_unknown_debit_as_variable_other():
    r = classify_transaction('Unknown Ref 8829', 150.0, is_debit=True)
    assert r['type'] == 'variable_expense'
    assert r['category'] == 'Other'
    assert r['confidence'] == 'medium'

def test_unclassified_when_debit_unknown():
    r = classify_transaction('', 0.0, is_debit=None)
    assert r['type'] == 'unclassified'
    assert r['confidence'] == 'low'
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_pdf_parser.py::test_classifies_salary_as_income -v
```

Expected: `ImportError` or `AttributeError`

- [ ] **Step 3: Add `classify_transaction` to `pdf_parser.py`**

Append to `pdf_parser.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_pdf_parser.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat(parser): add classify_transaction with keyword rules"
```

---

## Task 4: Header Detection & Amount Convention (`pdf_parser.py`)

**Files:**
- Modify: `pdf_parser.py`
- Modify: `tests/test_pdf_parser.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pdf_parser.py`:

```python
from pdf_parser import detect_column_positions, detect_amount_convention

def test_detect_date_and_description_columns():
    header = ['Date', 'Transaction Description', 'Debit', 'Credit', 'Balance']
    cols = detect_column_positions(header)
    assert cols['date'] == 0
    assert cols['description'] == 1
    assert cols['debit'] == 2
    assert cols['credit'] == 3
    assert cols['balance'] == 4
    assert cols['amount'] is None

def test_detect_single_amount_column():
    header = ['Value Date', 'Particulars', 'Amount', 'Running Balance']
    cols = detect_column_positions(header)
    assert cols['date'] == 0
    assert cols['description'] == 1
    assert cols['amount'] == 2
    assert cols['debit'] is None
    assert cols['credit'] is None

def test_detect_split_columns_convention():
    cols = {'debit': 2, 'credit': 3, 'amount': None}
    rows = [
        ['2025-05-01', 'Woolworths', '420.00', '', '10000.00'],
        ['2025-05-02', 'Salary', '', '28000.00', '38000.00'],
    ]
    assert detect_amount_convention(rows, cols) == 'split_columns'

def test_detect_signed_amount_convention():
    cols = {'debit': None, 'credit': None, 'amount': 2}
    rows = [
        ['2025-05-01', 'Woolworths', '-420.00', '10000.00'],
        ['2025-05-02', 'Salary', '28000.00', '38000.00'],
    ]
    assert detect_amount_convention(rows, cols) == 'signed_amount'

def test_detect_dr_cr_suffix_convention():
    cols = {'debit': None, 'credit': None, 'amount': 2}
    rows = [
        ['2025-05-01', 'Woolworths', '420.00 DR', '10000.00'],
        ['2025-05-02', 'Salary', '28000.00 CR', '38000.00'],
    ]
    assert detect_amount_convention(rows, cols) == 'dr_cr_suffix'
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_pdf_parser.py -k "detect" -v
```

Expected: `ImportError`

- [ ] **Step 3: Add the two detection functions to `pdf_parser.py`**

Append to `pdf_parser.py`:

```python
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
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_pdf_parser.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat(parser): add detect_column_positions and detect_amount_convention"
```

---

## Task 5: PDF Type Detection & Extraction Layers (`pdf_parser.py`)

**Files:**
- Modify: `pdf_parser.py`
- Modify: `tests/test_pdf_parser.py`

- [ ] **Step 1: Add failing tests**

Append to `tests/test_pdf_parser.py`:

```python
import io
from pdf_parser import detect_pdf_type, _extract_table_rows, _extract_positional_rows

# We can't embed a real PDF in tests, so we test the helpers with mocked pdfplumber pages.
# Use unittest.mock to avoid needing real PDFs for unit tests.
from unittest.mock import MagicMock, patch

def _make_mock_page(table=None, words=None):
    page = MagicMock()
    page.extract_table.return_value = table
    page.extract_words.return_value = words or []
    return page

def test_extract_table_rows_returns_rows_when_table_present():
    table = [
        ['Date', 'Description', 'Debit', 'Credit', 'Balance'],
        ['2025-05-01', 'Woolworths', '420.00', '', '10000.00'],
    ]
    page = _make_mock_page(table=table)
    rows = _extract_table_rows([page])
    assert rows == table

def test_extract_table_rows_returns_none_when_no_table():
    page = _make_mock_page(table=None)
    rows = _extract_table_rows([page])
    assert rows is None

def test_extract_positional_rows_groups_by_y():
    words = [
        {'text': 'Date', 'top': 10.0, 'x0': 5.0},
        {'text': 'Description', 'top': 10.0, 'x0': 50.0},
        {'text': '2025-05-01', 'top': 25.0, 'x0': 5.0},
        {'text': 'Woolworths', 'top': 25.0, 'x0': 50.0},
    ]
    page = _make_mock_page(words=words)
    rows = _extract_positional_rows([page])
    assert len(rows) == 2
    assert rows[0] == ['Date', 'Description']
    assert rows[1] == ['2025-05-01', 'Woolworths']
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_pdf_parser.py -k "extract or pdf_type" -v
```

Expected: `ImportError`

- [ ] **Step 3: Add extraction helpers to `pdf_parser.py`**

Append to `pdf_parser.py`:

```python
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
    """Return all rows from the first page that has a table, or None."""
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

    # Group by rounded Y
    buckets = {}
    for w in all_words:
        y_key = round(w['top'] / 3) * 3
        buckets.setdefault(y_key, []).append(w)

    rows = []
    for y_key in sorted(buckets):
        row_words = sorted(buckets[y_key], key=lambda w: w['x0'])
        rows.append([w['text'] for w in row_words])
    return rows
```

- [ ] **Step 4: Run tests**

```
pytest tests/test_pdf_parser.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat(parser): add PDF type detection and extraction layers"
```

---

## Task 6: Row Parsing & Main `parse_bank_statement` Entry Point (`pdf_parser.py`)

**Files:**
- Modify: `pdf_parser.py`
- Modify: `tests/test_pdf_parser.py`

- [ ] **Step 1: Add failing tests for row parsing and the main entry point**

Append to `tests/test_pdf_parser.py`:

```python
from pdf_parser import _parse_amount_cell, _rows_to_transactions, parse_bank_statement

def test_parse_amount_split_columns_debit():
    row = ['2025-05-01', 'Woolworths', '420.00', '', '10000.00']
    cols = {'date': 0, 'description': 1, 'debit': 2, 'credit': 3, 'amount': None, 'balance': 4}
    amount, is_debit = _parse_amount_cell(row, cols, 'split_columns')
    assert amount == 420.0
    assert is_debit is True

def test_parse_amount_split_columns_credit():
    row = ['2025-05-02', 'Salary', '', '28000.00', '38000.00']
    cols = {'date': 0, 'description': 1, 'debit': 2, 'credit': 3, 'amount': None, 'balance': 4}
    amount, is_debit = _parse_amount_cell(row, cols, 'split_columns')
    assert amount == 28000.0
    assert is_debit is False

def test_parse_amount_signed_negative():
    row = ['2025-05-01', 'Woolworths', '-420.00', '10000.00']
    cols = {'date': 0, 'description': 1, 'debit': None, 'credit': None, 'amount': 2, 'balance': 3}
    amount, is_debit = _parse_amount_cell(row, cols, 'signed_amount')
    assert amount == 420.0
    assert is_debit is True

def test_parse_amount_dr_cr_suffix_dr():
    row = ['2025-05-01', 'Woolworths', '420.00 DR', '10000.00']
    cols = {'date': 0, 'description': 1, 'debit': None, 'credit': None, 'amount': 2, 'balance': 3}
    amount, is_debit = _parse_amount_cell(row, cols, 'dr_cr_suffix')
    assert amount == 420.0
    assert is_debit is True

def test_rows_to_transactions_basic():
    rows = [
        ['Date', 'Description', 'Debit', 'Credit', 'Balance'],
        ['2025-05-01', 'Woolworths JHB', '420.00', '', '10000.00'],
    ]
    txns = _rows_to_transactions(rows)
    assert len(txns) == 1
    t = txns[0]
    assert t['date'] == '2025-05-01'
    assert t['amount'] == 420.0
    assert t['is_debit'] is True
    assert t['suggested_type'] == 'variable_expense'

def test_parse_bank_statement_image_pdf():
    """parse_bank_statement on a zero-text PDF returns a graceful error."""
    mock_pdf = MagicMock()
    mock_pdf.pages = [_make_mock_page(table=None, words=[])]
    mock_pdf.__enter__ = lambda s: s
    mock_pdf.__exit__ = MagicMock(return_value=False)

    with patch('pdf_parser.pdfplumber.open', return_value=mock_pdf):
        stream = io.BytesIO(b'fake')
        result = parse_bank_statement(stream)

    assert result['success'] is False
    assert result['error_type'] == 'image_pdf'
```

- [ ] **Step 2: Run tests to confirm they fail**

```
pytest tests/test_pdf_parser.py -k "parse_amount or rows_to or parse_bank" -v
```

Expected: `ImportError`

- [ ] **Step 3: Add `_parse_amount_cell`, `_rows_to_transactions`, and `parse_bank_statement` to `pdf_parser.py`**

Append to `pdf_parser.py`:

```python
import re as _re


def _parse_num(s: str) -> float:
    """Strip currency symbols, commas, spaces; return float."""
    cleaned = _re.sub(r'[R$£€,\s]', '', str(s or ''))
    try:
        return abs(float(cleaned.replace('DR', '').replace('CR', '')))
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
        val = float(_re.sub(r'[R$£€,\s]', '', raw))
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

    # Find header row — first row with a date-like or description-like keyword
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
```

- [ ] **Step 4: Run all tests**

```
pytest tests/test_pdf_parser.py -v
```

Expected: all PASSED.

- [ ] **Step 5: Commit**

```bash
git add pdf_parser.py tests/test_pdf_parser.py
git commit -m "feat(parser): complete parse_bank_statement entry point"
```

---

## Task 7: Flask Routes — `/api/pdf/preview` and `/api/pdf/confirm`

**Files:**
- Modify: `server.py`

- [ ] **Step 1: Add the import and the two routes to `server.py`**

Add `import pdf_parser` near the top of `server.py` (after the existing imports):

```python
import pdf_parser
```

Then append these two routes before the `if __name__ == '__main__':` line:

```python
# ── PDF Import routes ──────────────────────────────────────────────────────

@app.route('/api/pdf/preview', methods=['POST'])
def preview_pdf_import():
    if 'statement' not in request.files:
        return jsonify({'error': 'No file uploaded.'}), 400

    f = request.files['statement']

    if not f.filename.lower().endswith('.pdf') or f.mimetype not in ('application/pdf', 'application/octet-stream'):
        return jsonify({'error': 'Please upload a PDF file.'}), 400

    f.stream.seek(0, 2)
    size = f.stream.tell()
    f.stream.seek(0)
    if size > 10 * 1024 * 1024:
        return jsonify({'error': 'This file is too large. Please upload a PDF under 10MB.'}), 413

    result = pdf_parser.parse_bank_statement(f.stream)
    return jsonify(result)


@app.route('/api/pdf/confirm', methods=['POST'])
def confirm_pdf_import():
    data = request.get_json()
    transactions = data.get('transactions', [])

    inserted = 0
    skipped = 0
    errors = []

    for txn in transactions:
        confirmed_type = txn.get('confirmed_type', '')
        if confirmed_type == 'skip':
            skipped += 1
            continue

        try:
            if confirmed_type == 'income':
                database.add_income(
                    source=txn.get('confirmed_category', 'Other Income'),
                    amount_original=txn['amount'],
                    currency='ZAR',
                    amount_zar=txn['amount'],
                    rate_used=None,
                    date_received=txn['date'],
                    notes=txn.get('description', ''),
                )
            elif confirmed_type == 'fixed_expense':
                database.add_fixed_expense(
                    category=txn.get('confirmed_category', 'Other'),
                    person='Kai',
                    amount_zar=txn['amount'],
                    description=txn.get('description', ''),
                    is_recurring=0,
                    due_day=None,
                    date_logged=txn['date'],
                )
            elif confirmed_type == 'variable_expense':
                database.add_variable_expense(
                    category=txn.get('confirmed_category', 'Other'),
                    amount_zar=txn['amount'],
                    description=txn.get('description', ''),
                    date_logged=txn['date'],
                )
            else:
                errors.append({'row': txn, 'reason': f'Unknown type: {confirmed_type}'})
                continue

            inserted += 1

        except Exception as exc:
            errors.append({'row': txn, 'reason': str(exc)})

    return jsonify({'inserted': inserted, 'skipped': skipped, 'errors': errors})
```

- [ ] **Step 2: Test with curl (server must be running)**

Start server: `python server.py`

Test rejection of non-PDF:
```
curl -X POST http://localhost:5000/api/pdf/preview -F "statement=@README.md"
```
Expected: `{"error": "Please upload a PDF file."}`

Test confirm with empty list:
```
curl -X POST http://localhost:5000/api/pdf/confirm \
  -H "Content-Type: application/json" \
  -d '{"transactions": []}'
```
Expected: `{"inserted": 0, "skipped": 0, "errors": []}`

- [ ] **Step 3: Commit**

```bash
git add server.py
git commit -m "feat(server): add /api/pdf/preview and /api/pdf/confirm routes"
```

---

## Task 8: HTML — Import Button & Modal Skeleton

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add the import button to the header**

In `index.html`, locate the `<div class="month-nav">` block inside `<div class="header-right">`. Add the button and hidden input **before** `<div class="month-nav">`:

```html
      <!-- PDF Import -->
      <input type="file" id="pdf-upload-input" accept=".pdf" style="display:none">
      <button id="pdf-import-btn" class="btn-industrial">&#8659; Import Statement</button>
```

- [ ] **Step 2: Add the modal overlay at the bottom of `<body>`, before the closing `</body>` tag**

```html
<!-- PDF IMPORT PREVIEW MODAL -->
<div id="pdf-modal-overlay" class="pdf-modal-overlay hidden" role="dialog" aria-modal="true" aria-labelledby="pdf-modal-title">
  <div class="pdf-modal">

    <div class="pdf-modal-header">
      <span class="pdf-modal-title" id="pdf-modal-title">IMPORT PREVIEW</span>
      <button class="pdf-modal-close" id="pdf-modal-close" aria-label="Cancel import">&#10005; Cancel</button>
    </div>

    <div class="pdf-modal-summary" id="pdf-modal-summary">
      <!-- Populated by JS: "Found X transactions · Y high confidence" -->
    </div>

    <div class="pdf-modal-table-wrap">
      <table class="pdf-preview-table" id="pdf-preview-table">
        <thead>
          <tr>
            <th><input type="checkbox" id="pdf-select-all" title="Select all"></th>
            <th>Date</th>
            <th>Description</th>
            <th>Amount</th>
            <th>Type</th>
            <th>Category</th>
            <th>Conf.</th>
          </tr>
        </thead>
        <tbody id="pdf-preview-tbody">
          <!-- Populated by JS -->
        </tbody>
      </table>
    </div>

    <div class="pdf-modal-footer">
      <div class="pdf-modal-error hidden" id="pdf-modal-error"></div>
      <button class="btn-industrial btn-confirm" id="pdf-confirm-btn" disabled>Confirm Import</button>
    </div>

  </div>
</div>

<!-- Loading overlay (shown while parsing PDF) -->
<div id="pdf-loading-overlay" class="pdf-loading-overlay hidden">
  <div class="pdf-spinner"></div>
  <span class="pdf-loading-label">PARSING STATEMENT…</span>
</div>
```

- [ ] **Step 3: Verify the page still loads without JS errors**

Open `http://localhost:5000` in the browser. The Import Statement button should appear in the header. The modal should not be visible. Open DevTools console — no errors.

- [ ] **Step 4: Commit**

```bash
git add index.html
git commit -m "feat(html): add PDF import button and modal skeleton"
```

---

## Task 9: JavaScript — Upload Flow, Preview Renderer, Confirm Handler

**Files:**
- Modify: `app.js`

- [ ] **Step 1: Append the PDF import module to the bottom of `app.js`**

```javascript
// ── PDF Import ─────────────────────────────────────────────────────────────

const CATEGORY_OPTIONS = {
  income: ['Salary', 'Transfer In', 'Rental Income', 'Other Income'],
  fixed_expense: ['Rent', 'Insurance', 'Subscription', 'Medical Aid', 'Loan Repayment', 'Utilities', 'Other'],
  variable_expense: ['Food & Drink', 'Fuel', 'Transport', 'Shopping', 'Gaming', 'Clothing', 'Other'],
};

function initialisePdfImport() {
  const btn = document.getElementById('pdf-import-btn');
  const input = document.getElementById('pdf-upload-input');
  btn.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    if (input.files[0]) handlePdfFileSelected(input.files[0]);
    input.value = '';
  });
  document.getElementById('pdf-modal-close').addEventListener('click', closePdfModal);
  document.getElementById('pdf-confirm-btn').addEventListener('click', confirmImport);
  document.getElementById('pdf-select-all').addEventListener('change', e => {
    document.querySelectorAll('.pdf-row-check').forEach(cb => cb.checked = e.target.checked);
    updateConfirmButtonState();
  });
}

async function handlePdfFileSelected(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Please upload a PDF file.', 'error'); return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast('This file is too large. Please upload a PDF under 10MB.', 'error'); return;
  }

  showPdfLoading(true);
  try {
    const form = new FormData();
    form.append('statement', file);
    const res = await fetch(`${API}/pdf/preview`, { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showToast(data.error || 'Failed to parse PDF.', 'error');
      return;
    }
    renderPreviewModal(data);
  } catch (err) {
    showToast('Could not reach the server. Is it running?', 'error');
  } finally {
    showPdfLoading(false);
  }
}

function renderPreviewModal(parsedData) {
  const { transactions, summary } = parsedData;

  // Summary bar
  document.getElementById('pdf-modal-summary').innerHTML =
    `Found <strong>${summary.total_transactions}</strong> transactions &nbsp;·&nbsp; ` +
    `<span class="conf-high">&#9679; ${summary.high_confidence} high</span> &nbsp; ` +
    `<span class="conf-medium">&#9675; ${summary.medium_confidence} medium</span> &nbsp; ` +
    `<span class="conf-low">&#9675; ${summary.low_confidence} low &#9888;</span> &nbsp;|&nbsp; ` +
    `Credits: <strong>R ${summary.total_credits.toFixed(2)}</strong> &nbsp; ` +
    `Debits: <strong>R ${summary.total_debits.toFixed(2)}</strong>`;

  // Table body
  const tbody = document.getElementById('pdf-preview-tbody');
  tbody.innerHTML = '';

  transactions.forEach((txn, i) => {
    const isLow = txn.confidence === 'low';
    const isUnclassified = txn.suggested_type === 'unclassified';
    const tr = document.createElement('tr');
    if (isLow || isUnclassified) tr.classList.add('row-low-conf');

    const confIcon = txn.confidence === 'high' ? '<span class="conf-high">&#9679; HIGH</span>'
      : txn.confidence === 'medium' ? '<span class="conf-medium">&#9675; MED</span>'
      : '<span class="conf-low">&#9675; LOW &#9888;</span>';

    tr.innerHTML = `
      <td><input type="checkbox" class="pdf-row-check" data-idx="${i}" checked></td>
      <td>${txn.date}</td>
      <td title="${txn.raw_description}">${txn.description}</td>
      <td>R ${txn.amount.toFixed(2)}</td>
      <td>
        <select class="pdf-type-select" data-idx="${i}">
          ${isUnclassified ? '<option value="">— Select —</option>' : ''}
          <option value="income"${txn.suggested_type === 'income' ? ' selected' : ''}>Income</option>
          <option value="variable_expense"${txn.suggested_type === 'variable_expense' ? ' selected' : ''}>Variable Expense</option>
          <option value="fixed_expense"${txn.suggested_type === 'fixed_expense' ? ' selected' : ''}>Fixed Expense</option>
          <option value="skip">Skip</option>
        </select>
      </td>
      <td>
        <select class="pdf-cat-select" data-idx="${i}"></select>
      </td>
      <td>${confIcon}</td>
    `;

    tbody.appendChild(tr);

    const typeSelect = tr.querySelector('.pdf-type-select');
    const catSelect = tr.querySelector('.pdf-cat-select');
    updateCategoryOptions(typeSelect, catSelect, txn.suggested_category);
    typeSelect.addEventListener('change', () => {
      updateCategoryOptions(typeSelect, catSelect, null);
      updateConfirmButtonState();
    });
    tr.querySelector('.pdf-row-check').addEventListener('change', updateConfirmButtonState);
  });

  document.getElementById('pdf-modal-overlay').classList.remove('hidden');
  document.getElementById('pdf-modal-error').classList.add('hidden');
  updateConfirmButtonState();
}

function updateCategoryOptions(typeSelect, catSelect, preselect) {
  const type = typeSelect.value;
  const options = CATEGORY_OPTIONS[type] || [];
  catSelect.innerHTML = options.map(o =>
    `<option value="${o}"${preselect === o ? ' selected' : ''}>${o}</option>`
  ).join('');
  if (!preselect && options.length) catSelect.value = options[0];
}

function updateConfirmButtonState() {
  const confirmBtn = document.getElementById('pdf-confirm-btn');
  const rows = document.querySelectorAll('#pdf-preview-tbody tr');
  let allValid = true;
  rows.forEach(tr => {
    const cb = tr.querySelector('.pdf-row-check');
    if (cb && cb.checked) {
      const typeSelect = tr.querySelector('.pdf-type-select');
      if (!typeSelect.value) allValid = false;
    }
  });
  confirmBtn.disabled = !allValid;
}

function closePdfModal() {
  document.getElementById('pdf-modal-overlay').classList.add('hidden');
}

async function confirmImport() {
  const rows = document.querySelectorAll('#pdf-preview-tbody tr');
  const transactions = [];

  rows.forEach(tr => {
    const cb = tr.querySelector('.pdf-row-check');
    const idx = parseInt(tr.querySelector('[data-idx]').dataset.idx);
    const typeSelect = tr.querySelector('.pdf-type-select');
    const catSelect = tr.querySelector('.pdf-cat-select');

    // Reconstruct minimal txn data from DOM
    const cells = tr.querySelectorAll('td');
    const date = cells[1].textContent.trim();
    const description = cells[2].textContent.trim();
    const amountText = cells[3].textContent.replace('R', '').trim();
    const amount = parseFloat(amountText);

    transactions.push({
      date,
      description,
      amount,
      confirmed_type: cb.checked ? typeSelect.value : 'skip',
      confirmed_category: catSelect.value || 'Other',
    });
  });

  const confirmBtn = document.getElementById('pdf-confirm-btn');
  confirmBtn.disabled = true;
  confirmBtn.textContent = 'Importing…';

  try {
    const res = await fetch(`${API}/pdf/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transactions }),
    });
    const data = await res.json();

    if (!res.ok) {
      showImportError('Import failed. Please try again.');
      return;
    }

    closePdfModal();
    const msg = data.errors.length
      ? `${data.inserted} imported, ${data.errors.length} failed.`
      : `${data.inserted} transactions imported successfully.`;
    showToast(msg, data.errors.length ? 'warn' : 'success');

    // Refresh dashboard data
    loadAll();

  } catch (err) {
    showImportError('Could not reach the server.');
  } finally {
    confirmBtn.disabled = false;
    confirmBtn.textContent = 'Confirm Import';
  }
}

function showImportError(msg) {
  const el = document.getElementById('pdf-modal-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function showPdfLoading(show) {
  document.getElementById('pdf-loading-overlay').classList.toggle('hidden', !show);
}

function showToast(msg, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add('toast-visible'), 10);
  setTimeout(() => { toast.classList.remove('toast-visible'); setTimeout(() => toast.remove(), 400); }, 3500);
}
```

- [ ] **Step 2: Call `initialisePdfImport()` in the existing `DOMContentLoaded` init block**

Find the existing `document.addEventListener('DOMContentLoaded', ...)` or equivalent init call in `app.js` and add `initialisePdfImport();` at the end of it.

If the init is spread across multiple `addEventListener` calls, add a single new one:

```javascript
document.addEventListener('DOMContentLoaded', initialisePdfImport);
```

- [ ] **Step 3: Check for `loadAll` function name**

Search `app.js` for the function that reloads all dashboard data (income, fixed, variable). It may be named `loadAll`, `refreshDashboard`, `loadDashboard`, etc. Update the call inside `confirmImport()` to match whatever the actual function name is.

```
grep -n "function load\|function refresh" app.js
```

- [ ] **Step 4: Commit**

```bash
git add app.js
git commit -m "feat(js): add PDF import upload flow, preview renderer, and confirm handler"
```

---

## Task 10: CSS — Modal Styling

**Files:**
- Modify: `style.css`

- [ ] **Step 1: Append PDF modal styles to `style.css`**

```css
/* ── PDF Import Modal ─────────────────────────────────────────────────── */

.pdf-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.85);
  z-index: 1000;
  display: flex;
  align-items: flex-start;
  justify-content: center;
  padding: 2rem 1rem;
  overflow-y: auto;
}

.pdf-modal-overlay.hidden { display: none; }

.pdf-modal {
  background: #1a1a1a;
  border: 1px solid #c8a84b;
  width: 100%;
  max-width: 960px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.pdf-modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid #2e2e2e;
}

.pdf-modal-title {
  font-family: 'Share Tech Mono', monospace;
  color: #c8a84b;
  font-size: 1rem;
  letter-spacing: 0.15em;
}

.pdf-modal-close {
  background: none;
  border: 1px solid #444;
  color: #aaa;
  padding: 0.3rem 0.7rem;
  cursor: pointer;
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.8rem;
  transition: border-color 0.2s, color 0.2s;
}
.pdf-modal-close:hover { border-color: #c8a84b; color: #c8a84b; }

.pdf-modal-summary {
  padding: 0.75rem 1.25rem;
  font-size: 0.8rem;
  color: #888;
  border-bottom: 1px solid #2e2e2e;
  font-family: 'Share Tech Mono', monospace;
}

.conf-high  { color: #c8a84b; }
.conf-medium { color: #888; }
.conf-low   { color: #c8a84b; font-weight: bold; }

.pdf-modal-table-wrap {
  overflow-x: auto;
  max-height: 55vh;
  overflow-y: auto;
}

.pdf-preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.82rem;
  font-family: 'Share Tech Mono', monospace;
}

.pdf-preview-table thead {
  position: sticky;
  top: 0;
  background: #222;
  z-index: 2;
}

.pdf-preview-table th {
  color: #c8a84b;
  text-align: left;
  padding: 0.6rem 0.75rem;
  border-bottom: 1px solid #333;
  font-weight: 600;
  letter-spacing: 0.05em;
  font-size: 0.75rem;
}

.pdf-preview-table td {
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid #222;
  color: #ccc;
  vertical-align: middle;
}

.pdf-preview-table tr:hover td { background: #232323; }

.pdf-preview-table tr.row-low-conf {
  border-left: 3px solid #c8a84b;
}

/* Dropdowns in table */
.pdf-preview-table select {
  background: #111;
  border: 1px solid #333;
  color: #ccc;
  padding: 0.25rem 0.4rem;
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.78rem;
  -webkit-appearance: none;
  appearance: none;
  cursor: pointer;
}
.pdf-preview-table select:focus { outline: 1px solid #c8a84b; }

.pdf-modal-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 1rem;
  padding: 1rem 1.25rem;
  border-top: 1px solid #2e2e2e;
}

.pdf-modal-error {
  color: #e05252;
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.82rem;
}
.pdf-modal-error.hidden { display: none; }

/* Import Statement header button */
.btn-industrial {
  background: none;
  border: 1px solid #c8a84b;
  color: #c8a84b;
  padding: 0.35rem 0.85rem;
  cursor: pointer;
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.78rem;
  letter-spacing: 0.08em;
  transition: background 0.2s, color 0.2s;
}
.btn-industrial:hover { background: #c8a84b; color: #111; }
.btn-industrial:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-confirm {
  padding: 0.5rem 1.5rem;
}

/* Loading overlay */
.pdf-loading-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.7);
  z-index: 2000;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1rem;
}
.pdf-loading-overlay.hidden { display: none; }

.pdf-spinner {
  width: 36px;
  height: 36px;
  border: 3px solid #333;
  border-top-color: #c8a84b;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin { to { transform: rotate(360deg); } }

.pdf-loading-label {
  color: #c8a84b;
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.85rem;
  letter-spacing: 0.1em;
}

/* Toast notifications */
.toast {
  position: fixed;
  bottom: 2rem;
  right: 2rem;
  background: #1a1a1a;
  border: 1px solid #c8a84b;
  color: #ccc;
  padding: 0.75rem 1.25rem;
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.82rem;
  z-index: 3000;
  opacity: 0;
  transform: translateY(10px);
  transition: opacity 0.3s, transform 0.3s;
  max-width: 360px;
}
.toast.toast-visible { opacity: 1; transform: translateY(0); }
.toast.toast-error { border-color: #e05252; }
.toast.toast-warn  { border-color: #c8a84b; }
.toast.toast-success { border-color: #4caf50; }
```

- [ ] **Step 2: Confirm no visual regressions**

Open `http://localhost:5000`. The existing dashboard should look unchanged. The Import Statement button should appear in the header with amber styling.

- [ ] **Step 3: Commit**

```bash
git add style.css
git commit -m "feat(css): add PDF import modal and toast styling"
```

---

## Task 11: End-to-End Manual Verification

- [ ] **Check 1: Non-PDF rejection**

Click "Import Statement" → select a `.txt` or image file → confirm error toast appears ("Please upload a PDF file.") and the modal does not open.

- [ ] **Check 2: Oversized file rejection (client-side)**

If you have a PDF > 10MB, selecting it should show the size error toast immediately (no network request).

- [ ] **Check 3: Parse a real bank statement PDF**

Upload an FNB or any digital bank statement PDF. The loading spinner should appear, then the preview modal should open with rows in the table. Check that:
- Descriptions are cleaned (no `****1234` patterns)
- Types are pre-selected (not all blank)
- Low-confidence rows have amber left border and `○ LOW ⚠` indicator

- [ ] **Check 4: Unclassified row blocks Confirm**

If any row shows `— Select —` in the Type column, the Confirm Import button should remain disabled until you either choose a type or uncheck that row.

- [ ] **Check 5: Uncheck rows, then confirm**

Uncheck 3 rows → click Confirm Import → success toast shows correct number (`N transactions imported`) → unchecked rows are absent from the DB.

- [ ] **Check 6: Change type before confirm**

Find a Variable Expense row → change Type to Income → change Category to Salary → Confirm → verify in the dashboard (or directly in `finance.db`) that it landed in the `income` table.

- [ ] **Check 7: Dashboard refresh after import**

After a successful import, the month totals should update automatically (the `loadAll()` call in `confirmImport` triggers this).

- [ ] **Step: Final commit if any fixes were made during verification**

```bash
git add -A
git commit -m "fix: manual verification fixes"
```

---

## Notes for Executor

- **`loadAll` function name:** In Task 9 Step 3, you must grep `app.js` to confirm the actual name of the function that refreshes all dashboard data. If it doesn't exist (data loads only on page-load), add a `window.location.reload()` as a temporary fallback and flag it.
- **DB schema note:** The `income` table uses `date_received` (not `date`). Fixed and variable expenses use `date_logged`. The confirm route in Task 7 already uses the correct column names via `database.add_*` functions.
- **No `requirements.txt` existed** before this feature — Task 1 creates it from scratch using `pip freeze` to pin the existing deps.
- **MIME type check in preview route:** Some browsers send `application/octet-stream` for PDFs. The route allows both `application/pdf` and `application/octet-stream` to avoid false rejections; the `.pdf` extension check is the primary guard.
