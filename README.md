# Personal Finance Dashboard

A dark-industrial personal finance tracker built with HTML, CSS, JavaScript, Python (Flask), and SQLite. Runs entirely on your local machine — no cloud storage, no subscriptions, no data leaving your device.

Built as a portfolio project for [P4THF1ND3R](https://p4thf1nd3r.netlify.app)

---

## Features

- **Income tracking** — Log salary, freelance income, rental income, and any other sources
- **Fixed expense tracking** — Recurring committed costs: subscriptions, services, pass-through purchases
- **Variable expense tracking** — Day-to-day personal spending: fuel, food, clothing, entertainment, and anything else
- **Automatic date stamping** — Every entry records the exact date it was logged; the dashboard reads today's date from the system clock on every open
- **Live USD/ZAR exchange rate** — Fetched automatically from the [Frankfurter API](https://frankfurter.dev) (no API key needed), cached hourly
- **Rate history log** — Every fetched rate is saved to the database, building a personal record of USD/ZAR movement over time
- **Built-in USD ↔ ZAR converter** — Inline currency converter using the live rate
- **Currency conversion preview** — Shows the ZAR equivalent before you confirm an entry, locked to the rate at that exact moment
- **Daily rate sparkline** — Visual of USD/ZAR movement throughout the current month
- **Monthly history chart** — Bar + line chart comparing income, expenses, and net balance over the past 6 months
- **Month navigation** — Browse any past or future month's data
- **Persistent storage** — All data stored in a local SQLite database (`finance.db`) on your machine

---

## Architecture

```
Browser (index.html + app.js)
        ↕  HTTP requests via fetch()
Flask Server (server.py) — localhost:5000
        ↕  SQL queries
SQLite Database (finance.db)
```

The frontend handles display and user input. The Flask backend handles all data logic. The SQLite database stores everything permanently in a single file on your machine.

---

## Database Schema

Four tables:

| Table | Purpose |
|---|---|
| `income` | Every payment received — salary, foreign currency income, or other |
| `fixed_expenses` | Recurring committed costs with due dates and optional per-person tracking |
| `variable_expenses` | Day-to-day personal spending by category |
| `exchange_rates` | Historical log of every USD/ZAR rate fetched |

Income entries that use USD→ZAR conversion store both the original USD amount and the exact rate used, so the conversion is permanently auditable.

---

## Project Structure

```
finance-dashboard/
├── index.html       — Dashboard layout and structure
├── style.css        — Dark industrial theme (charcoal + amber)
├── app.js           — Frontend logic: API calls, charts, forms, date handling
├── server.py        — Flask backend: API routes, request handling
├── database.py      — All SQLite logic: schema creation, queries, inserts
├── finance.db       — Auto-created on first run (do not commit to Git)
└── README.md        — This file
```

---

## How to Run

### Requirements

- Python 3.8 or higher
- pip

### Install dependencies

```bash
pip install flask flask-cors
```

SQLite is built into Python — no separate install needed.

### Start the server

```bash
cd finance-dashboard
python server.py
```

The server starts on `http://localhost:5000`. Open that URL in your browser. The `finance.db` file is created automatically on first run.

### Stop the server

`Ctrl + C` in the terminal.

---

## Data & Privacy

Everything stays on your machine. The only external request the app makes is:

- A GET to `api.frankfurter.dev` to fetch the live USD/ZAR rate — no personal data is sent, only the currency pair is requested

Your `finance.db` file contains all your financial entries. It is listed in `.gitignore` and will not be committed to GitHub. Keep a manual backup copy if needed.

---

## Tech Stack

| Layer | Choice | Reason |
|---|---|---|
| Markup | HTML5 | No framework overhead |
| Styling | CSS3 (custom properties) | Full control, no build step |
| Frontend logic | Vanilla JavaScript | No dependencies |
| Charts | [Chart.js 4.4](https://chartjs.org) | CDN-loaded, zero config |
| Fonts | [Google Fonts](https://fonts.google.com) — Barlow Condensed, Barlow, Share Tech Mono | Industrial character |
| Backend | [Flask](https://flask.palletsprojects.com) + [flask-cors](https://flask-cors.readthedocs.io) | Lightweight Python server |
| Database | SQLite via Python `sqlite3` | Local-first, single file, no server process |
| FX API | [Frankfurter API](https://frankfurter.dev) | Free, no key, central bank sourced |

---

## API Endpoints (Flask)

Once the server is running, these are the routes `app.js` communicates with:

| Method | Route | Purpose |
|---|---|---|
| `GET` | `/api/income/:year/:month` | Fetch all income entries for a month |
| `POST` | `/api/income` | Add a new income entry |
| `DELETE` | `/api/income/:id` | Delete an income entry |
| `GET` | `/api/fixed/:year/:month` | Fetch fixed expenses for a month |
| `POST` | `/api/fixed` | Add a fixed expense entry |
| `DELETE` | `/api/fixed/:id` | Delete a fixed expense entry |
| `GET` | `/api/variable/:year/:month` | Fetch variable expenses for a month |
| `POST` | `/api/variable` | Add a variable expense entry |
| `DELETE` | `/api/variable/:id` | Delete a variable expense entry |
| `GET` | `/api/rate` | Get latest cached exchange rate |
| `POST` | `/api/rate` | Save a fetched rate to history |
| `GET` | `/api/history` | Get 6-month summary for history chart |

---

## .gitignore

`finance.db` is excluded from version control by default.

---

## Screenshots



---

## Roadmap

- [ ] Flask backend + SQLite schema (in progress)
- [ ] Frontend updated to call Flask API instead of localStorage
- [ ] Monthly summary export (CSV)
- [ ] Upcoming fixed expense warnings
- [ ] Per-category spending breakdown chart

---

## License

MIT — use it, fork it, build on it.
