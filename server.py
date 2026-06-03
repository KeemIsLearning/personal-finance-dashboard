from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import database
import pdf_parser
import os
import json
import requests as _requests
from datetime import date, datetime

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(__file__)

@app.route('/')
def index():
    return send_from_directory(BASE_DIR, 'index.html')

@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(BASE_DIR, filename)

database.init_db()

#Income routes
@app.route('/api/income/<int:year>/<int:month>', methods=['GET'])
def get_income(year, month):
    entries = database.get_income(year, month)
    return jsonify(entries)

@app.route('/api/income', methods=['POST'])
def add_income():
    data = request.get_json()
    new_id = database.add_income(
        source=data['source'],
        amount_original=data['amount_original'],
        currency=data['currency'],
        amount_zar=data['amount_zar'],
        rate_used=data.get('rate_used'),
        date_received=data['date_received'],
        notes=data.get('notes', '')
    )
    return jsonify({'id': new_id}), 201

@app.route('/api/income/<int:entry_id>', methods=['DELETE'])
def delete_income(entry_id):
    database.delete_income(entry_id)
    return jsonify({'deleted': entry_id})

@app.route('/api/income/<int:entry_id>', methods=['PUT'])
def update_income(entry_id):
    d = request.get_json()
    database.update_income(entry_id, d['source'], d['amount_original'], d['currency'],
                           d['amount_zar'], d.get('rate_used'), d['date_received'], d.get('notes', ''))
    return jsonify({'updated': entry_id})

#Fixed expense routes
@app.route('/api/fixed/<int:year>/<int:month>', methods=['GET'])
def get_fixed(year, month):
    entries = database.get_fixed_expenses(year, month)
    return jsonify(entries)

@app.route('/api/fixed', methods=['POST'])
def add_fixed():
    data = request.get_json()
    new_id = database.add_fixed_expense(
        category=data['category'],
        person=data.get('person', 'Kai'),
        amount_zar=data['amount_zar'],
        description=data.get('description', ''),
        is_recurring=data.get('is_recurring', 1),
        due_day=data.get('due_day'),
        date_logged=data.get('date_logged', str(date.today()))
    )
    return jsonify({'id': new_id}), 201

@app.route('/api/fixed/<int:entry_id>', methods=['DELETE'])
def delete_fixed(entry_id):
    database.delete_fixed_expense(entry_id)
    return jsonify({'deleted': entry_id})

@app.route('/api/fixed/<int:entry_id>', methods=['PUT'])
def update_fixed(entry_id):
    d = request.get_json()
    database.update_fixed_expense(entry_id, d['category'], d.get('person', 'Kai'), d['amount_zar'],
                                  d.get('description', ''), d.get('is_recurring', 1), d.get('due_day'), d['date_logged'])
    return jsonify({'updated': entry_id})

#Non-fixed expense routes
@app.route('/api/variable/<int:year>/<int:month>', methods=['GET'])
def get_variable(year, month):
    entries = database.get_variable_expenses(year, month)
    return jsonify(entries)

@app.route('/api/variable', methods=['POST'])
def add_variable():
    data = request.get_json()
    new_id = database.add_variable_expense(
        category=data['category'],
        amount_zar=data['amount_zar'],
        description=data.get('description', ''),
        date_logged=data.get('date_logged', str(date.today()))
    )
    return jsonify({'id': new_id}), 201

@app.route('/api/variable/<int:entry_id>', methods=['DELETE'])
def delete_variable(entry_id):
    database.delete_variable_expense(entry_id)
    return jsonify({'deleted': entry_id})

@app.route('/api/variable/<int:entry_id>', methods=['PUT'])
def update_variable(entry_id):
    d = request.get_json()
    database.update_variable_expense(entry_id, d['category'], d['amount_zar'],
                                     d.get('description', ''), d['date_logged'])
    return jsonify({'updated': entry_id})

#Exchange rate routes
@app.route('/api/rate', methods=['GET'])
def get_rate():
    rate = database.get_latest_rate()
    if rate:
        return jsonify(rate)
    return jsonify({'error': 'No rate saved yet'}), 404

@app.route('/api/rate', methods=['POST'])
def save_rate():
    data = request.get_json()
    database.save_rate(
        rate_date=data['rate_date'],
        usd_to_zar=data['usd_to_zar']
    )
    return jsonify({'saved': True}), 201

#History route
@app.route('/api/history', methods=['GET'])
def get_history():
    data = database.get_history()
    return jsonify(data)

#Budget config routes
BUDGET_PATH = os.path.join(BASE_DIR, 'budget.json')
BUDGET_EXAMPLE_PATH = os.path.join(BASE_DIR, 'budget.example.json')

def _ensure_budget_file():
    """Create budget.json from the example template if it doesn't exist yet."""
    if not os.path.exists(BUDGET_PATH):
        import shutil
        shutil.copy(BUDGET_EXAMPLE_PATH, BUDGET_PATH)

@app.route('/api/budget', methods=['GET'])
def get_budget():
    _ensure_budget_file()
    with open(BUDGET_PATH, 'r') as f:
        return jsonify(json.load(f))

@app.route('/api/budget', methods=['PUT'])
def update_budget():
    with open(BUDGET_PATH, 'w') as f:
        json.dump(request.get_json(), f, indent=2)
    return jsonify({'saved': True})

#FX proxy routes
@app.route('/api/fx/latest')
def fx_latest():
    def _fetch_all():
        r = _requests.get(
            'https://api.frankfurter.dev/v1/latest?from=ZAR&to=USD,EUR,GBP', timeout=5
        )
        if not r.ok:
            raise Exception(f'HTTP {r.status_code}')
        d = r.json()
        return {
            'date': d['date'],
            'rates': {k: round(1 / v, 6) for k, v in d['rates'].items()}
        }

    try:
        result = _fetch_all()
        return (json.dumps(result), 200, {'Content-Type': 'application/json'})
    except Exception:
        pass

    # Fallback: open.er-api.com
    try:
        r = _requests.get('https://open.er-api.com/v6/latest/ZAR', timeout=5)
        d = r.json()
        rates_raw = d.get('rates', {})
        ts = d.get('time_last_update_unix', 0)
        date_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d') if ts else ''
        result = {
            'date': date_str,
            'rates': {k: round(1 / rates_raw[k], 6) for k in ('USD', 'EUR', 'GBP') if rates_raw.get(k)}
        }
        return (json.dumps(result), 200, {'Content-Type': 'application/json'})
    except Exception as exc:
        return (json.dumps({'error': str(exc)}), 503, {'Content-Type': 'application/json'})

@app.route('/api/fx/history')
def fx_history():
    from_ = request.args.get('from', '')
    to = request.args.get('to', '')

    try:
        date.fromisoformat(from_)
        date.fromisoformat(to)
    except ValueError:
        return (json.dumps({'error': 'Invalid date parameters. Use YYYY-MM-DD.'}), 400, {'Content-Type': 'application/json'})

    if date.fromisoformat(from_) > date.fromisoformat(to):
        return (json.dumps({'error': 'from must not be after to'}), 400, {'Content-Type': 'application/json'})

    try:
        r = _requests.get(
            f'https://api.frankfurter.dev/v1/{from_}..{to}?from=ZAR&to=USD,EUR,GBP', timeout=5
        )
        if not r.ok:
            raise Exception(f'HTTP {r.status_code}')
        d = r.json()
        inverted = {
            date_key: {k: round(1 / v, 6) for k, v in day_rates.items()}
            for date_key, day_rates in d.get('rates', {}).items()
        }
        return (json.dumps({'rates': inverted}), 200, {'Content-Type': 'application/json'})
    except Exception:
        pass

    # Fallback: return latest rates only (open.er-api.com has no date-range endpoint)
    try:
        r = _requests.get('https://open.er-api.com/v6/latest/ZAR', timeout=5)
        d = r.json()
        rates_raw = d.get('rates', {})
        ts = d.get('time_last_update_unix', 0)
        today_str = datetime.utcfromtimestamp(ts).strftime('%Y-%m-%d') if ts else ''
        day = {k: round(1 / rates_raw[k], 6) for k in ('USD', 'EUR', 'GBP') if rates_raw.get(k)}
        return (json.dumps({'rates': {today_str: day}}), 200, {'Content-Type': 'application/json'})
    except Exception as exc:
        return (json.dumps({'error': str(exc)}), 503, {'Content-Type': 'application/json'})

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

if __name__ == '__main__':
    app.run(debug=True, port=5000)