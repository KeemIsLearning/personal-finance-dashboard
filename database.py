import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'finance.db')
#Connection helper - Comms between the dashboard and the dashboard
def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

#Creates the tables income, fixed expenses, variable/non-fixed expenses, exchange_rates
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS income (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source TEXT NOT NULL,
            amount_original REAL NOT NULL,
            currency TEXT NOT NULL DEFAULT 'ZAR',
            amount_zar REAL NOT NULL,
            rate_used REAL,
            date_received DATE NOT NULL,
            notes TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS fixed_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            person TEXT NOT NULL DEFAULT 'Kai',
            amount_zar REAL NOT NULL,
            description TEXT,
            is_recurring INTEGER NOT NULL DEFAULT 1,
            due_day INTEGER,
            date_logged DATE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS variable_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            amount_zar REAL NOT NULL,
            description TEXT,
            date_logged DATE NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS exchange_rates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rate_date DATE NOT NULL,
            usd_to_zar REAL NOT NULL,
            source TEXT NOT NULL DEFAULT 'Frankfurter API'
        )
    ''')

    conn.commit()
    conn.close()

#Income functions
def add_income(source, amount_original, currency, amount_zar, rate_used, date_received, notes):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO income (source, amount_original, currency, amount_zar, rate_used, date_received, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (source, amount_original, currency, amount_zar, rate_used, date_received, notes))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_income(year, month):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM income
        WHERE strftime('%Y', date_received) = ?
        AND strftime('%m', date_received) = ?
        ORDER BY date_received DESC
    ''', (str(year), str(month).zfill(2)))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_income(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM income WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()

def update_income(entry_id, source, amount_original, currency, amount_zar, rate_used, date_received, notes):
    conn = get_connection()
    conn.execute(
        'UPDATE income SET source=?, amount_original=?, currency=?, amount_zar=?, rate_used=?, date_received=?, notes=? WHERE id=?',
        (source, amount_original, currency, amount_zar, rate_used, date_received, notes, entry_id)
    )
    conn.commit()
    conn.close()

#Fixed and variable expense functions
def add_fixed_expense(category, person, amount_zar, description, is_recurring, due_day, date_logged):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO fixed_expenses (category, person, amount_zar, description, is_recurring, due_day, date_logged)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (category, person, amount_zar, description, is_recurring, due_day, date_logged))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_fixed_expenses(year, month):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM fixed_expenses
        WHERE strftime('%Y', date_logged) = ?
        AND strftime('%m', date_logged) = ?
        ORDER BY date_logged DESC
    ''', (str(year), str(month).zfill(2)))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_fixed_expense(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM fixed_expenses WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()

def update_fixed_expense(entry_id, category, person, amount_zar, description, is_recurring, due_day, date_logged):
    conn = get_connection()
    conn.execute(
        'UPDATE fixed_expenses SET category=?, person=?, amount_zar=?, description=?, is_recurring=?, due_day=?, date_logged=? WHERE id=?',
        (category, person, amount_zar, description, is_recurring, due_day, date_logged, entry_id)
    )
    conn.commit()
    conn.close()

def add_variable_expense(category, amount_zar, description, date_logged):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO variable_expenses (category, amount_zar, description, date_logged)
        VALUES (?, ?, ?, ?)
    ''', (category, amount_zar, description, date_logged))
    conn.commit()
    new_id = cursor.lastrowid
    conn.close()
    return new_id

def get_variable_expenses(year, month):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM variable_expenses
        WHERE strftime('%Y', date_logged) = ?
        AND strftime('%m', date_logged) = ?
        ORDER BY date_logged DESC
    ''', (str(year), str(month).zfill(2)))
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def delete_variable_expense(entry_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('DELETE FROM variable_expenses WHERE id = ?', (entry_id,))
    conn.commit()
    conn.close()

def update_variable_expense(entry_id, category, amount_zar, description, date_logged):
    conn = get_connection()
    conn.execute(
        'UPDATE variable_expenses SET category=?, amount_zar=?, description=?, date_logged=? WHERE id=?',
        (category, amount_zar, description, date_logged, entry_id)
    )
    conn.commit()
    conn.close()

#Exchange rates
def save_rate(rate_date, usd_to_zar):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO exchange_rates (rate_date, usd_to_zar)
        VALUES (?, ?)
    ''', (rate_date, usd_to_zar))
    conn.commit()
    conn.close()

def get_latest_rate():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT * FROM exchange_rates
        ORDER BY rate_date DESC
        LIMIT 1
    ''')
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_history():
    conn = get_connection()
    cursor = conn.cursor()

    results = []
    for i in range(5, -1, -1):
        cursor.execute('''
            SELECT
                strftime('%Y-%m', date_received) as month,
                SUM(amount_zar) as total_income
            FROM income
            WHERE date_received >= date('now', ? || ' months')
            AND date_received < date('now', ? || ' months')
            GROUP BY month
        ''', (f'-{i+1}', f'-{i}' if i > 0 else '+1'))

    cursor.execute('''
        SELECT
            strftime('%Y-%m', date_received) as month,
            SUM(amount_zar) as total_income
        FROM income
        WHERE date_received >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month ASC
    ''')
    income_rows = {row['month']: row['total_income'] for row in cursor.fetchall()}

    cursor.execute('''
        SELECT
            strftime('%Y-%m', date_logged) as month,
            SUM(amount_zar) as total_fixed
        FROM fixed_expenses
        WHERE date_logged >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month ASC
    ''')
    fixed_rows = {row['month']: row['total_fixed'] for row in cursor.fetchall()}

    cursor.execute('''
        SELECT
            strftime('%Y-%m', date_logged) as month,
            SUM(amount_zar) as total_variable
        FROM variable_expenses
        WHERE date_logged >= date('now', '-6 months')
        GROUP BY month
        ORDER BY month ASC
    ''')
    variable_rows = {row['month']: row['total_variable'] for row in cursor.fetchall()}

    all_months = sorted(set(list(income_rows.keys()) + list(fixed_rows.keys()) + list(variable_rows.keys())))

    for month in all_months:
        income = income_rows.get(month, 0)
        expenses = (fixed_rows.get(month, 0) + variable_rows.get(month, 0))
        results.append({
            'month': month,
            'income': income,
            'expenses': expenses,
            'balance': income - expenses
        })

    conn.close()
    return results


