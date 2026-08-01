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
const demoSelect       = document.getElementById('demo-select');

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
  const refIcon = document.getElementById('ref-icon');
  const refTitle = document.getElementById('ref-title');
  const list = document.getElementById('referral-reasons');

  banner.style.display = 'flex';
  if (referral.referral_recommended) {
    banner.className = 'referral-banner ref-urgent';
    refIcon.textContent = '🚨';
    refTitle.textContent = 'Referral Recommended';
    list.innerHTML = referral.reasons.map(r => `<li>${escHtml(r)}</li>`).join('');
    list.style.display = 'block';
  } else {
    banner.className = 'referral-banner ref-ok';
    refIcon.textContent = '✓';
    refTitle.textContent = 'Continue Routine Monitoring';
    list.innerHTML = '';
    list.style.display = 'none';
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

  if (arc) {
    const offset = CIRCUMFERENCE * (1 - Math.min(percent, 1));
    arc.style.strokeDashoffset = offset;
  }
  if (scoreEl) scoreEl.textContent = scoreText;
  if (categoryEl) categoryEl.textContent = categoryText;

  if (card) card.className = `gauge-card risk-${riskLevel}`;
}

function renderIDRS(idrs) {
  const bar = document.getElementById('idrs-breakdown');
  const labels = document.getElementById('idrs-breakdown-labels');

  if (!idrs.risk_score && idrs.risk_score !== 0) {
    setGauge('gauge-idrs', 'idrs-arc', 0, '—', 'No data', 'na');
    if (bar) bar.style.display = 'none';
    if (labels) labels.style.display = 'none';
    return;
  }
  const score   = idrs.risk_score;
  const cat     = idrs.risk_category || '—';
  const pct     = score / 100;
  const level   = cat.includes('High') ? 'high' : cat.includes('Moderate') ? 'mod' : 'low';
  
  const unitEl = document.getElementById('idrs-unit');
  if (unitEl) unitEl.textContent = '/100 points';
  
  setGauge('gauge-idrs', 'idrs-arc', pct, score, cat, level);

  // Explainability Breakdown
  if (idrs.extra_data && idrs.extra_data.total !== undefined) {
    const d = idrs.extra_data;
    const colors = ['#0f172a', '#475569', '#94a3b8', '#cbd5e1']; // Dark to light neutral
    const parts = [
      { k: 'Age', v: d.age_pts },
      { k: 'Waist', v: d.waist_pts },
      { k: 'Activity', v: d.activity_pts },
      { k: 'Family', v: d.family_pts }
    ];
    
    let barHtml = '';
    let labelHtml = '';
    parts.forEach((p, i) => {
      const w = d.total === 0 ? 0 : (p.v / d.total) * 100;
      if (w > 0) {
        barHtml += `<div class="breakdown-segment" style="width:${w}%; background:${colors[i]}"></div>`;
        labelHtml += `<div class="bl-item"><div class="bl-color" style="background:${colors[i]}"></div>${p.k}: ${p.v}</div>`;
      }
    });
    
    if (bar) { bar.innerHTML = barHtml; bar.style.display = 'flex'; }
    if (labels) { labels.innerHTML = labelHtml; labels.style.display = 'flex'; }
  } else {
    if (bar) bar.style.display = 'none';
    if (labels) labels.style.display = 'none';
  }
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
  let html = escHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>');
    
  if (html.toLowerCase().includes('patient summary') && html.toLowerCase().includes('referral note')) {
    // Basic heuristic to split the text into two distinct sections for typography
    const parts = html.split(/Referral Note/i);
    return `<div class="llm-section-patient">${parts[0]}</div>
            <div class="llm-section-clinical"><strong>Referral Note</strong><br>${parts[1]}</div>`;
  }
  return html;
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

// ============================================================
// DEMO / SAMPLE TESTCASES
// ============================================================
const SYNTHETIC_PATIENTS = [
    {
      "id": "P01_low_risk_full_data",
      "demographics": { "age": 32, "sex": "female" },
      "diabetes": { "waist_circumference_cm": 74, "physical_activity": "vigorous", "family_history_diabetes": "none", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 112, "diastolic_bp": 72, "smoking_status": "non_smoker", "total_cholesterol_mmol_l": 3.8, "bmi": 21.5, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 0.7, "urine_acr_mg_g": 8 },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P02_moderate_risk_full_data",
      "demographics": { "age": 46, "sex": "male" },
      "diabetes": { "waist_circumference_cm": 92, "physical_activity": "moderate", "family_history_diabetes": "one_parent", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 128, "diastolic_bp": 82, "smoking_status": "non_smoker", "total_cholesterol_mmol_l": 5.0, "bmi": 26.5, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 0.9, "urine_acr_mg_g": 22 },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P03_high_risk_full_data",
      "demographics": { "age": 55, "sex": "male" },
      "diabetes": { "waist_circumference_cm": 95, "physical_activity": "sedentary", "family_history_diabetes": "one_parent", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 145, "diastolic_bp": 90, "smoking_status": "smoker", "total_cholesterol_mmol_l": 5.5, "bmi": 28.0, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 1.2, "urine_acr_mg_g": 45 },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P04_missing_labs_moderate",
      "demographics": { "age": 48, "sex": "female" },
      "diabetes": { "waist_circumference_cm": 88, "physical_activity": "mild", "family_history_diabetes": "one_parent", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 134, "diastolic_bp": 86, "smoking_status": "non_smoker", "total_cholesterol_mmol_l": null, "bmi": 27.0, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": null, "urine_acr_mg_g": null },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P05_minimal_data_vitals_only",
      "demographics": { "age": 51, "sex": "male" },
      "diabetes": { "waist_circumference_cm": 101, "physical_activity": "sedentary", "family_history_diabetes": "both_parents", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 138, "diastolic_bp": 88, "smoking_status": "smoker", "total_cholesterol_mmol_l": null, "bmi": null, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": null, "urine_acr_mg_g": null },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P06_fully_normal",
      "demographics": { "age": 29, "sex": "female" },
      "diabetes": { "waist_circumference_cm": 70, "physical_activity": "vigorous", "family_history_diabetes": "none", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 108, "diastolic_bp": 70, "smoking_status": "non_smoker", "total_cholesterol_mmol_l": 3.5, "bmi": 20.5, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 0.6, "urine_acr_mg_g": 5 },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P07_multi_comorbid_severe",
      "demographics": { "age": 63, "sex": "male" },
      "diabetes": { "waist_circumference_cm": 104, "physical_activity": "sedentary", "family_history_diabetes": "both_parents", "known_diabetes_diagnosis": "yes" },
      "cardio": { "systolic_bp": 168, "diastolic_bp": 98, "smoking_status": "smoker", "total_cholesterol_mmol_l": 6.4, "bmi": 31.0, "known_clinical_cvd": "yes", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 2.1, "urine_acr_mg_g": 340 },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P08_known_diabetes_diagnosis",
      "demographics": { "age": 58, "sex": "female" },
      "diabetes": { "waist_circumference_cm": 96, "physical_activity": "mild", "family_history_diabetes": "one_parent", "known_diabetes_diagnosis": "yes" },
      "cardio": { "systolic_bp": 132, "diastolic_bp": 84, "smoking_status": "non_smoker", "total_cholesterol_mmol_l": 5.2, "bmi": 27.5, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 1.0, "urine_acr_mg_g": 35 },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    },
    {
      "id": "P09_acute_ischemic_stroke",
      "demographics": { "age": 67, "sex": "male" },
      "diabetes": { "waist_circumference_cm": 98, "physical_activity": "sedentary", "family_history_diabetes": "none", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 192, "diastolic_bp": 112, "smoking_status": "smoker", "total_cholesterol_mmol_l": 5.8, "bmi": 26.0, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 1.1, "urine_acr_mg_g": 18 },
      "stroke": { "prior_stroke_tia": "yes", "acute_stroke_type": "acute_ischemic_tpa_eligible" }
    },
    {
      "id": "P10_elderly_boundary_values",
      "demographics": { "age": 70, "sex": "female" },
      "diabetes": { "waist_circumference_cm": 91, "physical_activity": "mild", "family_history_diabetes": "one_parent", "known_diabetes_diagnosis": "no" },
      "cardio": { "systolic_bp": 181, "diastolic_bp": 95, "smoking_status": "smoker", "total_cholesterol_mmol_l": null, "bmi": 34.6, "known_clinical_cvd": "no", "newly_diagnosed_htn": "no" },
      "kidney": { "serum_creatinine_mg_dl": 1.3, "urine_acr_mg_g": 60 },
      "stroke": { "prior_stroke_tia": "no", "acute_stroke_type": "none" }
    }
];

if (demoSelect) {
  demoSelect.addEventListener('change', (e) => {
    const pId = e.target.value;
    if (!pId) {
      form.reset();
      strokeHoursField.style.display = 'none';
      return;
    }
    const p = SYNTHETIC_PATIENTS.find(x => x.id === pId);
    if (!p) return;

    document.getElementById('age').value = p.demographics.age || '';
    document.getElementById('sex').value = p.demographics.sex || '';
    document.getElementById('waist').value = p.diabetes.waist_circumference_cm || '';
    document.getElementById('physical_activity').value = p.diabetes.physical_activity || '';
    document.getElementById('family_history_diabetes').value = p.diabetes.family_history_diabetes || '';
    
    // UI expects true/false for some boolean selects
    document.getElementById('has_diabetes').value = p.diabetes.known_diabetes_diagnosis === 'yes' ? 'true' : 'false';
    
    document.getElementById('systolic_bp').value = p.cardio.systolic_bp || '';
    document.getElementById('diastolic_bp').value = p.cardio.diastolic_bp || '';
    
    // UI expects true/false for smoking select in some designs? Wait, let's check index.html.
    // In index.html: <input type="checkbox" or <select> for is_smoker? Let me use what was in the original demo:
    // document.getElementById('is_smoker').value = p.cardio.smoking_status === 'smoker' ? 'true' : 'false'; 
    // Wait, let's look at the old demoBtn code to be exact.
    const isSmokerEl = document.getElementById('is_smoker');
    if (isSmokerEl) isSmokerEl.value = p.cardio.smoking_status === 'smoker' ? 'true' : 'false';
    
    const cholEl = document.getElementById('total_cholesterol');
    if (cholEl) cholEl.value = p.cardio.total_cholesterol_mmol_l || '';
    
    document.getElementById('bmi').value = p.cardio.bmi || '';
    
    const cvdEl = document.getElementById('known_cvd');
    if (cvdEl) cvdEl.value = p.cardio.known_clinical_cvd === 'yes' ? 'true' : 'false';
    
    document.getElementById('newly_diagnosed_htn').value = p.cardio.newly_diagnosed_htn === 'yes' ? 'true' : 'false';
    
    document.getElementById('serum_creatinine').value = p.kidney.serum_creatinine_mg_dl || '';
    document.getElementById('urine_acr').value = p.kidney.urine_acr_mg_g || '';
    
    document.getElementById('prior_stroke').value = p.stroke.prior_stroke_tia === 'yes' ? 'true' : 'false';
    document.getElementById('acute_stroke_type').value = p.stroke.acute_stroke_type === 'none' ? '' : p.stroke.acute_stroke_type;
    
    strokeHoursField.style.display = p.stroke.acute_stroke_type === 'ich' ? 'flex' : 'none';
  });
}

// ============================================================
// THEME TOGGLE (DARK MODE)
// ============================================================
const themeToggleBtn = document.getElementById('theme-toggle');

// Check for saved theme preference, otherwise use system preference
const savedTheme = localStorage.getItem('theme');
const systemPrefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;

if (savedTheme === 'dark' || (!savedTheme && systemPrefersDark)) {
  document.documentElement.setAttribute('data-theme', 'dark');
  if (themeToggleBtn) themeToggleBtn.textContent = '☀️';
} else {
  document.documentElement.setAttribute('data-theme', 'light');
  if (themeToggleBtn) themeToggleBtn.textContent = '🌙';
}

if (themeToggleBtn) {
  themeToggleBtn.addEventListener('click', () => {
    const currentTheme = document.documentElement.getAttribute('data-theme');
    if (currentTheme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'light');
      localStorage.setItem('theme', 'light');
      themeToggleBtn.textContent = '🌙';
    } else {
      document.documentElement.setAttribute('data-theme', 'dark');
      localStorage.setItem('theme', 'dark');
      themeToggleBtn.textContent = '☀️';
    }
  });
}

