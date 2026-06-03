# Multi-Currency FX Toggle — Design Spec
Date: 2026-06-03

## Overview

Add USD / EUR / GBP toggle buttons to the FX panel. All three rates are fetched in a single API call on load. Switching currencies is instant (no extra network call). The header pill, panel title, big rate display, converter, and sparkline all update to reflect the active currency.

---

## Server (`server.py`)

### `/api/fx/latest` (GET)
- Call `GET https://api.frankfurter.dev/v1/latest?from=ZAR&to=USD,EUR,GBP`
- Invert each rate: `ZAR_per_X = 1 / rate_ZAR_to_X`
- Return:
  ```json
  { "date": "2026-06-03", "rates": { "USD": 16.27, "EUR": 17.86, "GBP": 21.04 } }
  ```
- Fallback to `open.er-api.com` on failure, mapped to the same shape.

### `/api/fx/history` (GET, params: `from`, `to`)
- Call `GET https://api.frankfurter.dev/v1/{from}..{to}?from=ZAR&to=USD,EUR,GBP`
- Invert each daily rate for each currency.
- Return:
  ```json
  {
    "rates": {
      "2026-06-01": { "USD": 16.20, "EUR": 17.80, "GBP": 20.90 },
      "2026-06-02": { "USD": 16.27, "EUR": 17.86, "GBP": 21.04 }
    }
  }
  ```
- Fallback: return latest rates only (no history range available from open.er-api.com).

---

## State (`app.js`)

Replace:
```js
state.rate = null
state.rateUpdated = null
```

With:
```js
state.rates = { USD: null, EUR: null, GBP: null }
state.activeCurrency = 'USD'
state.rateUpdated = null
state.sparklineDataAll = { USD: [], EUR: [], GBP: [] }
```

Remove `state.sparklineData` (replaced by `state.sparklineDataAll`).

---

## JS Functions (`app.js`)

### `fetchRate(forceRefresh)`
- Checks localStorage cache (`pf_fx_cache`) — now stores `{ rates, updated, timestamp }`.
- On cache miss or force refresh: calls `/api/fx/latest`, populates `state.rates` and `state.rateUpdated`.
- Also calls `fetchSparklineData()` to populate `state.sparklineDataAll`.
- Calls `applyRate()` to render.

### `applyRate()`
- Reads `state.rates[state.activeCurrency]` and `state.activeCurrency`.
- Updates:
  - Header pill label: `{CURRENCY}/ZAR`
  - Header pill value: `state.rates[activeCurrency].toFixed(4)`
  - `statRate`, `rateSub`: same
  - `fxBigNumber`: rate
  - `fxUnit`: `ZAR per {CURRENCY}`
  - Panel title: `{CURRENCY} / ZAR EXCHANGE`
  - Converter left tag: `{CURRENCY}`
  - Sparkline label: `{CURRENCY}/ZAR RATE THIS MONTH`
- Replots sparkline from `state.sparklineDataAll[state.activeCurrency]`.
- Recalculates converter outputs if either input is non-empty.

### `setCurrency(currency)`
- Sets `state.activeCurrency = currency`.
- Updates toggle button active states (amber highlight on selected, dimmed outline on others).
- Calls `applyRate()`.

### `fetchSparklineData()`
- Calls `/api/fx/history?from=...&to=...`.
- Populates `state.sparklineDataAll.USD`, `.EUR`, `.GBP` from the response.

---

## HTML (`index.html`)

### Header pill
- Add `id="ratePillLabel"` to the `USD/ZAR` span so JS can update it.

### FX panel header
- Add a toggle group next to the refresh button:
  ```html
  <div class="fx-currency-toggle">
    <button class="fx-toggle-btn active" data-currency="USD">USD</button>
    <button class="fx-toggle-btn" data-currency="EUR">EUR</button>
    <button class="fx-toggle-btn" data-currency="GBP">GBP</button>
  </div>
  ```
- Panel title span: add `id="fxPanelTitle"`.
- `fxUnit` span: already exists, JS updates its text.
- Converter left tag: add `id="convCurrencyTag"`.
- Sparkline label: add `id="sparklineLabel"`.

---

## CSS (`style.css`)

### `.fx-currency-toggle`
- `display: flex; gap: 4px;` inline with the refresh button.

### `.fx-toggle-btn`
- Outlined pill: `border: 1px solid var(--amber); color: var(--amber); background: transparent;`
- Small, monospace, uppercase — matches existing panel button style.

### `.fx-toggle-btn.active`
- `background: var(--amber); color: var(--bg);` — amber fill, dark text.

---

## Income Entry (unchanged)
The Congo Rent income entry (`rent_usd`) remains hardcoded to USD. It is independent of the FX panel toggle.

---

## Out of Scope
- Saving per-currency rate history to the SQLite database (the `rates` table only stores USD/ZAR today).
- Historical sparkline for the fallback provider (open.er-api.com has no date-range endpoint).
