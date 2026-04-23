"""
import_april.py
One-time script to bulk insert April 2026 transactions into finance.db
Run once from the finance-dashboard folder:
    python import_april.py
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'finance.db')

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# ---------------------------------------------------------------
# INCOME
# All amounts in ZAR. Currency = ZAR unless noted.
# ---------------------------------------------------------------
income = [
    # (source, amount_original, currency, amount_zar, rate_used, date_received, notes)

    # Salary already entered manually via dashboard - skip if already in db
    # Leftover money already entered manually - skip

    # Father sending money via FNB
    ("other", 250.00, "ZAR", 250.00, None, "2026-04-16", "FNB Pmt from Dad"),

    # Mom paying back + extra for purchases done on her behalf
    ("other", 700.00, "ZAR", 700.00, None, "2026-04-18", "Argent De Poche - Mom payback + extra"),

    # Friend N Nthontho paying back the R90 owed
    ("other", 90.00, "ZAR", 90.00, None, "2026-04-15", "N Nthontho - friend payback"),

    # Uncle's wife - cash deposit (loan to be repaid after school fees cleared)
    ("other", 8780.00, "ZAR", 8780.00, None, "2026-04-10", "ADT Cash Depo Makabu - Uncle wife loan (repay after Eduvos)"),
    ("other", 200.00, "ZAR", 200.00, None, "2026-04-10", "ADT Cash Depo Extra - Uncle wife loan"),
]

# ---------------------------------------------------------------
# FIXED EXPENSES
# Committed recurring or large fixed costs
# ---------------------------------------------------------------
fixed = [
    # (category, person, amount_zar, description, is_recurring, due_day, date_logged)

    # Bank fees - monthly recurring
    ("subscriptions", "Kai", 33.00,    "FNB Service Fees",         1, 4, "2026-04-04"),
    ("subscriptions", "Kai", 7.50,     "FNB Monthly Account Fee",  1, 4, "2026-04-04"),

    # School fees - Eduvos
    ("school", "Kai", 7550.00, "Eduvos school fees April", 1, 10, "2026-04-10"),

    # Father's pass-through payments - non-recurring, logged under his name
    ("other", "Dad", 10000.00, "Car - Dad pass-through",          0, None, "2026-04-01"),
    ("other", "Dad", 9550.00,  "Plk El 14 - Dad pass-through",   0, None, "2026-04-01"),
    ("other", "Dad", 14300.00, "Plk Lw 17 - Dad pass-through",   0, None, "2026-04-01"),
    ("other", "Dad", 4000.00,  "Plk Mangaung - Dad pass-through",0, None, "2026-04-01"),
]

# ---------------------------------------------------------------
# VARIABLE EXPENSES
# Personal day-to-day spending
# ---------------------------------------------------------------
variable = [
    # (category, amount_zar, description, date_logged)

    # --- April 1 ---
    ("subscriptions", 549.00, "PlayStation purchase (31 Mar)",    "2026-04-01"),
    ("other",          13.73, "Int Pymt Fee - PlayStation 549",   "2026-04-01"),

    # --- April 4 ---
    ("other",           4.23, "Int Pymt Fee - PlayStation 169",   "2026-04-04"),
    ("other",           8.00, "Byc Debit",                        "2026-04-04"),
    ("other",         166.60, "Cash Deposit Fee",                 "2026-04-04"),
    ("subscriptions", 169.00, "PlayStation purchase (1 Apr)",     "2026-04-04"),
    ("other",           5.00, "Federal Loch Logan - Parking",     "2026-04-04"),

    # --- April 7 ---
    ("subscriptions", 599.99, "Apple.com subscription (4 Apr)",   "2026-04-07"),
    ("other",          15.00, "Int Pymt Fee - Apple 599.99",      "2026-04-07"),
    ("food",          376.90, "Mr D food delivery (3 Apr)",       "2026-04-07"),

    # --- April 9 ---
    ("other",          10.00, "Federal Loch Logan - Parking",     "2026-04-09"),
    ("other",         250.00, "ATM Cash Preller withdrawal",      "2026-04-09"),

    # --- April 10 ---
    ("food",          172.79, "PnP Fam Langenhoven groceries",    "2026-04-10"),
    ("other",           1.00, "EFT Charge FNB",                   "2026-04-10"),
    ("other",         250.00, "ATM Cash Preller withdrawal",      "2026-04-10"),

    # --- April 11 ---
    ("subscriptions", 1499.00,"PlayStation purchase (9 Apr)",     "2026-04-11"),
    ("other",           37.48,"Int Pymt Fee - PlayStation 1499",  "2026-04-11"),
    ("other",           10.32,"Byc Debit",                        "2026-04-11"),

    # --- April 13 ---
    ("fuel",          600.00, "Engen Crossing fuel (10 Apr)",     "2026-04-13"),
    ("other",         813.50, "Exclusive Books Loch Logan",       "2026-04-13"),
    ("other",          79.00, "Smart-Ap Prepaid Airtime",         "2026-04-13"),

    # --- April 14 ---
    ("other",          90.00, "Payment to friend (N Nthontho)",   "2026-04-14"),

    # --- April 15 ---
    ("food",          315.60, "Steers Langenhoven",               "2026-04-15"),
    ("clothing",      249.00, "Cotton On Loch Logan",             "2026-04-15"),
    ("other",           5.00, "Federal Loch Logan - Parking",     "2026-04-15"),

    # --- April 16 ---
    ("subscriptions",  79.99, "Apple.com billing (15 Apr)",       "2026-04-16"),
    ("other",           2.00, "Int Pymt Fee - Apple 79.99",       "2026-04-16"),
    ("other",         250.00, "ATM Cash withdrawal",              "2026-04-16"),

    # --- April 17 ---
    ("subscriptions",  39.00, "PlayStation purchase (15 Apr)",    "2026-04-17"),

    # --- April 18 ---
    ("other",          14.91, "Byc Debit",                        "2026-04-18"),
]

# ---------------------------------------------------------------
# INSERT FUNCTIONS
# ---------------------------------------------------------------
def insert_income(conn, entries):
    cursor = conn.cursor()
    count = 0
    for source, amount_original, currency, amount_zar, rate_used, date_received, notes in entries:
        cursor.execute('''
            INSERT INTO income
                (source, amount_original, currency, amount_zar, rate_used, date_received, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (source, amount_original, currency, amount_zar, rate_used, date_received, notes))
        count += 1
    return count

def insert_fixed(conn, entries):
    cursor = conn.cursor()
    count = 0
    for category, person, amount_zar, description, is_recurring, due_day, date_logged in entries:
        cursor.execute('''
            INSERT INTO fixed_expenses
                (category, person, amount_zar, description, is_recurring, due_day, date_logged)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (category, person, amount_zar, description, is_recurring, due_day, date_logged))
        count += 1
    return count

def insert_variable(conn, entries):
    cursor = conn.cursor()
    count = 0
    for category, amount_zar, description, date_logged in entries:
        cursor.execute('''
            INSERT INTO variable_expenses
                (category, amount_zar, description, date_logged)
            VALUES (?, ?, ?, ?)
        ''', (category, amount_zar, description, date_logged))
        count += 1
    return count

# ---------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------
if __name__ == '__main__':
    conn = get_connection()

    try:
        income_count   = insert_income(conn, income)
        fixed_count    = insert_fixed(conn, fixed)
        variable_count = insert_variable(conn, variable)

        conn.commit()

        print(f"Import complete:")
        print(f"  Income entries inserted:   {income_count}")
        print(f"  Fixed expenses inserted:   {fixed_count}")
        print(f"  Variable expenses inserted:{variable_count}")
        print(f"  Total rows:                {income_count + fixed_count + variable_count}")
        print()
        print("Note: If you already entered your salary and 'leftover money'")
        print("via the dashboard, those are NOT duplicated here.")
        print("The Mrd pending R-573.80 was skipped (not yet cleared).")

    except Exception as e:
        conn.rollback()
        print(f"Error during import: {e}")
        raise

    finally:
        conn.close()
