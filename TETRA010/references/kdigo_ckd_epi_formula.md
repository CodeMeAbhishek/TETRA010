# KDIGO / CKD-EPI Reference — CKD Scoring Engine Inputs

Backing reference for `engine_ckd.py`. This file supplies what `IDRS.txt` and
`2017_ACC_AHA.txt` do not: the eGFR formula and the KDIGO staging grid.

---

## 1. eGFR — CKD-EPI 2021 (race-free) creatinine equation

Inputs required: serum creatinine (mg/dL), age (years), sex.

```
eGFR = 142 × min(Scr/κ, 1)^α × max(Scr/κ, 1)^(-1.200) × 0.9938^Age × (1.012 if female)
```

Where:
- `κ` = 0.7 for females, 0.9 for males
- `α` = -0.241 for females, -0.302 for males
- `Scr` = serum creatinine in mg/dL

Result units: mL/min/1.73m².

**Pseudocode:**
```python
def egfr_ckd_epi_2021(scr_mg_dl: float, age: int, sex: str) -> float:
    kappa = 0.7 if sex == "female" else 0.9
    alpha = -0.241 if sex == "female" else -0.302
    ratio = scr_mg_dl / kappa
    egfr = 142 * (min(ratio, 1) ** alpha) * (max(ratio, 1) ** -1.200) * (0.9938 ** age)
    if sex == "female":
        egfr *= 1.012
    return egfr
```

## 2. GFR categories (from eGFR)

| Category | eGFR (mL/min/1.73m²) | Description |
|---|---|---|
| G1 | ≥90 | Normal |
| G2 | 60–89 | Mildly decreased |
| G3a | 45–59 | Mild–moderate decrease |
| G3b | 30–44 | Moderate–severe decrease |
| G4 | 15–29 | Severe decrease |
| G5 | <15 | Kidney failure |

## 3. Albuminuria categories (from urine ACR, mg/g)

| Category | ACR (mg/g) | Description |
|---|---|---|
| A1 | <30 | Normal / mildly increased |
| A2 | 30–300 | Moderately increased |
| A3 | >300 | Severely increased |

## 4. KDIGO combined risk heat-map (G × A)

Cell values are relative risk of CKD progression, kidney failure, cardiovascular events, and
death — Green (low) → Yellow (moderately increased) → Orange (high) → Red (very high).

| | A1 (<30) | A2 (30–300) | A3 (>300) |
|---|---|---|---|
| **G1 (≥90)** | Green | Yellow | Orange |
| **G2 (60–89)** | Green | Yellow | Orange |
| **G3a (45–59)** | Yellow | Orange | Red |
| **G3b (30–44)** | Orange | Red | Red |
| **G4 (15–29)** | Red | Red | Red |
| **G5 (<15)** | Red | Red | Red |

**Referral rule (feeds Section 5 of RULES.md):** any Red cell, or G3b+/A3 specifically, should
trigger the referral banner.

## 5. Graceful-degradation logic (missing labs)

Implement in this order of preference:

1. **Creatinine + ACR both available** → full G×A heat-map cell (as above).
2. **Creatinine only** → compute G-stage, output it, and flag: "Urine ACR not available —
   recommend to complete KDIGO risk grid."
3. **Neither available** → do not fabricate a stage. Instead compute a pre-test probability
   flag from other engines' outputs already in the record:
   - Diabetes present (IDRS Moderate/High or known diagnosis) **and**
   - Hypertension present (Stage 1+) **and**
   - Age ≥50 **and/or** family history of diabetes/CKD
   - → "High pre-test probability for CKD — recommend serum creatinine (eGFR) + urine ACR."
   This flag should still surface even if only one or two of these conditions are met, at a
   lower urgency tier — do not suppress the recommendation entirely just because the full
   pattern isn't present.

**Do not** let the LLM layer estimate an eGFR or ACR value when labs are missing — the module
either returns a computed number from the formula above, or it returns `null` + a
missing-investigation flag. No LLM-estimated fallback.
