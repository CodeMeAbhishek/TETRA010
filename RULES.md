# RULES.md — Rule-Based Clinical Scoring Engine (Track A / HealthTech-1)

This file governs how any coding agent (Antigravity, Claude Code, etc.) must build and modify
this codebase. Re-read this file at the start of every session and any time the agent's
behavior seems to drift from it.

---

## 0. What this project is

An AI-powered clinical decision support assistant that:
1. Takes patient data (demographics, symptoms, vitals, history, meds, labs — often incomplete).
2. Computes risk for 5 conditions: **Diabetes, Hypertension, CKD, Cardiovascular Disease, Stroke**.
3. Identifies missing investigations and recommends evidence-based tests to close the gap.
4. Recommends referral when risk crosses a defined threshold, with a explanation of *why*.
5. Runs independently of any hospital IT system, is multilingual, explainable, and usable in
   low-resource primary care (PHC-level, offline-capable, phone-usable by a health worker).

Reference: `problem_statement.txt`

---

## 1. THE NON-NEGOTIABLE ARCHITECTURE RULE

**The LLM never computes a clinical score. Ever.**

- All risk scores (IDRS, WHO-CVD, ACC/AHA BP category, KDIGO stage) are produced by
  deterministic, testable, pure functions in the **Rule-Based Clinical Scoring Engine**.
- The LLM (Claude API) sits **on top of** the scoring engine's output, never underneath it.
- The LLM's only jobs are:
  - Explaining a score that was already computed (plain language, multilingual).
  - Reasoning about which investigations are missing and phrasing the recommendation.
  - Drafting referral notes/summaries from structured data it is handed.
  - Personalizing patient education material.
- The LLM must **never** be asked "what is this patient's risk?" or "does this patient have
  diabetes?" — only "explain this score: {structured JSON}".

**If an agent session ever starts hardcoding a risk number, calling an LLM to produce a score,
or skipping the scoring engine, STOP and re-read this section.** This is the single most
important architectural decision in the project and the reason judges will trust the system.

---

## 2. Reference folder — file map

| File | Purpose | Status |
|---|---|---|
| `problem_statement.txt` | Original hackathon brief (Track A, Problem 1) — source of truth for required outcomes | ✅ |
| `IDRS.txt` | MDRF-IDRS diabetes score: scoring table, thresholds, missing-investigation logic, validation stats | ✅ |
| `Indian_Diabetes_Risk_Score_in_detecting_undiagnosed_diabetes_in_the_Indian_population.md` | ICMR-INDIAB national validation paper (113,043 subjects) backing IDRS — cite this for credibility (sensitivity 60.2%, specificity 68.8%, accuracy 68.5%) | ✅ |
| `2017_ACC_AHA.txt` | HTN categories, treatment-decision logic, missing-investigation panel, CKD/diabetes/stroke cross-module interaction rules, acute + secondary stroke BP logic | ✅ |
| `south-asia-1.png` | WHO CVD risk **lab-based** chart (South Asia): age, sex, smoking, SBP, total cholesterol, diabetes status → 5-tier % risk | ✅ |
| `south-asia-2.png` | WHO CVD risk **non-lab-based** chart (South Asia): age, sex, smoking, SBP, BMI → 5-tier % risk (fallback when no lipid panel) | ✅ |
| `kdigo_ckd_epi_formula.md` | CKD-EPI 2021 eGFR formula + KDIGO G×A heat-map grid | ✅ (generated — see file) |

**Note on `2017_ACC_AHA.txt`:** this file's structure already maps directly to engine names
(Missing-Investigation Recommender, Referral & Decision Engine, Cross-Module Rules), which
suggests it was AI-summarized rather than pulled verbatim from the guideline. It is good enough
to build against, but keep the original 2017 ACC/AHA guideline PDF on hand in case a judge asks
"where exactly does the guideline say that."

---

## 3. Scoring engines — one module per condition

### 3.1 Diabetes — `engine_idrs.py`
Source: `IDRS.txt`

- Inputs (all mandatory — no labs needed):
  - Age: `<35`→0, `35–49`→20, `≥50`→30
  - Waist circumference (sex-specific): M `<90`/F `<80`→0, M `90–99`/F `80–89`→10, M `≥100`/F `≥90`→20
  - Physical activity: Vigorous→0, Moderate→10, Mild→20, Sedentary→30
  - Family history: None→0, One parent→10, Both parents→20
- **Waist circumference is a strictly mandatory field** — the module must not run without it
  (it's the Asian-Indian-phenotype variable that makes this score valid; do not substitute BMI).
- Total = sum of the four, max 100.
- Thresholds: `<30` Low · `30–50` Moderate · `≥60` High.
- Missing-investigation rule: Moderate or High → recommend Fasting Capillary Blood Glucose
  and/or OGTT.
- Explainability payload the LLM layer receives: `{age_pts, waist_pts, activity_pts,
  family_pts, total, category}` — never invent numbers not in this payload.

### 3.2 Cardiovascular Disease (+ stroke, bundled) — `engine_who_cvd.py`
Source: `south-asia-1.png` (lab-based), `south-asia-2.png` (non-lab-based)

- These are **lookup tables, not formulas** — digitize both grids into JSON:
  `{age_band, sex, smoking(y/n), sbp_band, chol_band_or_bmi_band, diabetes(y/n)} → risk_%`.
- Decision rule for which chart to use:
  1. If total cholesterol is available → use lab-based chart (`south-asia-1.png`).
  2. Else if BMI is available → use non-lab chart (`south-asia-2.png`).
  3. Else → cannot compute CVD risk; flag "BMI or lipid panel required" as missing investigation.
- Both charts already split by diabetes status (separate "People without Diabetes" / "People
  with Diabetes" panels) — diabetes status is a required input, not optional.
- Risk bands (both charts): `<5%` green · `5–<10%` yellow · `10–<20%` orange · `20–<30%` red ·
  `≥30%` purple.
- **Stroke is not a separate score.** The WHO-CVD output already bundles heart attack + stroke
  into one 10-year percentage. Label the UI output "10-year risk of heart attack or stroke."
  Do not build a second stroke-scoring module unless a judge specifically challenges this — the
  ACC/AHA doc's Pooled Cohort Equations also treat ASCVD risk as inclusive of stroke.
- Which chart version was used (lab vs non-lab) must be shown in the explainability panel.

### 3.3 Hypertension — `engine_htn.py`
Source: `2017_ACC_AHA.txt`

- Categories (higher of SBP/DBP category wins if they disagree):
  - Normal: SBP `<120` AND DBP `<80`
  - Elevated: SBP `120–129` AND DBP `<80`
  - Stage 1: SBP `130–139` OR DBP `80–89`
  - Stage 2: SBP `≥140` OR DBP `≥90`
- Treatment-decision logic (feeds the Referral & Decision Engine, not just a label):
  - Normal → lifestyle only, reassess 1 year
  - Elevated → lifestyle only, reassess 3–6 months
  - Stage 1 + ASCVD risk `<10%` → lifestyle only, reassess 3–6 months
  - Stage 1 + ASCVD risk `≥10%` or known CVD → lifestyle + medication, reassess 1 month
  - Stage 2 → lifestyle + 2-agent medication, reassess 1 month
- Missing-investigation panel to trigger for any newly-flagged HTN patient: fasting glucose,
  CBC, lipid profile, serum creatinine + eGFR, sodium/potassium/calcium, TSH, urinalysis, ECG.
  Optional (context-dependent): echo, uric acid, urinary ACR.
- Cross-module BP targets to enforce elsewhere in the engine:
  - HTN + CKD (stage 3+, or stage 1–2 with albuminuria ≥300 mg/g) → target `<130/80`, first-line ACEi/ARB
  - HTN + Diabetes → target `<130/80`, first-line thiazide/ACEi/ARB/CCB (ACEi/ARB if albuminuria)
  - HTN + prior stroke/TIA (secondary prevention) → target `<130/80`, first-line thiazide + ACEi/ARB combo
- Acute stroke BP logic (route to acute-care flag, not primary-care referral output):
  - ICH, SBP `>220` → continuous IV drug infusion, close monitoring
  - ICH, SBP `150–220` within 6h → do NOT recommend lowering to `<140` (flag as harmful, not beneficial)
  - Ischemic + eligible for IV tPA → lower to `<185/110` pre-therapy, maintain `<180/105` for 24h post
  - Ischemic, not tPA-eligible, BP `≥220/120` → may lower ~15% in first 24h
  - Ischemic, not tPA-eligible, BP `<220/120` → withhold new antihypertensives for 48–72h

### 3.4 CKD — `engine_ckd.py`
Source: `kdigo_ckd_epi_formula.md` (generated — see that file for the CKD-EPI 2021 equation
and the full KDIGO G×A heat-map grid)

- Step 1: if serum creatinine + age + sex available → compute eGFR via CKD-EPI 2021
  (race-free) equation → assign G1–G5.
- Step 2: if urine ACR available → assign A1–A3.
- Step 3: combine G×A into KDIGO heat-map color (Green/Yellow/Orange/Red).
- **Graceful degradation (this is the strongest "missing investigation" demo moment):**
  - No creatinine/ACR at all → do not compute a stage. Instead compute a *pre-test probability
    flag* from risk factors already known elsewhere in the record: diabetes present + hypertension
    present + age ≥50 + family history → "High pre-test probability for CKD — recommend serum
    creatinine (eGFR) + urine ACR."
  - Creatinine available, no ACR → compute G-stage only, flag "ACR not available — recommend to
    complete KDIGO risk grid."
  - Neither justifies skipping the flag entirely if HTN or diabetes risk is already Moderate/High —
    always surface the recommendation to test.

---

## 4. Missing-Investigation Recommender — cross-cutting rule

This is not a per-engine afterthought; it is a shared service every engine reports into.

- Each engine module returns, alongside its score, a list of `missing_inputs` it needed but
  didn't get, each tagged with **which specific test would resolve it** (not a generic "more
  labs needed").
- The Recommender aggregates these across all 5 engines into one deduplicated panel so a
  patient with both an HTN flag and a CKD flag doesn't get told to order creatinine twice.
- Every recommendation must trace back to the guideline that justifies it (IDRS →
  fasting glucose/OGTT; ACC/AHA HTN panel → the 8-test basic panel; CKD → creatinine+eGFR / ACR).
  The LLM layer may phrase this, but the *test name and the guideline citation* come from the
  engine, not the LLM.

---

## 5. Referral & Decision Engine

- Triggers a referral banner when **any** of: CVD risk ≥20%, Stage 2 HTN, CKD stage G3b+ or any
  A3, IDRS High risk with no prior diagnosis, or acute stroke logic firing.
- Referral output must include the *reason* (which score, which threshold, which guideline) —
  this is the explainability requirement from the problem statement, not optional polish.

---

## 6. LLM orchestration layer

- Receives only structured JSON from the scoring engines (scores, categories, missing_inputs,
  referral flags) — never raw patient free text passed straight into a "diagnose this" prompt.
- Responsibilities: plain-language explanation, multilingual patient education (English +
  at least one regional language, e.g. Hindi or Gujarati), referral note drafting.
- May cite validation statistics (e.g. IDRS sensitivity/specificity/accuracy from the
  ICMR-INDIAB paper) when explaining a score's limitations to a clinician — this shows judges
  the system understands IDRS is a screening tool, not a diagnostic one.

---

## 7. Standing instructions for coding agents

1. Read this file and everything in `/reference` before writing any scoring logic.
2. Confirm understanding of Section 1 (LLM never scores) before proceeding.
3. Every score-producing function must be unit-testable in isolation, with no network/LLM call
   inside it.
4. If a required input for an engine is missing, the engine must still return a partial result
   plus a `missing_inputs` list — it must never silently fail or return null.
5. If this file and the code disagree, this file wins — flag the discrepancy, don't silently
   resolve it in code.
6. Re-injection reminder for long sessions: if drift is suspected, re-paste "Re-read RULES.md
   section 1 — you're violating the no-LLM-scoring rule right now."
