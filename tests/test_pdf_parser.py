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
