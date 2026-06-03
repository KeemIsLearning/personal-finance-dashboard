/* ============================================
   P4THF1ND3R FINANCE — app.js
   Local-first finance dashboard
   FX: Frankfurter API (no key required)
   Storage: localStorage
   ============================================ */

'use strict';

const API = 'http://127.0.0.1:5000/api';

const state = {
    currentYear: new Date().getFullYear(),
    currentMonth: new Date().getMonth(),
    rates: { USD: null, EUR: null, GBP: null },
    activeCurrency: 'USD',
    rateUpdated: null,
    sparklineDataAll: { USD: [], EUR: [], GBP: [] },
    historyChart: null,
    sparklineChart: null,
    budget: null
};

const MONTHS = [
    'January','February','March','April','May','June',
    'July','August','September','October','November','December'
];

function monthLabel(year, month) {
    return `${MONTHS[month]} ${year}`;
}

function today() {
    return new Date().toISOString().slice(0, 10);
}

//API helper functions
async function apiFetch(path) {
  const res = await fetch(`${API}${path}`);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPost(path, body) {
  const res = await fetch(`${API}${path}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(`${API}${path}`, { method: 'DELETE' });
  if (!res.ok) throw new Error(`DELETE ${path} failed: ${res.status}`);
  return res.json();
}

async function apiPut(path, body) {
  const res = await fetch(`${API}${path}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
  });
  if (!res.ok) throw new Error(`PUT ${path} failed: ${res.status}`);
  return res.json();
}

let _editTarget = null;

//Exchange rate
const FX_CACHE_KEY = 'pf_fx_cache';
const FX_CACHE_TTL = 60 * 60 * 1000;

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

function setCurrency(currency) {
    state.activeCurrency = currency;
    document.querySelectorAll('.fx-toggle-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.currency === currency);
    });
    applyRate();
}

function setRateStatus(status) {
    const el = document.getElementById('rateStatus');
    el.textContent = status;
    el.style.color = status === 'LIVE' ? '#6ab04a'
        : status === 'CACHED' ? '#e8a020'
        : '#9a9488';
}

async function fetchSparklineData() {
    const now = new Date();
    const year = now.getFullYear();
    const month = String(now.getMonth() + 1).padStart(2, '0');
    const from = `${year}-${month}-01`;
    const to = today();
    try {
        const res = await fetch(
            `/api/fx/history?from=${from}&to=${to}`
        );
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        if (data.rates) {
            state.sparklineData = Object.entries(data.rates)
                .map(([date, rates]) => ({ date, value: rates.ZAR }))
                .sort((a, b) => a.date.localeCompare(b.date));
        }
        renderSparkline();
    } catch (err) {
        console.warn('Sparkline fetch failed:', err);
    }
}

//Render functions
async function renderAll() {
  document.getElementById('currentMonthLabel').textContent =
      monthLabel(state.currentYear, state.currentMonth);
  updateFooterDate();

  try {
      const [income, fixed, variable] = await Promise.all([
          apiFetch(`/income/${state.currentYear}/${state.currentMonth + 1}`),
          apiFetch(`/fixed/${state.currentYear}/${state.currentMonth + 1}`),
          apiFetch(`/variable/${state.currentYear}/${state.currentMonth + 1}`)
      ]);

      renderIncomeList(income);
      renderExpenseList(fixed, variable);
      renderSummary(income, fixed, variable);
      renderHistoryChart();
  } catch (err) {
      console.error('renderAll failed:', err);
  }
}

function renderSummary(income, fixed, variable) {
  const totalIncome = income.reduce((sum, e) => sum + e.amount_zar, 0);
  const totalExpenses = [
      ...fixed.map(e => e.amount_zar),
      ...variable.map(e => e.amount_zar)
  ].reduce((sum, v) => sum + v, 0);
  const net = totalIncome - totalExpenses;

  document.getElementById('totalIncome').textContent = `R ${totalIncome.toFixed(2)}`;
  document.getElementById('totalExpenses').textContent = `R ${totalExpenses.toFixed(2)}`;
  document.getElementById('netBalance').textContent = `R ${net.toFixed(2)}`;
  document.getElementById('expenseSub').textContent =
      `${fixed.length + variable.length} entries`;

  const sources = income.map(e => e.source);
  const hasSalary = sources.includes('salary');
  const hasRent = sources.includes('rent_usd');
  let incomeSub = '';
  if (hasSalary && hasRent) incomeSub = 'salary + congo rent';
  else if (hasSalary) incomeSub = 'salary';
  else if (hasRent) incomeSub = 'congo rent';
  else incomeSub = `${income.length} entries`;
  document.getElementById('incomeSub').textContent = incomeSub;

  const balanceCard = document.getElementById('balanceCard');
  balanceCard.classList.remove('positive', 'negative');
  if (net > 0) balanceCard.classList.add('positive');
  else if (net < 0) balanceCard.classList.add('negative');
}

function renderIncomeList(income) {
  const list = document.getElementById('incomeList');
  list.innerHTML = '';
  if (!income.length) {
      list.innerHTML = '<li class="empty-state">No income logged for this month.</li>';
      return;
  }
  income.forEach(entry => {
      const li = document.createElement('li');
      li.className = 'entry-item';
      let noteStr = entry.notes || sourceName(entry.source);
      if (entry.currency === 'USD' && entry.rate_used) {
          noteStr += ` ($ ${entry.amount_original.toFixed(2)} @ ${entry.rate_used.toFixed(4)})`;
      }
      li.innerHTML = `
          <div class="entry-left">
              <span class="entry-cat-badge cat-${entry.source}">${sourceName(entry.source)}</span>
              <span class="entry-desc">${escHtml(noteStr)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
              <span class="entry-amount income">R ${entry.amount_zar.toFixed(2)}</span>
              <span class="entry-desc" style="font-size:0.7rem;opacity:0.5">
                  ${entry.date_received}
              </span>
              <button class="entry-edit">&#9998;</button>
              <button class="entry-delete" data-id="${entry.id}" data-type="income">✕</button>
          </div>
      `;
      list.appendChild(li);
      li.querySelector('.entry-edit').addEventListener('click', () => openEditModal('income', entry));
  });
  list.querySelectorAll('.entry-delete').forEach(btn => {
      btn.addEventListener('click', () => deleteEntry('income', btn.dataset.id));
  });
}

function renderExpenseList(fixed, variable) {
  const list = document.getElementById('expenseList');
  list.innerHTML = '';
  const all = [
      ...fixed.map(e => ({ ...e, _type: 'fixed' })),
      ...variable.map(e => ({ ...e, _type: 'variable', date_received: e.date_logged }))
  ].sort((a, b) => {
      const da = a.date_logged || a.date_received || '';
      const db = b.date_logged || b.date_received || '';
      return db.localeCompare(da);
  });

  if (!all.length) {
      list.innerHTML = '<li class="empty-state">No expenses logged for this month.</li>';
      return;
  }
  all.forEach(entry => {
      const li = document.createElement('li');
      li.className = 'entry-item';
      const cat = entry.category;
      const desc = entry.description || categoryLabel(cat);
      const dateStr = entry.date_logged || '';
      li.innerHTML = `
          <div class="entry-left">
              <span class="entry-cat-badge cat-${cat}">${categoryLabel(cat)}</span>
              <span class="entry-desc">${escHtml(desc)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:6px;">
              <span class="entry-amount expense">R ${entry.amount_zar.toFixed(2)}</span>
              <span class="entry-desc" style="font-size:0.7rem;opacity:0.5">${dateStr}</span>
              <button class="entry-edit">&#9998;</button>
              <button class="entry-delete" data-id="${entry.id}"
                  data-type="${entry._type}">✕</button>
          </div>
      `;
      list.appendChild(li);
      li.querySelector('.entry-edit').addEventListener('click', () => openEditModal(entry._type, entry));
  });
  list.querySelectorAll('.entry-delete').forEach(btn => {
      btn.addEventListener('click', () => deleteEntry(btn.dataset.type, btn.dataset.id));
  });
}

async function deleteEntry(type, id) {
  try {
      await apiDelete(`/${type}/${id}`);
      renderAll();
  } catch (err) {
      console.error('Delete failed:', err);
  }
}

//Form submission
document.getElementById('incomeSource').addEventListener('change', function () {
  const isUSD = this.value === 'rent_usd';
  document.getElementById('conversionPreview').style.display = isUSD ? 'grid' : 'none';
  updateConversionPreview();
});

document.getElementById('incomeAmount').addEventListener('input', updateConversionPreview);

function updateConversionPreview() {
  const source = document.getElementById('incomeSource').value;
  const amount = parseFloat(document.getElementById('incomeAmount').value);
  const el = document.getElementById('conversionValue');
  if (source === 'rent_usd' && !isNaN(amount) && state.rate) {
      el.textContent = `R ${(amount * state.rate).toFixed(2)}`;
  } else {
      el.textContent = 'calculating…';
  }
}

document.getElementById('submitIncome').addEventListener('click', async () => {
  const source = document.getElementById('incomeSource').value;
  const rawAmount = parseFloat(document.getElementById('incomeAmount').value);
  const note = document.getElementById('incomeNote').value.trim();

  if (isNaN(rawAmount) || rawAmount <= 0) { alert('Please enter a valid amount.'); return; }

  let amount_zar = rawAmount;
  let currency = 'ZAR';
  let rate_used = null;

  if (source === 'rent_usd') {
      if (!state.rate) { alert('Exchange rate not loaded yet. Please wait or refresh.'); return; }
      amount_zar = rawAmount * state.rate;
      currency = 'USD';
      rate_used = state.rate;
  }

  try {
      await apiPost('/income', {
          source,
          amount_original: rawAmount,
          currency,
          amount_zar: parseFloat(amount_zar.toFixed(2)),
          rate_used,
          date_received: today(),
          notes: note
      });

      document.getElementById('incomeAmount').value = '';
      document.getElementById('incomeNote').value = '';
      document.getElementById('conversionPreview').style.display = 'none';
      toggleForm('incomeForm');
      renderAll();
  } catch (err) {
      console.error('Add income failed:', err);
      alert('Could not save. Is the server running?');
  }
});

document.getElementById('submitExpense').addEventListener('click', async () => {
  const activeTab = document.querySelector('.expense-tab.active')?.dataset.tab || 'variable';
  const category = document.getElementById('expenseCategory').value;
  const amount = parseFloat(document.getElementById('expenseAmount').value);
  const desc = document.getElementById('expenseDesc').value.trim();

  if (isNaN(amount) || amount <= 0) { alert('Please enter a valid amount.'); return; }

  const endpoint = activeTab === 'fixed' ? '/fixed' : '/variable';
  const body = {
      category,
      amount_zar: parseFloat(amount.toFixed(2)),
      description: desc,
      date_logged: today()
  };

  if (activeTab === 'fixed') {
      body.person = document.getElementById('expensePerson')?.value || 'Kai';
      body.is_recurring = document.getElementById('expenseRecurring')?.checked ? 1 : 0;
  }

  try {
      await apiPost(endpoint, body);
      document.getElementById('expenseAmount').value = '';
      document.getElementById('expenseDesc').value = '';
      toggleForm('expenseForm');
      renderAll();
  } catch (err) {
      console.error('Add expense failed:', err);
      alert('Could not save. Is the server running?');
  }
});

//Charts,navigation,helpers and init
function renderSparkline() {
  const canvas = document.getElementById('sparklineChart');
  if (state.sparklineChart) { state.sparklineChart.destroy(); }
  if (!state.sparklineData.length) return;

  const labels = state.sparklineData.map(d => d.date.slice(5));
  const values = state.sparklineData.map(d => parseFloat(d.value.toFixed(4)));

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

async function renderHistoryChart() {
  const canvas = document.getElementById('historyChart');
  if (state.historyChart) { state.historyChart.destroy(); }

  try {
      const history = await apiFetch('/history');
      const noMsg = document.getElementById('noHistoryMsg');

      if (!history.length) {
          noMsg.style.display = 'block';
          canvas.style.display = 'none';
          return;
      }

      noMsg.style.display = 'none';
      canvas.style.display = 'block';

      const labels = history.map(h => {
          const [y, m] = h.month.split('-');
          return MONTHS[parseInt(m) - 1].slice(0, 3) + ' ' + y.slice(2);
      });

      state.historyChart = new Chart(canvas, {
          type: 'bar',
          data: {
              labels,
              datasets: [
                  {
                      label: 'Income',
                      data: history.map(h => h.income),
                      backgroundColor: 'rgba(106,176,74,0.45)',
                      borderColor: '#6ab04a',
                      borderWidth: 1,
                      borderRadius: 2
                  },
                  {
                      label: 'Expenses',
                      data: history.map(h => h.expenses),
                      backgroundColor: 'rgba(212,80,80,0.35)',
                      borderColor: '#d45050',
                      borderWidth: 1,
                      borderRadius: 2
                  },
                  {
                      label: 'Balance',
                      data: history.map(h => h.balance),
                      type: 'line',
                      borderColor: '#e8a020',
                      borderWidth: 2,
                      pointRadius: 3,
                      pointBackgroundColor: '#e8a020',
                      fill: false,
                      tension: 0.3,
                      yAxisID: 'y'
                  }
              ]
          },
          options: {
              responsive: true,
              maintainAspectRatio: false,
              interaction: { mode: 'index', intersect: false },
              plugins: {
                  legend: { display: false },
                  tooltip: {
                      backgroundColor: '#222220',
                      borderColor: 'rgba(232,160,32,0.3)',
                      borderWidth: 1,
                      titleColor: '#9a9488',
                      bodyColor: '#e8e4d8',
                      bodyFont: { family: 'Share Tech Mono', size: 12 },
                      callbacks: { label: ctx => ` ${ctx.dataset.label}: R ${ctx.raw.toFixed(2)}` }
                  }
              },
              scales: {
                  x: {
                      ticks: { color: '#5a564e', font: { family: 'Share Tech Mono', size: 10 },
                          autoSkip: false, maxRotation: 0 },
                      grid: { color: 'rgba(255,255,255,0.04)' },
                      border: { color: 'rgba(255,255,255,0.07)' }
                  },
                  y: {
                      ticks: { color: '#5a564e', font: { family: 'Share Tech Mono', size: 10 },
                          callback: v => 'R ' + (v >= 1000 ? (v/1000).toFixed(1)+'k' : v.toFixed(0)) },
                      grid: { color: 'rgba(255,255,255,0.04)' },
                      border: { color: 'rgba(255,255,255,0.07)' }
                  }
              }
          }
      });
  } catch (err) {
      console.warn('History chart failed:', err);
  }
}

function initConverter() {
    const usdInput = document.getElementById('convUSD');
    const zarInput = document.getElementById('convZAR');
    usdInput.addEventListener('input', () => {
        if (!state.rate) return;
        const usd = parseFloat(usdInput.value);
        zarInput.value = isNaN(usd) ? '' : (usd * state.rate).toFixed(2);
    });
    zarInput.addEventListener('input', () => {
        if (!state.rate) return;
        const zar = parseFloat(zarInput.value);
        usdInput.value = isNaN(zar) ? '' : (zar / state.rate).toFixed(2);
    });
}

function renderConverter() {
    const usdInput = document.getElementById('convUSD');
    const zarInput = document.getElementById('convZAR');
    if (!state.rate || !usdInput.value) return;
    const usd = parseFloat(usdInput.value);
    if (!isNaN(usd)) zarInput.value = (usd * state.rate).toFixed(2);
}

document.getElementById('prevMonth').addEventListener('click', () => {
  state.currentMonth--;
  if (state.currentMonth < 0) { state.currentMonth = 11; state.currentYear--; }
  renderAll();
});

document.getElementById('nextMonth').addEventListener('click', () => {
  state.currentMonth++;
  if (state.currentMonth > 11) { state.currentMonth = 0; state.currentYear++; }
  renderAll();
});

document.querySelectorAll('.panel-toggle[data-target]').forEach(btn => {
  btn.addEventListener('click', () => toggleForm(btn.dataset.target));
});

document.querySelectorAll('.btn-cancel').forEach(btn => {
  btn.addEventListener('click', () => toggleForm(btn.dataset.target));
});

document.getElementById('refreshRate').addEventListener('click', () => fetchRate(true));
document.querySelectorAll('.fx-toggle-btn').forEach(btn => {
    btn.addEventListener('click', () => setCurrency(btn.dataset.currency));
});

function toggleForm(id) {
  document.getElementById(id).classList.toggle('hidden');
}

function sourceName(src) {
  const map = { salary: 'Salary', rent_usd: 'Congo Rent', other: 'Other' };
  return map[src] || src;
}

function categoryLabel(cat) {
  const map = {
      school: 'School Fees', fuel: 'Fuel', subscriptions: 'Subscriptions',
      food: 'Food & Groceries', car: 'Car', clothing: 'Clothing',
      utilities: 'Utilities', other: 'Other'
  };
  return map[cat] || cat;
}

function escHtml(str) {
  return String(str)
      .replace(/&/g,'&amp;').replace(/</g,'&lt;')
      .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function updateFooterDate() {
  document.getElementById('footerDate').textContent =
      new Date().toLocaleDateString('en-ZA', {
          weekday: 'short', year: 'numeric', month: 'short', day: 'numeric'
      });
}

// ---- EDIT MODAL ----

function categoryOptions(selected) {
    const opts = [
        ['school','School Fees'],['fuel','Fuel'],['subscriptions','Subscriptions'],
        ['food','Food & Groceries'],['car','Car / Transport'],['clothing','Clothing'],
        ['utilities','Utilities'],['other','Other']
    ];
    return opts.map(([v, l]) =>
        `<option value="${v}"${v === selected ? ' selected' : ''}>${l}</option>`
    ).join('');
}

function buildEditForm(type, entry) {
    if (type === 'income') {
        return `
          <div class="form-row">
            <label>Source</label>
            <select id="editSource">
              <option value="salary"${entry.source==='salary'?' selected':''}>Salary (ZAR)</option>
              <option value="rent_usd"${entry.source==='rent_usd'?' selected':''}>Congo Rent (USD)</option>
              <option value="other"${entry.source==='other'?' selected':''}>Other (ZAR)</option>
            </select>
          </div>
          <div class="form-row">
            <label>Amount</label>
            <input type="number" id="editAmount" value="${entry.amount_original}" min="0" step="0.01" />
          </div>
          <div class="form-row">
            <label>Date</label>
            <input type="date" id="editDate" value="${entry.date_received}" />
          </div>
          <div class="form-row">
            <label>Notes</label>
            <input type="text" id="editNotes" value="${escHtml(entry.notes || '')}" />
          </div>`;
    }
    if (type === 'fixed') {
        return `
          <div class="form-row">
            <label>Category</label>
            <select id="editCategory">${categoryOptions(entry.category)}</select>
          </div>
          <div class="form-row">
            <label>Person</label>
            <input type="text" id="editPerson" value="${escHtml(entry.person || 'Kai')}" />
          </div>
          <div class="form-row">
            <label>Amount (ZAR)</label>
            <input type="number" id="editAmount" value="${entry.amount_zar}" min="0" step="0.01" />
          </div>
          <div class="form-row">
            <label>Description</label>
            <input type="text" id="editDesc" value="${escHtml(entry.description || '')}" />
          </div>
          <div class="form-row">
            <label>Recurring</label>
            <input type="checkbox" id="editRecurring"${entry.is_recurring ? ' checked' : ''} />
          </div>
          <div class="form-row">
            <label>Due Day</label>
            <input type="number" id="editDueDay" value="${entry.due_day || ''}" min="1" max="31" />
          </div>
          <div class="form-row">
            <label>Date</label>
            <input type="date" id="editDate" value="${entry.date_logged}" />
          </div>`;
    }
    return `
      <div class="form-row">
        <label>Category</label>
        <select id="editCategory">${categoryOptions(entry.category)}</select>
      </div>
      <div class="form-row">
        <label>Amount (ZAR)</label>
        <input type="number" id="editAmount" value="${entry.amount_zar}" min="0" step="0.01" />
      </div>
      <div class="form-row">
        <label>Description</label>
        <input type="text" id="editDesc" value="${escHtml(entry.description || '')}" />
      </div>
      <div class="form-row">
        <label>Date</label>
        <input type="date" id="editDate" value="${entry.date_logged}" />
      </div>`;
}

function openEditModal(type, entry) {
    _editTarget = { type, id: entry.id };
    const titles = { income: 'EDIT INCOME', fixed: 'EDIT FIXED EXPENSE', variable: 'EDIT VARIABLE EXPENSE' };
    document.getElementById('editModalTitle').textContent = titles[type];
    document.getElementById('editModalBody').innerHTML = buildEditForm(type, entry);
    document.getElementById('editModal').classList.remove('hidden');
}

function closeEditModal() {
    document.getElementById('editModal').classList.add('hidden');
    _editTarget = null;
}

async function saveEdit() {
    const { type, id } = _editTarget;
    let body;

    if (type === 'income') {
        const source = document.getElementById('editSource').value;
        const amount_original = parseFloat(document.getElementById('editAmount').value);
        const date_received = document.getElementById('editDate').value;
        const notes = document.getElementById('editNotes').value.trim();
        if (isNaN(amount_original) || amount_original <= 0) { alert('Enter a valid amount.'); return; }
        let currency = 'ZAR', amount_zar = amount_original, rate_used = null;
        if (source === 'rent_usd') {
            if (!state.rate) { alert('Exchange rate not loaded yet.'); return; }
            currency = 'USD';
            amount_zar = parseFloat((amount_original * state.rate).toFixed(2));
            rate_used = state.rate;
        }
        body = { source, amount_original, currency, amount_zar, rate_used, date_received, notes };
    } else if (type === 'fixed') {
        const category = document.getElementById('editCategory').value;
        const person = document.getElementById('editPerson').value.trim() || 'Kai';
        const amount_zar = parseFloat(document.getElementById('editAmount').value);
        const description = document.getElementById('editDesc').value.trim();
        const is_recurring = document.getElementById('editRecurring').checked ? 1 : 0;
        const due_day = parseInt(document.getElementById('editDueDay').value) || null;
        const date_logged = document.getElementById('editDate').value;
        if (isNaN(amount_zar) || amount_zar <= 0) { alert('Enter a valid amount.'); return; }
        body = { category, person, amount_zar, description, is_recurring, due_day, date_logged };
    } else {
        const category = document.getElementById('editCategory').value;
        const amount_zar = parseFloat(document.getElementById('editAmount').value);
        const description = document.getElementById('editDesc').value.trim();
        const date_logged = document.getElementById('editDate').value;
        if (isNaN(amount_zar) || amount_zar <= 0) { alert('Enter a valid amount.'); return; }
        body = { category, amount_zar, description, date_logged };
    }

    try {
        await apiPut(`/${type}/${id}`, body);
        closeEditModal();
        renderAll();
    } catch (err) {
        console.error('Edit failed:', err);
        alert('Could not save changes. Is the server running?');
    }
}

// =============================================
// BUDGET PLANNER
// =============================================

async function loadBudget() {
    try {
        state.budget = await apiFetch('/budget');
        renderBudget();
    } catch (err) {
        console.error('Budget load failed:', err);
    }
}

async function saveBudget() {
    try {
        await apiPut('/budget', state.budget);
    } catch (err) {
        console.error('Budget save failed:', err);
    }
}

function budgetBaselineTotal() {
    return (state.budget?.baseline || []).reduce((s, i) => s + i.amount, 0);
}

function renderBudget() {
    const b = state.budget;
    if (!b) return;

    const baselineTotal = budgetBaselineTotal();
    const remaining = b.income - baselineTotal;

    // Stats
    document.getElementById('budgetIncome').textContent     = `R ${b.income.toLocaleString()}`;
    document.getElementById('budgetBaselineOut').textContent = `R ${baselineTotal.toLocaleString()}`;
    document.getElementById('budgetRemaining').textContent   = `R ${remaining.toLocaleString()}`;
    document.getElementById('budgetBarMax').textContent      = `R ${b.income.toLocaleString()}`;

    // Baseline list
    const bl = document.getElementById('budgetBaselineList');
    bl.innerHTML = b.baseline.map(item => `
        <li class="budget-item" data-bid="${item.id}">
          <div class="budget-item-left">
            <span class="budget-item-name">${escHtml(item.name)}</span>
            ${item.note ? `<span class="budget-item-note">(${escHtml(item.note)})</span>` : ''}
          </div>
          <div class="budget-item-right">
            <span class="budget-item-amount">R ${item.amount.toLocaleString()}</span>
            <button class="budget-item-edit" data-bid="${item.id}" title="Edit">&#9998;</button>
            <button class="budget-item-delete" data-bid="${item.id}" title="Delete">&#x2715;</button>
          </div>
        </li>`).join('') + `
        <li class="budget-item total-row">
          <span class="budget-item-name">TOTAL BASELINE</span>
          <span class="budget-item-amount">R ${baselineTotal.toLocaleString()}</span>
        </li>`;

    bl.querySelectorAll('.budget-item-edit').forEach(btn =>
        btn.addEventListener('click', e => { e.stopPropagation(); openBudgetItemEdit('baseline', parseInt(btn.dataset.bid)); }));
    bl.querySelectorAll('.budget-item-delete').forEach(btn =>
        btn.addEventListener('click', e => { e.stopPropagation(); deleteBudgetItem('baseline', parseInt(btn.dataset.bid)); }));

    // Optional list
    const ol = document.getElementById('budgetOptionalList');
    ol.innerHTML = b.optional.map(item => {
        const isSelected = b.selectedOptional === item.id;
        const costText = item.min === 0 ? 'R 0'
            : item.min === item.max ? `\u2248 R ${item.min.toLocaleString()}`
            : `\u2248 R ${item.min.toLocaleString()}\u2013${item.max.toLocaleString()}`;
        const midCost = item.min === item.max ? item.min : Math.round((item.min + item.max) / 2);
        const left = remaining - midCost;
        const leftText = item.min === 0
            ? `R ${remaining.toLocaleString()} stacked`
            : `\u2248 R ${left.toLocaleString()} left`;
        return `
        <li class="budget-optional-card${isSelected ? ' selected' : ''}" data-oid="${item.id}">
          <div class="opt-card-left">
            <span class="opt-select-dot${isSelected ? ' active' : ''}"></span>
            <span class="opt-card-name">${escHtml(item.name)}</span>
            <span class="opt-tag opt-tag-${escHtml(item.tagColor)}">${escHtml(item.tag)}</span>
          </div>
          <div style="display:flex;align-items:center;gap:0.5rem">
            <div class="opt-card-right">
              <span class="opt-cost">${costText}</span>
              <span class="opt-left${left < 0 && item.min > 0 ? ' negative' : ''}">${leftText}</span>
            </div>
            <div class="opt-card-actions">
              <button class="budget-item-edit" data-oid="${item.id}" title="Edit">&#9998;</button>
              <button class="budget-item-delete" data-oid="${item.id}" title="Delete">&#x2715;</button>
            </div>
          </div>
        </li>`;
    }).join('');

    ol.querySelectorAll('.budget-optional-card').forEach(card =>
        card.addEventListener('click', () => selectOptional(parseInt(card.dataset.oid))));
    ol.querySelectorAll('.budget-item-edit').forEach(btn =>
        btn.addEventListener('click', e => { e.stopPropagation(); openBudgetItemEdit('optional', parseInt(btn.dataset.oid)); }));
    ol.querySelectorAll('.budget-item-delete').forEach(btn =>
        btn.addEventListener('click', e => { e.stopPropagation(); deleteBudgetItem('optional', parseInt(btn.dataset.oid)); }));

    renderBudgetTotals();
    renderBudgetRules();
}

function renderBudgetTotals() {
    const b = state.budget;
    if (!b) return;
    const baselineTotal = budgetBaselineTotal();
    const selected = b.optional.find(o => o.id === b.selectedOptional) || null;
    const midCost = selected
        ? (selected.min === selected.max ? selected.min : Math.round((selected.min + selected.max) / 2))
        : 0;
    const costDisplay = selected
        ? (selected.min === selected.max
            ? (selected.min === 0 ? 'R 0' : `\u2248 R ${selected.min.toLocaleString()}`)
            : `\u2248 R ${selected.min.toLocaleString()}\u2013${selected.max.toLocaleString()}`)
        : null;
    const totalCost  = baselineTotal + midCost;
    const bufferLeft = b.income - totalCost;
    const pct        = Math.min(100, Math.round((totalCost / b.income) * 100)) || 0;

    document.getElementById('budgetTotals').innerHTML = `
        <div class="budget-total-row">
          <span>BASELINE</span>
          <span class="mono">R ${baselineTotal.toLocaleString()}</span>
        </div>
        ${selected ? `
        <div class="budget-total-row">
          <span>+ ${escHtml(selected.name.toUpperCase())}</span>
          <span class="mono">${costDisplay}</span>
        </div>` : ''}
        <div class="budget-total-row grand-total">
          <span>TOTAL</span>
          <span class="mono">${selected ? '\u2248 ' : ''}R ${totalCost.toLocaleString()}</span>
        </div>
        <div class="budget-total-row buffer-row${bufferLeft < 0 ? ' negative' : ''}">
          <span>BUFFER LEFT</span>
          <span class="mono">${selected ? '\u2248 ' : ''}R ${bufferLeft.toLocaleString()}</span>
        </div>`;

    const fill = document.getElementById('budgetBarFill');
    fill.style.width = `${pct}%`;
    fill.className = 'budget-bar-fill' + (pct >= 90 ? ' danger' : pct >= 75 ? ' warning' : '');
    document.getElementById('budgetBarPct').textContent = `${pct}%`;
}

function renderBudgetRules() {
    const rules = state.budget?.rules || [];
    document.getElementById('budgetRules').innerHTML = rules.map((r, i) => `
        <li class="rule-item">
          <span class="rule-num">[${String(i + 1).padStart(2, '0')}]</span>
          <span class="rule-text">${escHtml(r)}</span>
        </li>`).join('');
}

async function selectOptional(id) {
    if (!state.budget) return;
    state.budget.selectedOptional = (state.budget.selectedOptional === id) ? null : id;
    renderBudget();
    saveBudget();
}

async function deleteBudgetItem(list, id) {
    if (!state.budget) return;
    state.budget[list] = state.budget[list].filter(i => i.id !== id);
    renderBudget();
    saveBudget();
}

// ---- Budget modal helpers ----

function openBudgetIncomeEdit() {
    const b = state.budget;
    if (!b) return;
    _editTarget = { type: '__budgetIncome' };
    document.getElementById('editModalTitle').textContent = 'EDIT INCOME TARGET';
    document.getElementById('editModalBody').innerHTML = `
        <div class="form-row">
          <label>Income (ZAR)</label>
          <input type="number" id="editAmount" value="${b.income}" min="0" step="1" />
        </div>`;
    document.getElementById('editModal').classList.remove('hidden');
}

function openBudgetItemEdit(list, id) {
    const b = state.budget;
    if (!b) return;
    const item = b[list].find(i => i.id === id);
    if (!item) return;
    _editTarget = { type: `__budget_${list}`, id };
    if (list === 'baseline') {
        document.getElementById('editModalTitle').textContent = id === -1 ? 'ADD BASELINE ITEM' : 'EDIT BASELINE ITEM';
        document.getElementById('editModalBody').innerHTML = `
            <div class="form-row">
              <label>Name</label>
              <input type="text" id="editBName" value="${escHtml(item.name)}" placeholder="e.g. Rent" />
            </div>
            <div class="form-row">
              <label>Amount (ZAR)</label>
              <input type="number" id="editBAmount" value="${item.amount}" min="0" step="1" />
            </div>
            <div class="form-row">
              <label>Note</label>
              <input type="text" id="editBNote" value="${escHtml(item.note || '')}" placeholder="optional" />
            </div>`;
    } else {
        const tagColorOpts = ['gaming','wardrobe','periodic','stack'].map(v =>
            `<option value="${v}"${v === item.tagColor ? ' selected' : ''}>${v}</option>`).join('');
        document.getElementById('editModalTitle').textContent = id === -1 ? 'ADD OPTIONAL ITEM' : 'EDIT OPTIONAL ITEM';
        document.getElementById('editModalBody').innerHTML = `
            <div class="form-row">
              <label>Name</label>
              <input type="text" id="editOName" value="${escHtml(item.name)}" />
            </div>
            <div class="form-row">
              <label>Tag label</label>
              <input type="text" id="editOTag" value="${escHtml(item.tag)}" placeholder="e.g. GAMING" />
            </div>
            <div class="form-row">
              <label>Tag colour</label>
              <select id="editOTagColor">${tagColorOpts}</select>
            </div>
            <div class="form-row">
              <label>Min cost</label>
              <input type="number" id="editOMin" value="${item.min}" min="0" step="1" />
            </div>
            <div class="form-row">
              <label>Max cost</label>
              <input type="number" id="editOMax" value="${item.max}" min="0" step="1" />
            </div>`;
    }
    document.getElementById('editModal').classList.remove('hidden');
}

function openBudgetAddItem(list) {
    const b = state.budget;
    if (!b) return;
    const newId = Math.max(0, ...b[list].map(i => i.id)) + 1;
    if (list === 'baseline') {
        b.baseline.push({ id: newId, name: '', amount: 0, note: '' });
    } else {
        b.optional.push({ id: newId, name: '', tag: '', tagColor: 'gaming', min: 0, max: 0 });
    }
    openBudgetItemEdit(list, newId);
}

async function saveBudgetEdit() {
    if (!_editTarget) return;
    const { type, id } = _editTarget;

    if (type === '__budgetIncome') {
        const val = parseFloat(document.getElementById('editAmount').value);
        if (isNaN(val) || val <= 0) { alert('Enter a valid income amount.'); return; }
        state.budget.income = val;

    } else if (type === '__budget_baseline') {
        const item = state.budget.baseline.find(i => i.id === id);
        if (!item) return;
        const name   = document.getElementById('editBName').value.trim();
        const amount = parseFloat(document.getElementById('editBAmount').value);
        const note   = document.getElementById('editBNote').value.trim();
        if (!name || isNaN(amount) || amount < 0) { alert('Enter a valid name and amount.'); return; }
        item.name = name; item.amount = amount; item.note = note;

    } else if (type === '__budget_optional') {
        const item = state.budget.optional.find(i => i.id === id);
        if (!item) return;
        const name     = document.getElementById('editOName').value.trim();
        const tag      = document.getElementById('editOTag').value.trim();
        const tagColor = document.getElementById('editOTagColor').value;
        const min      = parseFloat(document.getElementById('editOMin').value) || 0;
        const max      = parseFloat(document.getElementById('editOMax').value) || 0;
        if (!name) { alert('Enter a name.'); return; }
        item.name = name; item.tag = tag; item.tagColor = tagColor; item.min = min; item.max = max;
    } else {
        // fallback to regular entry edit
        saveEdit();
        return;
    }

    closeEditModal();
    renderBudget();
    saveBudget();
}

document.addEventListener('DOMContentLoaded', () => {
  renderAll();
  initConverter();
  loadBudget();
  fetchRate();
  setInterval(() => fetchRate(), 60 * 60 * 1000);

  // Entry edit modal
  document.getElementById('editSaveBtn').addEventListener('click', () => {
      if (_editTarget && _editTarget.type && _editTarget.type.startsWith('__budget')) {
          saveBudgetEdit();
      } else {
          saveEdit();
      }
  });
  document.getElementById('editCancelBtn').addEventListener('click', closeEditModal);
  document.getElementById('editModalClose').addEventListener('click', closeEditModal);
  document.getElementById('editModal').addEventListener('click', e => {
      if (e.target === e.currentTarget) closeEditModal();
  });

  // Budget UI buttons
  document.getElementById('budgetEditIncomeBtn').addEventListener('click', openBudgetIncomeEdit);
  document.getElementById('budgetAddBaselineBtn').addEventListener('click', () => openBudgetAddItem('baseline'));
  document.getElementById('budgetAddOptionalBtn').addEventListener('click', () => openBudgetAddItem('optional'));

  // PDF Import
  initialisePdfImport();
});

// ── PDF Import ─────────────────────────────────────────────────────────────

const CATEGORY_OPTIONS = {
  income: ['Salary', 'Transfer In', 'Rental Income', 'Other Income'],
  fixed_expense: ['Rent', 'Insurance', 'Subscription', 'Medical Aid', 'Loan Repayment', 'Utilities', 'Other'],
  variable_expense: ['Food & Drink', 'Fuel', 'Transport', 'Shopping', 'Gaming', 'Clothing', 'Other'],
};

function initialisePdfImport() {
  const btn = document.getElementById('pdf-import-btn');
  const input = document.getElementById('pdf-upload-input');
  btn.addEventListener('click', () => input.click());
  input.addEventListener('change', () => {
    if (input.files[0]) handlePdfFileSelected(input.files[0]);
    input.value = '';
  });
  document.getElementById('pdf-modal-close').addEventListener('click', closePdfModal);
  document.getElementById('pdf-confirm-btn').addEventListener('click', confirmImport);
  document.getElementById('pdf-select-all').addEventListener('change', e => {
    document.querySelectorAll('.pdf-row-check').forEach(cb => cb.checked = e.target.checked);
    updateConfirmButtonState();
  });
}

async function handlePdfFileSelected(file) {
  if (!file.name.toLowerCase().endsWith('.pdf')) {
    showToast('Please upload a PDF file.', 'error'); return;
  }
  if (file.size > 10 * 1024 * 1024) {
    showToast('This file is too large. Please upload a PDF under 10MB.', 'error'); return;
  }

  showPdfLoading(true);
  try {
    const form = new FormData();
    form.append('statement', file);
    const res = await fetch(`${API}/pdf/preview`, { method: 'POST', body: form });
    const data = await res.json();

    if (!res.ok || !data.success) {
      showToast(data.error || 'Failed to parse PDF.', 'error');
      return;
    }
    renderPreviewModal(data);
  } catch (err) {
    showToast('Could not reach the server. Is it running?', 'error');
  } finally {
    showPdfLoading(false);
  }
}

function renderPreviewModal(parsedData) {
  const { transactions, summary } = parsedData;

  document.getElementById('pdf-modal-summary').innerHTML =
    `Found <strong>${summary.total_transactions}</strong> transactions &nbsp;·&nbsp; ` +
    `<span class="conf-high">&#9679; ${summary.high_confidence} high</span> &nbsp; ` +
    `<span class="conf-medium">&#9675; ${summary.medium_confidence} medium</span> &nbsp; ` +
    `<span class="conf-low">&#9675; ${summary.low_confidence} low &#9888;</span> &nbsp;|&nbsp; ` +
    `Credits: <strong>R ${summary.total_credits.toFixed(2)}</strong> &nbsp; ` +
    `Debits: <strong>R ${summary.total_debits.toFixed(2)}</strong>`;

  const tbody = document.getElementById('pdf-preview-tbody');
  tbody.innerHTML = '';

  transactions.forEach((txn, i) => {
    const isLow = txn.confidence === 'low';
    const isUnclassified = txn.suggested_type === 'unclassified';
    const tr = document.createElement('tr');
    if (isLow || isUnclassified) tr.classList.add('row-low-conf');

    const confIcon = txn.confidence === 'high' ? '<span class="conf-high">&#9679; HIGH</span>'
      : txn.confidence === 'medium' ? '<span class="conf-medium">&#9675; MED</span>'
      : '<span class="conf-low">&#9675; LOW &#9888;</span>';

    tr.innerHTML = `
      <td><input type="checkbox" class="pdf-row-check" data-idx="${i}" checked></td>
      <td>${txn.date}</td>
      <td title="${txn.raw_description}">${txn.description}</td>
      <td>R ${txn.amount.toFixed(2)}</td>
      <td>
        <select class="pdf-type-select" data-idx="${i}">
          ${isUnclassified ? '<option value="">— Select —</option>' : ''}
          <option value="income"${txn.suggested_type === 'income' ? ' selected' : ''}>Income</option>
          <option value="variable_expense"${txn.suggested_type === 'variable_expense' ? ' selected' : ''}>Variable Expense</option>
          <option value="fixed_expense"${txn.suggested_type === 'fixed_expense' ? ' selected' : ''}>Fixed Expense</option>
          <option value="skip">Skip</option>
        </select>
      </td>
      <td>
        <select class="pdf-cat-select" data-idx="${i}"></select>
      </td>
      <td>${confIcon}</td>
    `;

    tbody.appendChild(tr);

    const typeSelect = tr.querySelector('.pdf-type-select');
    const catSelect = tr.querySelector('.pdf-cat-select');
    updateCategoryOptions(typeSelect, catSelect, txn.suggested_category);
    typeSelect.addEventListener('change', () => {
      updateCategoryOptions(typeSelect, catSelect, null);
      updateConfirmButtonState();
    });
    tr.querySelector('.pdf-row-check').addEventListener('change', updateConfirmButtonState);
  });

  document.getElementById('pdf-modal-overlay').classList.remove('hidden');
  document.getElementById('pdf-modal-error').classList.add('hidden');
  updateConfirmButtonState();
}

function updateCategoryOptions(typeSelect, catSelect, preselect) {
  const type = typeSelect.value;
  const options = CATEGORY_OPTIONS[type] || [];
  catSelect.innerHTML = options.map(o =>
    `<option value="${o}"${preselect === o ? ' selected' : ''}>${o}</option>`
  ).join('');
  if (!preselect && options.length) catSelect.value = options[0];
}

function updateConfirmButtonState() {
  const confirmBtn = document.getElementById('pdf-confirm-btn');
  const rows = document.querySelectorAll('#pdf-preview-tbody tr');
  let allValid = true;
  rows.forEach(tr => {
    const cb = tr.querySelector('.pdf-row-check');
    if (cb && cb.checked) {
      const typeSelect = tr.querySelector('.pdf-type-select');
      if (!typeSelect.value) allValid = false;
    }
  });
  confirmBtn.disabled = !allValid;
}

function closePdfModal() {
  document.getElementById('pdf-modal-overlay').classList.add('hidden');
}

async function confirmImport() {
  const rows = document.querySelectorAll('#pdf-preview-tbody tr');
  const transactions = [];

  rows.forEach(tr => {
    const cb = tr.querySelector('.pdf-row-check');
    const typeSelect = tr.querySelector('.pdf-type-select');
    const catSelect = tr.querySelector('.pdf-cat-select');

    const cells = tr.querySelectorAll('td');
    const date = cells[1].textContent.trim();
    const description = cells[2].textContent.trim();
    const amountText = cells[3].textContent.replace('R', '').trim();
    const amount = parseFloat(amountText);

    transactions.push({
      date,
      description,
      amount,
      confirmed_type: cb.checked ? typeSelect.value : 'skip',
      confirmed_category: catSelect.value || 'Other',
    });
  });

  const confirmBtn = document.getElementById('pdf-confirm-btn');
  confirmBtn.disabled = true;
  confirmBtn.textContent = 'Importing…';

  try {
    const res = await fetch(`${API}/pdf/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ transactions }),
    });
    const data = await res.json();

    if (!res.ok) {
      showImportError('Import failed. Please try again.');
      return;
    }

    closePdfModal();
    const msg = data.errors.length
      ? `${data.inserted} imported, ${data.errors.length} failed.`
      : `${data.inserted} transactions imported successfully.`;
    showToast(msg, data.errors.length ? 'warn' : 'success');

    renderAll();

  } catch (err) {
    showImportError('Could not reach the server.');
  } finally {
    confirmBtn.disabled = false;
    confirmBtn.textContent = 'Confirm Import';
  }
}

function showImportError(msg) {
  const el = document.getElementById('pdf-modal-error');
  el.textContent = msg;
  el.classList.remove('hidden');
}

function showPdfLoading(show) {
  document.getElementById('pdf-loading-overlay').classList.toggle('hidden', !show);
}

function showToast(msg, type = 'success') {
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = msg;
  document.body.appendChild(toast);
  setTimeout(() => toast.classList.add('toast-visible'), 10);
  setTimeout(() => { toast.classList.remove('toast-visible'); setTimeout(() => toast.remove(), 400); }, 3500);
}
