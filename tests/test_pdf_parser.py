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
