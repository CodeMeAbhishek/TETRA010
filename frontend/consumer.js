'use strict';

// ============================================================
// CONFIG
// ============================================================
const IS_LOCAL = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
const API_BASE = IS_LOCAL ? 'http://localhost:8000' : 'https://nidan-backend-k7jj.onrender.com';

// ============================================================
// STATE
// ============================================================
let conversationHistory = [];  // [{role, content}]
let currentPayload = null;     // ConsumerIntakePayload or null
let pendingConfirmations = [];
let conflicts = [];
let assessmentResults = null;
let isLoading = false;

// Demo State
let demoScenarios = [];
let currentDemo = null;
let currentDemoTurnIndex = 0;
let isAutoPlaying = false;
let autoPlayTimer = null;

// ============================================================
// DOM REFERENCES
// ============================================================
const chatArea      = document.getElementById('chat-area');
const chatInput     = document.getElementById('chat-input');
const btnSend       = document.getElementById('btn-send');
const btnUpload     = document.getElementById('btn-upload');
const fileInput     = document.getElementById('report-file-input');
const btnAssess     = document.getElementById('btn-assess');
const assessBar     = document.getElementById('assess-bar');
const apiStatus     = document.getElementById('consumer-api-status');
const welcomeCard   = document.getElementById('welcome-card');
const themeToggle   = document.getElementById('consumer-theme-toggle');

const demoSelect    = document.getElementById('demo-select');
const demoControls  = document.getElementById('demo-controls');
const demoIndicator = document.getElementById('demo-indicator');
const demoBtnNext   = document.getElementById('demo-btn-next');
const demoBtnReset  = document.getElementById('demo-btn-reset');
const demoAutoPlay  = document.getElementById('demo-auto-play');
const demoStatusText= document.getElementById('demo-status-text');

// ============================================================
// THEME TOGGLE (matches clinician UI pattern)
// ============================================================
const savedTheme = localStorage.getItem('nidan-theme') || 'light';
document.documentElement.setAttribute('data-theme', savedTheme);
themeToggle.textContent = savedTheme === 'dark' ? '☀️' : '🌙';

themeToggle.addEventListener('click', () => {
  const current = document.documentElement.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  localStorage.setItem('nidan-theme', next);
  themeToggle.textContent = next === 'dark' ? '☀️' : '🌙';
});

// ============================================================
// API STATUS CHECK
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
// HINT CHIPS
// ============================================================
document.querySelectorAll('.hint-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    chatInput.value = chip.dataset.hint;
    sendMessage();
  });
});

// ============================================================
// SEND MESSAGE
// ============================================================
chatInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
});

btnSend.addEventListener('click', sendMessage);

async function sendMessage() {
  const text = chatInput.value.trim();
  if (!text || isLoading) return;

  // Hide welcome card
  if (welcomeCard) welcomeCard.style.display = 'none';

  // Add user message to UI and history
  addMessage('user', text);
  conversationHistory.push({ role: 'user', content: text });
  chatInput.value = '';
  setLoading(true);

  try {
    const response = await fetch(`${API_BASE}/consumer/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        conversation: conversationHistory,
        current_payload: currentPayload,
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();

    // Update state
    currentPayload = data.updated_payload;
    pendingConfirmations = data.pending_confirmations || [];
    conflicts = data.conflicts || [];

    // Add assistant response
    addMessage('assistant', data.assistant_message);
    conversationHistory.push({ role: 'assistant', content: data.assistant_message });

    // Render verification cards
    if (pendingConfirmations.length > 0) {
      renderVerificationCards(pendingConfirmations);
    }

    // Render conflicts
    if (conflicts.length > 0) {
      renderConflicts(conflicts);
    }

    // Render gap summary pills
    if (data.gap_summary) {
      renderGapPills(data.gap_summary);
    }

    // Show/hide assess button
    updateAssessButton(data.gap_summary);

  } catch (err) {
    addMessage('assistant', `Sorry, I encountered an error: ${err.message}. Please try again.`);
  } finally {
    setLoading(false);
  }
}

// ============================================================
// UPLOAD REPORT
// ============================================================
btnUpload.addEventListener('click', () => fileInput.click());

fileInput.addEventListener('change', async () => {
  const file = fileInput.files[0];
  if (!file) return;

  if (welcomeCard) welcomeCard.style.display = 'none';

  addMessage('user', `📎 Uploaded: ${file.name}`);
  setLoading(true);

  try {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/consumer/upload-report`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    addMessage('assistant', data.message);

    // If fields were extracted, show verification cards
    if (Object.keys(data.extracted_fields).length > 0) {
      const cards = Object.entries(data.extracted_fields).map(([name, field]) => ({
        field_name: name,
        value: field.value,
        source: field.source,
        confidence: field.confidence,
      }));
      renderVerificationCards(cards);
    }

  } catch (err) {
    addMessage('assistant', `Could not process the report: ${err.message}`);
  } finally {
    setLoading(false);
    fileInput.value = '';
  }
});

// ============================================================
// CONFIRM FIELD
// ============================================================
async function confirmField(fieldName, value, wasEdited) {
  try {
    const response = await fetch(`${API_BASE}/consumer/confirm-field`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        field_name: fieldName,
        confirmed_value: value,
        was_edited: wasEdited,
        current_payload: currentPayload,
      }),
    });

    if (!response.ok) throw new Error(`HTTP ${response.status}`);

    const data = await response.json();
    currentPayload = data.updated_payload;

    // Remove the card from UI
    const card = document.getElementById(`verify-${fieldName}`);
    if (card) {
      card.style.opacity = '0';
      card.style.transform = 'translateX(-10px)';
      setTimeout(() => card.remove(), 200);
    }

  } catch (err) {
    console.error('Confirm field failed:', err);
  }
}

// ============================================================
// ASSESS
// ============================================================
btnAssess.addEventListener('click', runAssessment);

async function runAssessment() {
  if (!currentPayload || isLoading) return;

  setLoading(true);
  btnAssess.disabled = true;
  btnAssess.textContent = '⏳ Running Assessment…';

  try {
    const response = await fetch(`${API_BASE}/consumer/assess`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        payload: currentPayload,
        language: 'English',
      }),
    });

    if (!response.ok) {
      const err = await response.json().catch(() => ({}));
      throw new Error(err.detail || `HTTP ${response.status}`);
    }

    const data = await response.json();
    assessmentResults = data;
    renderResults(data);

  } catch (err) {
    addMessage('assistant', `Assessment failed: ${err.message}`);
  } finally {
    setLoading(false);
    btnAssess.disabled = false;
    btnAssess.textContent = '🔬 Get My Results';
  }
}

// ============================================================
// UI HELPERS
// ============================================================

function addMessage(role, content) {
  const div = document.createElement('div');
  div.className = `msg msg-${role}`;
  div.textContent = content;
  chatArea.appendChild(div);
  scrollToBottom();
}

function setLoading(loading) {
  isLoading = loading;
  btnSend.disabled = loading;
  chatInput.disabled = loading;

  // Remove existing typing indicator
  const existing = document.getElementById('typing-indicator');
  if (existing) existing.remove();

  if (loading) {
    const indicator = document.createElement('div');
    indicator.className = 'typing-indicator';
    indicator.id = 'typing-indicator';
    indicator.innerHTML = '<span class="typing-dot"></span><span class="typing-dot"></span><span class="typing-dot"></span>';
    chatArea.appendChild(indicator);
    scrollToBottom();
  }
}

function scrollToBottom() {
  requestAnimationFrame(() => {
    chatArea.scrollTop = chatArea.scrollHeight;
  });
}

function renderVerificationCards(cards) {
  const container = document.createElement('div');
  container.className = 'verification-cards';

  cards.forEach(card => {
    const el = document.createElement('div');
    el.className = 'verify-card';
    el.id = `verify-${card.field_name}`;
    el.style.transition = 'opacity 0.2s, transform 0.2s';

    const label = formatFieldName(card.field_name);
    const sourceTag = card.source === 'extracted_from_document' ? '📄 From report' :
                      card.source === 'inferred' ? '🤔 Inferred' : '✓ Stated';

    el.innerHTML = `
      <div class="verify-info">
        <div class="verify-label">${label}</div>
        <div class="verify-value">${card.value}</div>
        <div class="verify-source">${sourceTag} · ${Math.round(card.confidence * 100)}% confidence</div>
      </div>
      <div class="verify-actions">
        <button class="btn-verify btn-confirm" data-field="${card.field_name}" data-value="${card.value}">✓ Confirm</button>
        <button class="btn-verify btn-edit" data-field="${card.field_name}">✎ Edit</button>
      </div>
    `;

    // Confirm handler
    el.querySelector('.btn-confirm').addEventListener('click', (e) => {
      confirmField(e.target.dataset.field, card.value, false);
    });

    // Edit handler
    el.querySelector('.btn-edit').addEventListener('click', (e) => {
      const fieldName = e.target.dataset.field;
      const newValue = prompt(`Enter corrected value for ${formatFieldName(fieldName)}:`, card.value);
      if (newValue !== null && newValue.trim() !== '') {
        // Try to parse as number if appropriate
        let parsed = newValue.trim();
        const num = parseFloat(parsed);
        if (!isNaN(num) && isFinite(num)) parsed = num;
        confirmField(fieldName, parsed, true);
      }
    });

    container.appendChild(el);
  });

  chatArea.appendChild(container);
  scrollToBottom();
}

function renderConflicts(conflictList) {
  conflictList.forEach(conflict => {
    const el = document.createElement('div');
    el.className = 'conflict-banner';
    el.innerHTML = `
      <strong>⚠ Conflict:</strong> ${formatFieldName(conflict.field_name)} was previously
      <strong>${conflict.old_value}</strong> (${conflict.old_source}) but new input says
      <strong>${conflict.new_value}</strong> (${conflict.new_source}).
      The earlier confirmed value is kept. You can re-state to override.
    `;
    chatArea.appendChild(el);
  });
  scrollToBottom();
}

function renderGapPills(gapSummary) {
  const container = document.createElement('div');
  container.className = 'gap-pills';

  const engineNames = { idrs: 'Diabetes', cvd: 'CVD', htn: 'Blood Pressure', ckd: 'Kidney' };

  for (const [key, info] of Object.entries(gapSummary)) {
    let isOk = info.can_run;
    if (key === 'ckd') {
      // CKD degrades gracefully, so can_run is always true. 
      // But we only want the pill to turn green if actual kidney labs were provided.
      const hasCreatinine = !info.missing_optional.includes('serum_creatinine_mg_dl');
      const hasAcr = !info.missing_optional.includes('urine_acr_mg_g');
      isOk = hasCreatinine || hasAcr;
    }

    const pill = document.createElement('span');
    pill.className = `gap-pill ${isOk ? 'gap-pill-ok' : 'gap-pill-missing'}`;
    pill.textContent = `${isOk ? '✓' : '○'} ${engineNames[key] || key}`;
    container.appendChild(pill);
  }

  chatArea.appendChild(container);
  scrollToBottom();
}

function updateAssessButton(gapSummary) {
  if (!gapSummary) return;
  // Show button if at least one engine can run
  const anyCanRun = Object.values(gapSummary).some(info => info.can_run);
  assessBar.className = anyCanRun ? 'assess-bar visible' : 'assess-bar';
}

function renderResults(data) {
  const panel = document.createElement('div');
  panel.className = 'results-panel';

  let html = '<h3>🩺 Your Health Assessment</h3>';

  // Engine results
  const engines = [
    { key: 'idrs_diabetes_risk', name: 'Diabetes Risk (IDRS)', scoreKey: 'risk_score', catKey: 'risk_category' },
    { key: 'who_cvd_risk', name: '10-Year Heart Attack / Stroke Risk', scoreKey: 'risk_percentage', catKey: null },
    { key: 'hypertension_risk', name: 'Blood Pressure', scoreKey: null, catKey: 'risk_category' },
    { key: 'ckd_kdigo_risk', name: 'Kidney Health (KDIGO)', scoreKey: null, catKey: 'risk_category' },
  ];

  engines.forEach(engine => {
    const result = data.structured_data[engine.key];
    if (!result) return;

    const score = engine.scoreKey ? result[engine.scoreKey] : null;
    const category = engine.catKey ? result[engine.catKey] : null;
    const hasData = score != null || category != null;

    html += `<div class="result-engine">`;
    html += `<div class="result-engine-name">${engine.name}</div>`;

    if (hasData) {
      if (score != null) {
        html += `<div class="result-engine-score">${score}${engine.key === 'who_cvd_risk' ? '' : ' / 100'}</div>`;
      }
      if (category) {
        const catClass = getCategoryClass(category);
        html += `<span class="result-engine-category ${catClass}">${category}</span>`;
      }
      // Extra data
      const extra = result.extra_data || {};
      if (extra.chart_used) {
        html += `<div class="result-missing">Chart: ${extra.chart_used === 'lab_based' ? 'Lab-based' : 'Non-lab (BMI-based)'}</div>`;
      }
      if (extra.eGFR != null) {
        html += `<div class="result-missing">eGFR: ${Math.round(extra.eGFR * 10) / 10} mL/min</div>`;
      }
    } else {
      // Engine could not score — show what's needed
      const missing = result.missing_inputs || [];
      if (missing.length > 0) {
        html += `<div class="result-missing">Could not score — needs: ${missing.map(m => m.test_name || m.test || '').join(', ')}</div>`;
      } else if (result.extra_data && result.extra_data.error) {
        html += `<div class="result-missing">${result.extra_data.error}</div>`;
      } else {
        html += `<div class="result-missing">Insufficient data for this assessment.</div>`;
      }
    }

    html += `</div>`;
  });

  // Missing investigations
  const missing = data.structured_data.missing_investigations || [];
  if (missing.length > 0) {
    html += `<div class="result-engine"><div class="result-engine-name">Recommended Tests</div>`;
    missing.forEach(m => {
      const testName = m.test_name || m.test || '';
      const reasons = m.reasons ? m.reasons.join('; ') : (m.reason || '');
      html += `<div class="result-missing">• <strong>${testName}</strong> — ${reasons}</div>`;
    });
    html += `</div>`;
  }

  // Referral
  const referral = data.structured_data.referral_decision || {};
  if (referral.referral_recommended) {
    html += `<div class="referral-banner-consumer">`;
    html += `<strong>⚠ Referral Recommended</strong><br/>`;
    (referral.reasons || []).forEach(r => {
      html += `• ${r}<br/>`;
    });
    html += `</div>`;
  }

  // LLM explanation
  if (data.llm_explanation && !data.llm_explanation.startsWith('[LLM disabled')) {
    const contentHtml = window.marked ? window.marked.parse(data.llm_explanation) : escapeHtml(data.llm_explanation);
    html += `<div class="result-llm" style="line-height: 1.6; font-size: 0.95rem;">${contentHtml}</div>`;
  }

  // ── Patient → Clinician Handoff (Queue) ──────────────────────────────────
  let handoff = null;
  if (currentPayload) {
    handoff = {
      id: 'patient_' + Date.now() + Math.random().toString(36).substr(2, 5),
      timestamp: new Date().toISOString(),
      payload: currentPayload,
      assessment_summary: {
        engines_run: engines.filter(e => data.structured_data[e.key] && (
          (e.scoreKey && data.structured_data[e.key][e.scoreKey] != null) ||
          (e.catKey  && data.structured_data[e.key][e.catKey]  != null)
        )).map(e => e.name),
        referral_recommended: (data.structured_data.referral_decision || {}).referral_recommended || false,
      }
    };
  }

  // Add "Submit to Clinician" CTA button
  const ctaDiv = document.createElement('div');
  ctaDiv.style.cssText = 'margin-top:1rem; padding: 1rem; background: var(--bg-card); border: 1px solid var(--brand-blue); border-radius: var(--radius-md); display:flex; align-items:center; gap:1rem; flex-wrap:wrap;';
  ctaDiv.innerHTML = `
    <div style="flex:1; min-width:180px;">
      <div style="font-weight:600; color:var(--text-primary); font-size:0.95rem;">📋 Submit your assessment</div>
      <div style="font-size:0.82rem; color:var(--text-secondary); margin-top:0.2rem;">Your answers are ready. Submit them securely to your doctor's queue.</div>
    </div>
    <button type="button" class="btn-assess" style="padding:0.5rem 1.25rem; font-size:0.9rem; white-space:nowrap;" id="btn-submit-to-clinician">
      Submit to Doctor
    </button>
  `;
  
  panel.innerHTML = html;
  panel.appendChild(ctaDiv); // append CTA inside the panel
  chatArea.appendChild(panel);
  scrollToBottom();

  const submitBtn = document.getElementById('btn-submit-to-clinician');
  if (submitBtn && handoff) {
    submitBtn.addEventListener('click', () => {
      // 1. Read existing queue
      let queue = [];
      const rawQueue = localStorage.getItem('nidan-patient-queue');
      if (rawQueue) {
        try { queue = JSON.parse(rawQueue); } catch (e) {}
      }
      
      // 2. Add current patient
      queue.push(handoff);
      localStorage.setItem('nidan-patient-queue', JSON.stringify(queue));
      
      // 3. Update UI to show completion
      ctaDiv.innerHTML = `<div style="color: var(--brand-green); font-weight: 600; width: 100%; text-align: center;">✅ Sent successfully. Please return the device to the front desk or close this window.</div>`;
      document.getElementById('chat-input-bar').style.display = 'none'; // disable further chat
    });
  }

  // Hide assess bar after showing results
  assessBar.className = 'assess-bar';
}

function getCategoryClass(category) {
  if (!category) return 'cat-na';
  const lower = category.toLowerCase();
  if (lower.includes('low') || lower.includes('normal') || lower.includes('green')) return 'cat-low';
  if (lower.includes('moderate') || lower.includes('elevated') || lower.includes('yellow')) return 'cat-mod';
  if (lower.includes('stage 1') || lower.includes('orange')) return 'cat-high';
  if (lower.includes('high') || lower.includes('stage 2') || lower.includes('red')) return 'cat-vhigh';
  return 'cat-na';
}

function formatFieldName(name) {
  const labels = {
    age: 'Age',
    sex: 'Sex',
    waist_circumference_cm: 'Waist Circumference (cm)',
    physical_activity: 'Physical Activity',
    family_history_diabetes: 'Family History — Diabetes',
    is_smoker: 'Smoker',
    systolic_bp: 'Systolic BP',
    diastolic_bp: 'Diastolic BP',
    total_cholesterol_mmol_L: 'Total Cholesterol (mmol/L)',
    bmi: 'BMI',
    has_diabetes: 'Diabetes Diagnosis',
    serum_creatinine_mg_dl: 'Serum Creatinine (mg/dL)',
    urine_acr_mg_g: 'Urine ACR (mg/g)',
    ascvd_10y_risk_percent: '10-Year ASCVD Risk (%)',
    known_clinical_cvd: 'Known CVD',
  };
  return labels[name] || name.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// ============================================================
// DEMO SCENARIOS
// ============================================================

// Fetch scenarios
(async () => {
  try {
    const r = await fetch('demo-scenarios.json');
    if (r.ok) {
      demoScenarios = await r.json();
      demoScenarios.forEach(sc => {
        const opt = document.createElement('option');
        opt.value = sc.id;
        opt.textContent = sc.label;
        demoSelect.appendChild(opt);
      });
      // Add document upload scenario manually
      const docOpt = document.createElement('option');
      docOpt.value = 'document_upload_demo';
      docOpt.textContent = 'Document Upload Demo (Stub)';
      demoSelect.appendChild(docOpt);
    }
  } catch (err) {
    console.error('Failed to load demo scenarios', err);
  }
})();

demoSelect.addEventListener('change', (e) => {
  const id = e.target.value;
  if (!id) {
    resetDemo();
    return;
  }
  
  if (id === 'document_upload_demo') {
    startDocumentDemo();
    return;
  }

  currentDemo = demoScenarios.find(s => s.id === id);
  if (currentDemo) {
    startDemo();
  }
});

demoBtnReset.addEventListener('click', () => {
  demoSelect.value = '';
  resetDemo();
});

demoBtnNext.addEventListener('click', playNextTurn);

demoAutoPlay.addEventListener('change', (e) => {
  isAutoPlaying = e.target.checked;
  if (isAutoPlaying && currentDemo && currentDemoTurnIndex < currentDemo.turns.length) {
    playNextTurn();
  }
});

function resetDemo() {
  currentDemo = null;
  currentDemoTurnIndex = 0;
  isAutoPlaying = false;
  demoAutoPlay.checked = false;
  clearTimeout(autoPlayTimer);
  
  demoControls.style.display = 'none';
  demoStatusText.textContent = '';
  
  // Clear chat
  chatArea.innerHTML = '';
  if (welcomeCard) {
    welcomeCard.style.display = 'block';
    chatArea.appendChild(welcomeCard);
  }
  
  conversationHistory = [];
  currentPayload = null;
  pendingConfirmations = [];
  conflicts = [];
  assessmentResults = null;
  
  updateAssessButton({});
  demoBtnNext.disabled = false;
  demoBtnNext.textContent = 'Next Turn';
}

function startDemo() {
  resetDemo(); // clear state but keep currentDemo logic separate
  // restore currentDemo which was cleared by resetDemo
  currentDemo = demoScenarios.find(s => s.id === demoSelect.value); 
  
  demoControls.style.display = 'flex';
  demoStatusText.textContent = currentDemo.description;
  demoIndicator.textContent = 'Demo: ' + currentDemo.label;
  
  if (welcomeCard) welcomeCard.style.display = 'none';
  addMessage('assistant', `Loaded scenario: ${currentDemo.label}. Click 'Next Turn' to begin.`);
}

async function startDocumentDemo() {
  resetDemo();
  demoControls.style.display = 'flex';
  demoStatusText.textContent = "Auto-attaching synthetic lab report image...";
  demoIndicator.textContent = 'Demo: Document Upload';
  demoBtnNext.disabled = true; // no turns for doc demo
  
  if (welcomeCard) welcomeCard.style.display = 'none';
  
  try {
    // Fetch the sample image as a blob
    const res = await fetch('demo-assets/sample-lab-report.png');
    if (!res.ok) throw new Error('Could not fetch sample image.');
    const blob = await res.blob();
    const file = new File([blob], 'sample-lab-report.png', { type: 'image/png' });
    
    // Create an artificial file input event
    const dataTransfer = new DataTransfer();
    dataTransfer.items.add(file);
    fileInput.files = dataTransfer.files;
    
    addMessage('user', `📎 Uploaded: ${file.name}`);
    addMessage('assistant', `(Demo Mode: Document Extraction is stubbed)`);
    
    // Trigger the file upload handler defined earlier
    const changeEvent = new Event('change');
    fileInput.dispatchEvent(changeEvent);
    
  } catch (err) {
    addMessage('assistant', `Error running document demo: ${err.message}`);
  }
}

async function playNextTurn() {
  if (!currentDemo || currentDemoTurnIndex >= currentDemo.turns.length) {
    demoBtnNext.disabled = true;
    demoBtnNext.textContent = 'Scenario Complete';
    return;
  }
  
  const text = currentDemo.turns[currentDemoTurnIndex];
  currentDemoTurnIndex++;
  
  demoBtnNext.disabled = true;
  chatInput.value = text;
  
  // Wait a moment for visual effect, then send
  setTimeout(async () => {
    await sendMessage();
    demoBtnNext.disabled = false;
    
    if (currentDemoTurnIndex >= currentDemo.turns.length) {
      demoBtnNext.textContent = 'Run Assessment';
      demoBtnNext.onclick = async () => {
        demoBtnNext.disabled = true;
        await runAssessment();
        demoBtnNext.textContent = 'Scenario Complete';
        demoBtnNext.onclick = playNextTurn; // restore
      };
      if (isAutoPlaying) {
        autoPlayTimer = setTimeout(() => demoBtnNext.click(), 2000);
      }
    } else if (isAutoPlaying) {
      autoPlayTimer = setTimeout(playNextTurn, 2000);
    }
  }, 500);
}
