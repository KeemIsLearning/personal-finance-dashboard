import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from pdf_parser import clean_transaction_description

def test_strips_pos_prefix():
    assert clean_transaction_description('POS PURCHASE WOOLWORTHS JHB 123456 ****4521') == 'Woolworths Jhb'

def test_strips_internet_trf_prefix():
    assert clean_transaction_description('INTERNET TRF TO NETFLIX') == 'Netflix'

def test_strips_immediate_pmt_prefix():
    assert clean_transaction_description('IMMEDIATE PMT SPOTIFY') == 'Spotify'

def test_strips_card_number():
    assert clean_transaction_description('ENGEN FUEL ****9912') == 'Engen Fuel'

def test_strips_long_ref_number():
    assert clean_transaction_description('WOOLWORTHS 12345678 JHB') == 'Woolworths Jhb'

def test_collapses_whitespace():
    assert clean_transaction_description('  PICK  N  PAY  ') == 'Pick N Pay'

def test_passthrough_clean_description():
    assert clean_transaction_description('Checkers Fourways') == 'Checkers Fourways'


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


import io
from pdf_parser import detect_pdf_type, _extract_table_rows, _extract_positional_rows
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
