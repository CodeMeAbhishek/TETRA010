# AI-Powered Lifestyle Disease Risk Prediction & Early Referral Assistant

**Track A / HealthTech Problem Statement 1**

Welcome to our project! This repository houses an offline-capable, deterministic, rule-based clinical decision support assistant designed to identify and stratify risk for lifestyle diseases in low-resource and primary healthcare (PHC) settings.

## 🎯 The Core Problem
Healthcare workers in low-resource settings often lack the immediate clinical tools to rapidly identify undiagnosed lifestyle diseases. Our solution takes patient data (demographics, symptoms, vitals, history, and available labs) and automatically computes risk, flags missing tests, and recommends referrals based on globally recognized medical guidelines.

## 🏗️ The Golden Rule of our Architecture
**The LLM never computes a clinical score. Ever.**

To ensure 100% medical accuracy, reliability, and trust from clinical evaluators, our architecture strictly separates risk calculation from AI explanation:
1. **The Rule-Based Clinical Scoring Engine**: A suite of pure, deterministic Python functions that calculate risk based strictly on verified medical guidelines (no LLM hallucination).
2. **The LLM Orchestration Layer**: The LLM sits *on top* of the scoring engine. It receives structured JSON data and uses its natural language capabilities to explain the score to the patient (in multiple languages), draft referral notes, and personalize education.

## 🧠 Supported Clinical Modules
Our scoring engine currently evaluates 5 major conditions using verified guidelines:
1. **Diabetes (MDRF-IDRS)**: Uses the Indian Diabetes Risk Score tailored for the Asian Indian phenotype (strongly weighting waist circumference).
2. **Cardiovascular Disease (WHO-CVD)**: Uses digitized WHO South Asia Risk Charts (both lab-based and BMI-fallback non-lab charts).
3. **Hypertension (2017 ACC/AHA)**: Categorizes blood pressure and dictates complex treatment timelines.
4. **Chronic Kidney Disease (KDIGO)**: Computes eGFR via the CKD-EPI 2021 equation and stratifies risk across the KDIGO G×A Heatmap.
5. **Stroke**: Integrated via the ACC/AHA acute stroke protocols and secondary prevention guidelines.

## 🗂️ Project Structure
* `/backend/scoring/`: The deterministic clinical engines, missing investigations aggregator, and referral decision engine.
* `/backend/orchestrator.py`: The bridge that securely passes structured clinical data to the LLM.
* `/references/`: Source-of-truth medical guidelines, source images, and research papers used to build the logic.
* `test_engines.py`: Our exhaustive test suite (currently at 86% coverage) validating the clinical logic against edge cases.

## 🚀 How to Run Tests
The clinical engines are thoroughly unit-tested to ensure perfect alignment with medical guidelines.
```bash
python -m unittest test_engines.py
```

## 📚 Clinical References & Sources
The logic in this engine is strictly built upon verified medical guidelines. The source documents and validation papers are stored locally in the `/references/` directory.

- **Diabetes (MDRF-IDRS):**
  - *Source:* Validated via the ICMR-INDIAB national study.
  - *Web Link:* [MDRF-IDRS / ICMR-INDIAB Validation](https://pubmed.ncbi.nlm.nih.gov/21745422/)
  - *Local File:* `/references/IDRS.txt` and `/references/Indian_Diabetes_Risk_Score_in_detecting_undiagnosed_diabetes_in_the_Indian_population.md`
- **Cardiovascular Disease (WHO-CVD):**
  - *Source:* WHO CVD Risk Charts for South Asia (2019).
  - *Web Link:* [WHO CVD Risk Chart Working Group](https://www.who.int/publications/i/item/9789241515986)
  - *Local File:* `/references/south-asia-1.png` (lab-based) and `/references/south-asia-2.png` (non-lab-based)
- **Hypertension (ACC/AHA):**
  - *Source:* 2017 ACC/AHA Guideline for the Prevention, Detection, Evaluation, and Management of High Blood Pressure in Adults.
  - *Web Link:* [AHA/ACC 2017 Guidelines](https://www.ahajournals.org/doi/10.1161/HYP.0000000000000065)
  - *Local File:* `/references/2017_ACC_AHA.txt`
- **Chronic Kidney Disease (KDIGO):**
  - *Source:* KDIGO 2012 / 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease.
  - *Web Link:* [KDIGO CKD Guidelines](https://kdigo.org/guidelines/ckd-evaluation-and-management/)
  - *Local File:* `/references/kdigo_ckd_epi_formula.md` and KDIGO heatmaps (`/references/kdigo_heatmap (1).png`)

