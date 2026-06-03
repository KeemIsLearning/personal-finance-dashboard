# Multi-Currency FX Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add USD / EUR / GBP toggle buttons to the FX panel so the user can switch between currencies; all three rates are fetched in one API call and switching is instant.

**Architecture:** The server fetches `from=ZAR&to=USD,EUR,GBP` from frankfurter.dev and inverts each rate to get ZAR-per-currency, returning a unified `{ date, rates: { USD, EUR, GBP } }` shape. The client stores all three rates and sparkline histories in state; `setCurrency()` switches the active currency and re-renders without a network call.

**Tech Stack:** Python/Flask (server.py), vanilla JS (app.js), HTML (index.html), CSS (style.css)

---

### Task 1: Update server FX routes to return all three currencies

**Files:**
- Modify: `server.py` (fx_latest and fx_history routes)

- [ ] **Step 1: Replace `fx_latest` route**

In `server.py`, replace the entire `fx_latest` function with:

```python
@app.route('/api/fx/latest')
def fx_latest():
    import json as _json
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
        return (_json.dumps(result), 200, {'Content-Type': 'application/json'})
    except Exception:
        pass

    # Fallback: open.er-api.com
    try:
        r = _requests.get('https://open.er-api.com/v6/latest/ZAR', timeout=5)
        d = r.json()
        rates_raw = d.get('rates', {})
        result = {
            'date': d.get('time_last_update_utc', '')[:10],
            'rates': {k: round(1 / rates_raw[k], 6) for k in ('USD', 'EUR', 'GBP') if rates_raw.get(k)}
        }
        return (_json.dumps(result), 200, {'Content-Type': 'application/json'})
    except Exception as exc:
        import json as _json
        return (_json.dumps({'error': str(exc)}), 503, {'Content-Type': 'application/json'})
```

- [ ] **Step 2: Replace `fx_history` route**

Replace the entire `fx_history` function with:

```python
@app.route('/api/fx/history')
def fx_history():
    import json as _json
    from_ = request.args.get('from')
    to = request.args.get('to')

    try:
        r = _requests.get(
            f'https://api.frankfurter.dev/v1/{from_}..{to}?from=ZAR&to=USD,EUR,GBP', timeout=5
        )
        if not r.ok:
            raise Exception(f'HTTP {r.status_code}')
        d = r.json()
        inverted = {
            date: {k: round(1 / v, 6) for k, v in day_rates.items()}
            for date, day_rates in d.get('rates', {}).items()
        }
        return (_json.dumps({'rates': inverted}), 200, {'Content-Type': 'application/json'})
    except Exception:
        pass

    # Fallback: return latest rates only (open.er-api.com has no date-range endpoint)
    try:
        r = _requests.get('https://open.er-api.com/v6/latest/ZAR', timeout=5)
        d = r.json()
        rates_raw = d.get('rates', {})
        today_str = d.get('time_last_update_utc', '')[:10]
        day = {k: round(1 / rates_raw[k], 6) for k in ('USD', 'EUR', 'GBP') if rates_raw.get(k)}
        return (_json.dumps({'rates': {today_str: day}}), 200, {'Content-Type': 'application/json'})
    except Exception as exc:
        return (_json.dumps({'error': str(exc)}), 503, {'Content-Type': 'application/json'})
```

- [ ] **Step 3: Remove the old `_frankfurter_to_standard` helper**

Delete these lines from `server.py` (they are no longer used):

```python
def _frankfurter_to_standard(data: dict) -> dict:
    """Normalise open.er-api.com response to match frankfurter shape."""
    return {
        'amount': 1,
        'base': data.get('base_code', 'USD'),
        'date': data.get('time_last_update_utc', '')[:10],
        'rates': {'ZAR': data.get('rates', {}).get('ZAR')},
    }
```

- [ ] **Step 4: Verify the endpoints manually**

Restart the Flask server:
```
python server.py
```

Then in another terminal:
```python
python -c "
import requests
r = requests.get('http://localhost:5000/api/fx/latest')
print('latest:', r.status_code, r.json())

import datetime
today = datetime.date.today().isoformat()
first = today[:8] + '01'
r2 = requests.get(f'http://localhost:5000/api/fx/history?from={first}&to={today}')
print('history status:', r2.status_code)
d = r2.json()
print('history keys:', list(d.get('rates', {}).keys())[:3])
first_day = list(d['rates'].values())[0]
print('first day rates:', first_day)
"
```

Expected output:
```
latest: 200 {'date': '2026-06-03', 'rates': {'USD': 16.27..., 'EUR': 17.8..., 'GBP': 21.0...}}
history status: 200
history keys: ['2026-06-01', '2026-06-02', '2026-06-03']
first day rates: {'USD': 16.2..., 'EUR': 17.8..., 'GBP': 21.0...}
```

- [ ] **Step 5: Commit**

```bash
git add server.py
git commit -m "feat(server): return USD/EUR/GBP rates from single ZAR-base FX call"
```

---

### Task 2: Add IDs and currency toggle buttons to HTML

**Files:**
- Modify: `index.html`

- [ ] **Step 1: Add `id="ratePillLabel"` to the header rate pill label**

Find (around line 23):
```html
<span class="rate-label">USD/ZAR</span>
```
Replace with:
```html
<span class="rate-label" id="ratePillLabel">USD/ZAR</span>
```

- [ ] **Step 2: Add `id="fxPanelTitle"` to the FX panel title**

Find (around line 156):
```html
<span class="panel-title">USD / ZAR EXCHANGE</span>
```
Replace with:
```html
<span class="panel-title" id="fxPanelTitle">USD / ZAR EXCHANGE</span>
```

- [ ] **Step 3: Add currency toggle buttons in the FX panel header**

Find (around line 157):
```html
<button class="panel-toggle" id="refreshRate">↻ REFRESH</button>
```
Replace with:
```html
<div class="fx-currency-toggle">
  <button class="fx-toggle-btn active" data-currency="USD">USD</button>
  <button class="fx-toggle-btn" data-currency="EUR">EUR</button>
  <button class="fx-toggle-btn" data-currency="GBP">GBP</button>
</div>
<button class="panel-toggle" id="refreshRate">↻ REFRESH</button>
```

- [ ] **Step 4: Add `id="fxUnit"` to the ZAR-per-currency span**

Find (around line 163):
```html
<span class="fx-unit">ZAR per USD</span>
```
Replace with:
```html
<span class="fx-unit" id="fxUnit">ZAR per USD</span>
```

- [ ] **Step 5: Add `id="convCurrencyTag"` to the converter left tag**

Find (around line 175):
```html
<span class="currency-tag">USD</span>
```
Replace with (only the first one — the left/foreign-currency tag, not the ZAR tag):
```html
<span class="currency-tag" id="convCurrencyTag">USD</span>
```

- [ ] **Step 6: Add `id="sparklineLabel"` to the sparkline label**

Find (around line 187):
```html
<span class="sparkline-label">RATE THIS MONTH (daily)</span>
```
Replace with:
```html
<span class="sparkline-label" id="sparklineLabel">USD/ZAR RATE THIS MONTH</span>
```

- [ ] **Step 7: Update the footer attribution text**

Find (around line 291):
```html
<a href="https://exchangerate-api.com" target="_blank" class="footer-attr">Exchange data: Frankfurter API</a>
```
Replace with:
```html
<a href="https://www.frankfurter.dev" target="_blank" class="footer-attr">Exchange data: Frankfurter</a>
```

- [ ] **Step 8: Commit**

```bash
git add index.html
git commit -m "feat(html): add currency toggle buttons and dynamic IDs to FX panel"
```

---

### Task 3: Add CSS for currency toggle buttons

**Files:**
- Modify: `style.css`

- [ ] **Step 1: Find the existing `.panel-header` styles to insert near**

Run:
```bash
grep -n "panel-header\|panel-toggle" style.css | head -20
```

Note the line numbers — insert the new styles immediately after the `.panel-toggle` block.

- [ ] **Step 2: Add toggle button styles**

Insert after the `.panel-toggle` CSS block:

```css
.fx-currency-toggle {
  display: flex;
  gap: 4px;
  align-items: center;
}

.fx-toggle-btn {
  font-family: 'Share Tech Mono', monospace;
  font-size: 0.7rem;
  padding: 2px 8px;
  background: transparent;
  border: 1px solid var(--amber);
  color: var(--amber);
  cursor: pointer;
  letter-spacing: 0.05em;
  opacity: 0.5;
  transition: opacity 0.15s, background 0.15s, color 0.15s;
}

.fx-toggle-btn.active {
  background: var(--amber);
  color: var(--bg);
  opacity: 1;
}

.fx-toggle-btn:hover:not(.active) {
  opacity: 0.8;
}
```

- [ ] **Step 3: Commit**

```bash
git add style.css
git commit -m "feat(css): add FX currency toggle button styles"
```

---

### Task 4: Update JS state and `fetchRate()`

**Files:**
- Modify: `app.js` (state object and fetchRate function)

- [ ] **Step 1: Update the state object**

Find (around line 14):
```js
    rate: null,
    rateUpdated: null,
```
Replace with:
```js
    rates: { USD: null, EUR: null, GBP: null },
    activeCurrency: 'USD',
    rateUpdated: null,
```

Find (around line 17):
```js
    sparklineData: [],
```
Replace with:
```js
    sparklineDataAll: { USD: [], EUR: [], GBP: [] },
```

- [ ] **Step 2: Rewrite `fetchRate()`**

Find and replace the entire `fetchRate` function (lines ~75–119):

```js
async function fetchRate(forceRefresh = false) {
    setRateStatus('FETCHING…');

    if (!forceRefresh) {
        const cached = localStorage.getItem(FX_CACHE_KEY);
        if (cached) {
            try {
                const { rates, updated, timestamp } = JSON.parse(cached);
                if (Date.now() - timestamp < FX_CACHE_TTL) {
                    state.rates = rates;
                    state.rateUpdated = updated;
                    applyRate();
                    return;
                }
            } catch { }
        }
    }

    try {
        const res = await fetch('/api/fx/latest');
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        const rates = data.rates;          // { USD: 16.27, EUR: 17.86, GBP: 21.04 }
        const updated = data.date || today();

        state.rates = rates;
        state.rateUpdated = updated;

        localStorage.setItem(FX_CACHE_KEY, JSON.stringify({
            rates, updated, timestamp: Date.now()
        }));

        await apiPost('/rate', { rate_date: updated, usd_to_zar: rates.USD });

        applyRate();
        await fetchSparklineData();
    } catch (err) {
        console.error('FX fetch error:', err);
        setRateStatus('OFFLINE');
        document.getElementById('fxLastUpdate').textContent = 'Could not fetch rate';
        const cached = localStorage.getItem(FX_CACHE_KEY);
        if (cached) {
            try {
                const { rates, updated } = JSON.parse(cached);
                state.rates = rates;
                state.rateUpdated = updated;
                applyRate();
                setRateStatus('CACHED');
            } catch { }
        }
    }
}
```

- [ ] **Step 3: Commit**

```bash
git add app.js
git commit -m "feat(js): update state and fetchRate for multi-currency rates object"
```

---

### Task 5: Rewrite `applyRate()` and add `setCurrency()`

**Files:**
- Modify: `app.js`

- [ ] **Step 1: Rewrite `applyRate()`**

Find and replace the entire `applyRate` function (currently starting around line 121):

```js
function applyRate() {
    const cur = state.activeCurrency;
    const rate = state.rates[cur];
    if (!rate) return;

    const formatted = rate.toFixed(4);

    // Header pill
    const pillLabel = document.getElementById('ratePillLabel');
    if (pillLabel) pillLabel.textContent = `${cur}/ZAR`;
    document.getElementById('headerRate').textContent = formatted;

    // Stat card
    document.getElementById('statRate').textContent = formatted;
    document.getElementById('rateSub').textContent = `1 ${cur} = ${rate.toFixed(2)} ZAR`;

    // FX panel
    const panelTitle = document.getElementById('fxPanelTitle');
    if (panelTitle) panelTitle.textContent = `${cur} / ZAR EXCHANGE`;
    document.getElementById('fxBigNumber').textContent = formatted;
    const fxUnit = document.getElementById('fxUnit');
    if (fxUnit) fxUnit.textContent = `ZAR per ${cur}`;
    document.getElementById('fxLastUpdate').textContent = `Last updated: ${state.rateUpdated}`;

    // Converter tag
    const convTag = document.getElementById('convCurrencyTag');
    if (convTag) convTag.textContent = cur;

    // Sparkline label
    const sparkLabel = document.getElementById('sparklineLabel');
    if (sparkLabel) sparkLabel.textContent = `${cur}/ZAR RATE THIS MONTH`;

    setRateStatus('LIVE');
    renderSparkline();
    renderConverter();
}
```

- [ ] **Step 2: Add `setCurrency()` after `applyRate()`**

Insert immediately after the closing `}` of `applyRate()`:

```js
function setCurrency(currency) {
    state.activeCurrency = currency;
    document.querySelectorAll('.fx-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.currency === currency);
    });
    applyRate();
}
```

- [ ] **Step 3: Wire up toggle button click handlers**

Find the existing refresh button listener (around line 593):
```js
document.getElementById('refreshRate').addEventListener('click', () => fetchRate(true));
```

Add immediately after it:
```js
document.querySelectorAll('.fx-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => setCurrency(btn.dataset.currency));
});
```

- [ ] **Step 4: Commit**

```bash
git add app.js
git commit -m "feat(js): rewrite applyRate for multi-currency, add setCurrency toggle"
```

---

### Task 6: Update `fetchSparklineData()` and `renderSparkline()`

**Files:**
- Modify: `app.js`

- [ ] **Step 1: Rewrite `fetchSparklineData()`**

Find and replace the entire `fetchSparklineData` function:

```js
async function fetchSparklineData() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const from = `${year}-${month}-01`;
    const to = today();
    try {
        const res = await fetch(`/api/fx/history?from=${from}&to=${to}`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.rates) {
            const entries = Object.entries(data.rates).sort(([a], [b]) => a.localeCompare(b));
            state.sparklineDataAll = {
                USD: entries.map(([date, r]) => ({ date, value: r.USD })),
                EUR: entries.map(([date, r]) => ({ date, value: r.EUR })),
                GBP: entries.map(([date, r]) => ({ date, value: r.GBP })),
            };
        }
        renderSparkline();
    } catch (err) {
        console.warn('Sparkline fetch failed:', err);
    }
}
```

- [ ] **Step 2: Rewrite `renderSparkline()`**

Find and replace the entire `renderSparkline` function:

```js
function renderSparkline() {
    const canvas = document.getElementById('sparklineChart');
    if (state.sparklineChart) { state.sparklineChart.destroy(); }
    const data = state.sparklineDataAll[state.activeCurrency] || [];
    if (!data.length) return;

    const labels = data.map(d => d.date.slice(5));
    const values = data.map(d => parseFloat(d.value.toFixed(4)));

    state.sparklineChart = new Chart(canvas, {
        type: 'line',
        data: {
            labels,
            datasets: [{
                data: values,
                borderColor: '#e8a020',
                borderWidth: 1.5,
                pointRadius: 0,
                pointHoverRadius: 3,
                fill: true,
                backgroundColor: 'rgba(232,160,32,0.06)',
                tension: 0.3
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#222220',
                    borderColor: 'rgba(232,160,32,0.3)',
                    borderWidth: 1,
                    titleColor: '#9a9488',
                    bodyColor: '#e8a020',
                    bodyFont: { family: 'Share Tech Mono', size: 12 },
                    callbacks: { label: ctx => `R ${ctx.raw.toFixed(4)}` }
                }
            },
            scales: {
                x: {
                    ticks: { color: '#5a564e', font: { family: 'Share Tech Mono', size: 10 },
                        maxTicksLimit: 6, autoSkip: true, maxRotation: 0 },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    border: { color: 'rgba(255,255,255,0.07)' }
                },
                y: {
                    ticks: { color: '#5a564e', font: { family: 'Share Tech Mono', size: 10 },
                        callback: v => v.toFixed(2) },
                    grid: { color: 'rgba(255,255,255,0.04)' },
                    border: { color: 'rgba(255,255,255,0.07)' }
                }
            }
        }
    });
}
```

- [ ] **Step 3: Commit**

```bash
git add app.js
git commit -m "feat(js): update sparkline to store and render per-currency history"
```

---

### Task 7: Update converter and income entry to use new state shape

**Files:**
- Modify: `app.js`

- [ ] **Step 1: Rewrite `initConverter()`**

Find and replace the entire `initConverter` function:

```js
function initConverter() {
    const fxInput = document.getElementById('convUSD');
    const zarInput = document.getElementById('convZAR');
    fxInput.addEventListener('input', () => {
        const rate = state.rates[state.activeCurrency];
        if (!rate) return;
        const val = parseFloat(fxInput.value);
        zarInput.value = isNaN(val) ? '' : (val * rate).toFixed(2);
    });
    zarInput.addEventListener('input', () => {
        const rate = state.rates[state.activeCurrency];
        if (!rate) return;
        const val = parseFloat(zarInput.value);
        fxInput.value = isNaN(val) ? '' : (val / rate).toFixed(2);
    });
}
```

- [ ] **Step 2: Rewrite `renderConverter()`**

Find and replace the entire `renderConverter` function:

```js
function renderConverter() {
    const fxInput = document.getElementById('convUSD');
    const zarInput = document.getElementById('convZAR');
    const rate = state.rates[state.activeCurrency];
    if (!rate || !fxInput.value) return;
    const val = parseFloat(fxInput.value);
    if (!isNaN(val)) zarInput.value = (val * rate).toFixed(2);
}
```

- [ ] **Step 3: Update income entry `updateConversionPreview()` to use `state.rates.USD`**

Find (around line 319):
```js
  if (source === 'rent_usd' && !isNaN(amount) && state.rate) {
      el.textContent = `R ${(amount * state.rate).toFixed(2)}`;
```
Replace with:
```js
  if (source === 'rent_usd' && !isNaN(amount) && state.rates.USD) {
      el.textContent = `R ${(amount * state.rates.USD).toFixed(2)}`;
```

- [ ] **Step 4: Update income submit handler to use `state.rates.USD`**

Find (around line 337):
```js
  if (source === 'rent_usd') {
      if (!state.rate) { alert('Exchange rate not loaded yet. Please wait or refresh.'); return; }
      amount_zar = rawAmount * state.rate;
      currency = 'USD';
      rate_used = state.rate;
  }
```
Replace with:
```js
  if (source === 'rent_usd') {
      if (!state.rates.USD) { alert('Exchange rate not loaded yet. Please wait or refresh.'); return; }
      amount_zar = rawAmount * state.rates.USD;
      currency = 'USD';
      rate_used = state.rates.USD;
  }
```

- [ ] **Step 5: Update income edit handler to use `state.rates.USD`**

Find (around line 737):
```js
        if (source === 'rent_usd') {
            if (!state.rate) { alert('Exchange rate not loaded yet.'); return; }
            currency = 'USD';
            amount_zar = parseFloat((amount_original * state.rate).toFixed(2));
            rate_used = state.rate;
        }
```
Replace with:
```js
        if (source === 'rent_usd') {
            if (!state.rates.USD) { alert('Exchange rate not loaded yet.'); return; }
            currency = 'USD';
            amount_zar = parseFloat((amount_original * state.rates.USD).toFixed(2));
            rate_used = state.rates.USD;
        }
```

- [ ] **Step 6: Commit**

```bash
git add app.js
git commit -m "feat(js): update converter and income entry to use new rates state shape"
```

---

### Task 8: Smoke test the full feature

- [ ] **Step 1: Clear localStorage and restart**

Restart the Flask server:
```
python server.py
```

Open `http://localhost:5000` in the browser. Open DevTools (F12).

In the Console tab run:
```js
localStorage.removeItem('pf_fx_cache');
fetchRate(true);
```

- [ ] **Step 2: Verify initial state (USD active)**

- Header pill shows `USD/ZAR` with a numeric rate (e.g. `16.2703`)
- FX panel title reads `USD / ZAR EXCHANGE`
- Big number matches the header pill
- Unit reads `ZAR per USD`
- Converter left tag reads `USD`
- Sparkline label reads `USD/ZAR RATE THIS MONTH`
- USD toggle button is amber-filled; EUR and GBP are outlined

- [ ] **Step 3: Switch to EUR**

Click the `EUR` toggle button.

- Header pill updates to `EUR/ZAR` with a higher rate (EUR > USD vs ZAR)
- Panel title: `EUR / ZAR EXCHANGE`
- Unit: `ZAR per EUR`
- Converter tag: `EUR`
- Sparkline replots with EUR history
- EUR button amber-filled; USD and GBP outlined

- [ ] **Step 4: Switch to GBP**

Click the `GBP` toggle button. Same checks — GBP rate should be the highest of the three.

- [ ] **Step 5: Check converter arithmetic**

With GBP active, enter `100` in the left (GBP) input. The ZAR value should be approximately `100 × GBP_rate`. Clear it and enter a ZAR amount — confirm the GBP field updates correctly.

- [ ] **Step 6: Check Congo Rent income entry is unaffected**

Open the income entry form, select **Congo Rent (USD)**. Enter `1000`. The conversion preview should show `R [1000 × USD_rate]` — it must use the USD rate regardless of which toggle is active.

- [ ] **Step 7: Check the Network tab**

Confirm only **one** `/api/fx/latest` request was made (not three). Switching currencies produces zero new network requests.

- [ ] **Step 8: Verify no console errors**

Console tab should be free of red errors. Warnings about sparkline data being empty for the first day of the month are acceptable.
