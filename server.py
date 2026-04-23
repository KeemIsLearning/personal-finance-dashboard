from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import database
import os
import json
import requests as _requests
from datetime import date

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

@app.route('/api/budget', methods=['GET'])
def get_budget():
    if not os.path.exists(BUDGET_PATH):
        return jsonify({'income': 0, 'baseline': [], 'optional': [], 'rules': [], 'selectedOptional': None})
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
    r = _requests.get('https://api.frankfurter.app/latest?from=USD&to=ZAR', timeout=5)
    return (r.content, r.status_code, {'Content-Type': 'application/json'})

@app.route('/api/fx/history')
def fx_history():
    from_ = request.args.get('from')
    to = request.args.get('to')
    r = _requests.get(f'https://api.frankfurter.app/{from_}..{to}?from=USD&to=ZAR', timeout=5)
    return (r.content, r.status_code, {'Content-Type': 'application/json'})

if __name__ == '__main__':
    app.run(debug=True, port=5000)