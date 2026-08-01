'use strict';

// ============================================================
// CONFIG
// ============================================================
const API_BASE = 'http://localhost:8000';

// ============================================================
// DOM REFERENCES
// ============================================================
const form           = document.getElementById('patient-form');
const submitBtn      = document.getElementById('submit-btn');
const resultsSection = document.getElementById('results-section');
const formSection    = document.getElementById('form-section');
const newBtn         = document.getElementById('new-assessment-btn');
const strokeTypeSelect = document.getElementById('acute_stroke_type');
const strokeHoursField = document.getElementById('stroke-hours-field');
const apiStatus        = document.getElementById('api-status');

// ============================================================
// SHOW/HIDE STROKE HOURS FIELD
// ============================================================
strokeTypeSelect.addEventListener('change', () => {
  strokeHoursField.style.display =
    strokeTypeSelect.value === 'ich' ? 'flex' : 'none';
});

// ============================================================
// PING API ON LOAD
// ============================================================
(async () => {
  try {
    const r = await fetch(`${API_BASE}/health`, { method: 'GET' });
    if (r.ok) {
      apiStatus.textContent = '● API Ready';
      apiStatus.className = 'badge badge--green';
    } else {
      throw new Error();
    }
  } catch {
    apiStatus.textContent = '● API Offline';
    apiStatus.className = 'badge badge--red';
  }
})();

// ============================================================
// FORM SUBMIT
// ============================================================
form.addEventListener('submit', async (e) => {
  e.preventDefault();
  setLoading(true);

  const payload = buildPayload();

  try {
    const response = await fetch(`${API_BASE}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    renderResults(data, payload.language);

  } catch (err) {
    alert(`Error calling API: ${err.message}\n\nMake sure the backend server is running:\n  python main.py`);
  } finally {
    setLoading(false);
  }
});

// ============================================================
// BUILD PAYLOAD FROM FORM
// ============================================================
function buildPayload() {
  const fd = new FormData(form);
  const payload = {};

  const intFields    = ['age', 'systolic_bp', 'diastolic_bp'];
  const floatFields  = ['waist_circumference_cm', 'total_cholesterol_mmol_L', 'bmi',
                        'serum_creatinine_mg_dl', 'urine_acr_mg_g',
                        'ascvd_10y_risk_percent', 'hours_since_stroke_onset'];
  const boolFields   = ['is_smoker', 'has_diabetes', 'known_clinical_cvd',
                        'has_previous_stroke_or_tia', 'is_newly_diagnosed_htn'];
  const stringFields = ['sex', 'physical_activity', 'family_history_diabetes',
                        'acute_stroke_type', 'language'];

  for (const [key, val] of fd.entries()) {
    if (val === '' || val === null) continue;

    if (intFields.includes(key)) {
      payload[key] = parseInt(val, 10);
    } else if (floatFields.includes(key)) {
      payload[key] = parseFloat(val);
    } else if (boolFields.includes(key)) {
      payload[key] = val === 'true';
    } else if (stringFields.includes(key)) {
      payload[key] = val;
    }
  }

  // Defaults
  if (!payload.language) payload.language = 'English';
  if (payload.is_newly_diagnosed_htn === undefined) payload.is_newly_diagnosed_htn = false;

  return payload;
}

// ============================================================
// RENDER RESULTS
// ============================================================
function renderResults(data, language) {
  const sd = data.structured_data;
  const idrs = sd.idrs_diabetes_risk;
  const htn  = sd.hypertension_risk;
  const cvd  = sd.who_cvd_risk;
  const ckd  = sd.ckd_kdigo_risk;
  const missing  = sd.missing_investigations || [];
  const referral = sd.referral_decision;

  // ---- Referral banner ----
  const banner = document.getElementById('referral-banner');
  if (referral.referral_recommended) {
    banner.style.display = 'flex';
    const list = document.getElementById('referral-reasons');
    list.innerHTML = referral.reasons
      .map(r => `<li>${escHtml(r)}</li>`)
      .join('');
  } else {
    banner.style.display = 'none';
  }

  // ---- Gauges ----
  renderIDRS(idrs);
  renderHTN(htn);
  renderCVD(cvd);
  renderCKD(ckd);

  // ---- Missing investigations ----
  renderMissing(missing);

  // ---- HTN treatment detail ----
  renderHTNDetail(htn);

  // ---- CKD detail ----
  renderCKDDetail(ckd);

  // ---- LLM explanation ----
  renderLLM(data.llm_explanation, language);

  // ---- Show results, hide form ----
  formSection.style.display   = 'none';
  resultsSection.style.display = 'block';
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

// ============================================================
// GAUGE HELPERS
// ============================================================
const CIRCUMFERENCE = 2 * Math.PI * 40; // r=40

function setGauge(cardId, arcId, percent, scoreText, categoryText, riskLevel) {
  const card = document.getElementById(cardId);
  const arc  = document.getElementById(arcId);
  const scoreEl    = document.getElementById(`${arcId.replace('-arc','-score')}`);
  const categoryEl = document.getElementById(`${arcId.replace('-arc','-category')}`);

  const offset = CIRCUMFERENCE * (1 - Math.min(percent, 1));
  arc.style.strokeDashoffset = offset;
  scoreEl.textContent    = scoreText;
  categoryEl.textContent = categoryText;

  card.className = `gauge-card risk-${riskLevel}`;
}

function renderIDRS(idrs) {
  if (!idrs.risk_score && idrs.risk_score !== 0) {
    setGauge('gauge-idrs', 'idrs-arc', 0, '—', 'No data', 'na');
    return;
  }
  const score   = idrs.risk_score;
  const cat     = idrs.risk_category || '—';
  const pct     = score / 100;
  const level   = cat.includes('High') ? 'high' : cat.includes('Moderate') ? 'mod' : 'low';
  document.getElementById('idrs-unit').textContent = '/100';
  setGauge('gauge-idrs', 'idrs-arc', pct, score, cat, level);
}

function renderHTN(htn) {
  const cat = htn.risk_category || '';
  let pct = 0, level = 'na', scoreText = '—';
  const stages = { 'Normal BP': 0.15, 'Elevated BP': 0.4, 'Stage 1 Hypertension': 0.65, 'Stage 2 Hypertension': 1.0 };
  if (cat && stages[cat] !== undefined) {
    pct = stages[cat];
    scoreText = cat.replace(' Hypertension','').replace(' BP','');
    level = cat === 'Normal BP' ? 'low' : cat === 'Elevated BP' ? 'mod' : cat === 'Stage 1 Hypertension' ? 'mod' : 'high';
  } else if (!cat) {
    scoreText = 'N/A';
  }
  setGauge('gauge-htn', 'htn-arc', pct, scoreText, cat || 'No BP data', level);
}

function renderCVD(cvd) {
  const raw = cvd.risk_percentage || '';
  if (!raw) {
    setGauge('gauge-cvd', 'cvd-arc', 0, '—', 'No data', 'na');
    return;
  }
  const num = parseInt(raw.split('-')[0].replace('%','').trim(), 10);
  const pct = num / 100;
  const level = num < 5 ? 'low' : num < 10 ? 'mod' : num < 20 ? 'mod' : num < 30 ? 'high' : 'vhigh';
  const chart = cvd.extra_data?.chart_used === 'lab_based' ? '(Lab-based)' : '(Non-lab)';
  setGauge('gauge-cvd', 'cvd-arc', pct, raw, chart, level);
}

function renderCKD(ckd) {
  const color = ckd.risk_category;
  const gStage = ckd.extra_data?.G_stage || '';
  const aStage = ckd.extra_data?.A_stage || '';
  const label  = gStage && aStage ? `${gStage} + ${aStage}` : gStage || 'Insufficient data';

  const colorMap = { Green: {pct:0.2, level:'low'}, Yellow: {pct:0.4, level:'mod'},
                     Orange: {pct:0.65, level:'mod'}, Red: {pct:0.9, level:'high'} };
  const c = colorMap[color] || {pct:0, level:'na'};
  setGauge('gauge-ckd', 'ckd-arc', c.pct, color || '—', label, c.level);
}

// ============================================================
// MISSING INVESTIGATIONS
// ============================================================
function renderMissing(missing) {
  const list  = document.getElementById('missing-list');
  const empty = document.getElementById('missing-empty');
  const count = document.getElementById('missing-count');

  list.innerHTML = '';
  if (!missing.length) {
    empty.style.display = 'block';
    count.style.display = 'none';
    return;
  }
  empty.style.display = 'none';
  count.textContent = `${missing.length} tests`;
  count.style.display = 'inline';

  missing.forEach(m => {
    const reasons = (m.reasons || []).join(' ');
    const citations = (m.guideline_citations || []).join(', ');
    list.insertAdjacentHTML('beforeend', `
      <li>
        <span class="missing-test">${escHtml(m.test_name)}</span>
        <span class="missing-reason">${escHtml(reasons)}</span>
        <span class="missing-citation">Source: ${escHtml(citations)}</span>
      </li>
    `);
  });
}

// ============================================================
// HTN TREATMENT DETAIL
// ============================================================
function renderHTNDetail(htn) {
  const el = document.getElementById('htn-treatment-content');
  const items = [];

  const treatment = htn.extra_data?.treatment_recommendation;
  const reassess  = htn.extra_data?.reassess_timeline;
  const targets   = htn.extra_data?.cross_module_targets || [];
  const acuteFlag = htn.extra_data?.acute_care_flag;
  const acuteAct  = htn.extra_data?.acute_stroke_action;

  if (acuteFlag) {
    items.push({ key: '🚨 ACUTE CARE', val: acuteAct || 'Activate acute stroke protocol' });
  }
  if (treatment) items.push({ key: 'Recommended Action', val: treatment });
  if (reassess)  items.push({ key: 'Reassess In', val: reassess });
  targets.forEach(t => items.push({ key: 'Cross-Module Target', val: t }));

  if (!items.length) {
    el.innerHTML = '<p style="color:var(--text-3);font-size:0.85rem">No blood pressure data provided.</p>';
    return;
  }

  el.innerHTML = items.map(i => `
    <div class="detail-row-item">
      <span class="detail-key">${escHtml(i.key)}</span>
      <span class="detail-val">${escHtml(i.val)}</span>
    </div>
  `).join('');
}

// ============================================================
// CKD DETAIL
// ============================================================
function renderCKDDetail(ckd) {
  const card = document.getElementById('ckd-detail-card');
  const el   = document.getElementById('ckd-detail-content');
  const ex   = ckd.extra_data || {};

  if (!ex.G_stage && !ex.eGFR) {
    card.style.display = 'none';
    return;
  }
  card.style.display = 'block';

  const items = [];
  if (ex.eGFR)    items.push({ key: 'eGFR (CKD-EPI 2021)', val: `${ex.eGFR.toFixed(1)} mL/min/1.73m²` });
  if (ex.G_stage) items.push({ key: 'G Stage', val: ex.G_stage });
  if (ex.A_stage) items.push({ key: 'A Stage', val: ex.A_stage });
  if (ckd.risk_category) items.push({ key: 'KDIGO Risk Color', val: ckd.risk_category });

  el.innerHTML = items.map(i => `
    <div class="detail-row-item">
      <span class="detail-key">${escHtml(i.key)}</span>
      <span class="detail-val">${escHtml(i.val)}</span>
    </div>
  `).join('');
}

// ============================================================
// LLM EXPLANATION
// ============================================================
function renderLLM(text, language) {
  const placeholder = document.getElementById('llm-placeholder');
  const llmText     = document.getElementById('llm-text');
  const llmDisabled = document.getElementById('llm-disabled');
  const langBadge   = document.getElementById('llm-lang-badge');

  placeholder.style.display = 'none';
  langBadge.textContent = language;

  if (!text || text.startsWith('[LLM disabled')) {
    llmDisabled.style.display = 'flex';
    llmText.style.display = 'none';
  } else {
    llmDisabled.style.display = 'none';
    llmText.style.display = 'block';
    llmText.innerHTML = formatLLMText(text);
  }
}

function formatLLMText(text) {
  // Convert markdown-style bold (**text**) to <strong>
  return escHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
}

// ============================================================
// HELPERS
// ============================================================
function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function setLoading(on) {
  if (on) {
    submitBtn.classList.add('loading');
    submitBtn.disabled = true;
  } else {
    submitBtn.classList.remove('loading');
    submitBtn.disabled = false;
  }
}

// ============================================================
// NEW ASSESSMENT BUTTON
// ============================================================
newBtn.addEventListener('click', () => {
  resultsSection.style.display = 'none';
  formSection.style.display    = 'block';
  // Reset LLM panel for next run
  document.getElementById('llm-placeholder').style.display = 'flex';
  document.getElementById('llm-text').style.display        = 'none';
  document.getElementById('llm-disabled').style.display    = 'none';
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
