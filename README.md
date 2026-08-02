# Nidan: Clinical Decision Support System

**Track A / HealthTech Problem Statement 1**

🚀 **Live Deployment:** Check out the working prototype here: [https://tetra-010-quu9.vercel.app/](https://tetra-010-quu9.vercel.app/)

This repository contains a clinical decision support system for primary healthcare. It identifies the risk of lifestyle diseases. The system operates locally and uses a deterministic rules engine. 

## 1. The Core Problem
Healthcare workers in low-resource settings need tools to identify undiagnosed diseases. Our software uses patient data to calculate risk, identify missing tests, and recommend referrals. The calculations follow established medical guidelines.

## 2. System Architecture
**The Large Language Model (LLM) never calculates a clinical score.**

The architecture has two distinct layers to ensure medical accuracy:
1. **The Rule-Based Clinical Scoring Engine**: Python functions calculate risk. These functions strictly follow medical guidelines. 
2. **The LLM Orchestration Layer**: The LLM receives the calculated scores as structured JSON data. It translates these scores into patient-friendly explanations in multiple languages. It also generates referral notes.

## 🧠 Supported Clinical Modules

Our scoring engine currently evaluates 5 major conditions using verified guidelines:

- **Diabetes (MDRF-IDRS)**: Uses the Indian Diabetes Risk Score tailored for the Asian Indian phenotype (strongly weighting waist circumference).
- **Cardiovascular Disease (WHO-CVD)**: Uses digitized WHO South Asia Risk Charts (both lab-based and BMI-fallback non-lab charts).
- **Hypertension (2017 ACC/AHA)**: Categorizes blood pressure and dictates complex treatment timelines.
- **Chronic Kidney Disease (KDIGO)**: Computes eGFR via the CKD-EPI 2021 equation and stratifies risk across the KDIGO G×A Heatmap.
- **Stroke**: Integrated via the ACC/AHA acute stroke protocols and secondary prevention guidelines.

## 3. Project Structure
- `/backend/scoring/`: The clinical engines, missing investigations aggregator, and referral decision engine.
- `/backend/api.py`: The FastAPI server.
- `/backend/orchestrator.py`: The integration layer for the LLM API.
- `/frontend/`: The user interface (HTML, CSS, JavaScript).
- `/references/`: The medical guidelines and source documents.
- `test_engines.py`: The unit test suite.

## 4. How to Run the Application
1. **Install dependencies:**
   ```bash
   pip install fastapi uvicorn pydantic openai python-dotenv
   ```
2. **Configure the API key:**
   Copy `.env.example` to `.env` and add your NVIDIA NIM or OpenRouter API key.
3. **Start the Backend API:**
   ```bash
   python main.py
   ```
   *The backend will run on `http://localhost:8000`.*
4. **Start the Frontend UI:**
   Open a new terminal and run:
   ```bash
   python -m http.server 8081 --directory frontend
   ```
5. **Access the Application:**
   Open a web browser and go to `http://localhost:8081/`. This is the unified landing page where you can choose to enter either the **Patient Portal (Consumer Tier)** or the **Clinician Dashboard**.

## 5. How to Run Tests
The clinical engines use unit tests to ensure alignment with medical guidelines.
```bash
python -m unittest test_engines.py -v
```

## 📚 Clinical References & Sources

The logic in this engine is strictly built upon verified medical guidelines. The source documents and validation papers are stored locally in the `/references/` directory.

- **Diabetes (MDRF-IDRS):**
  - *Source:* Validated via the ICMR-INDIAB national study.
  - *Web Link:* [MDRF-IDRS / ICMR-INDIAB Validation](https://ijmr.org.in/evaluation-of-madras-diabetes-research-foundation-indian-diabetes-risk-score-in-detecting-undiagnosed-diabetes-in-the-indian-population-results-from-the-indian-council-of-medical-research-india-diabe/)
  - *Local File:* `/references/IDRS.txt` and `/references/Indian_Diabetes_Risk_Score_in_detecting_undiagnosed_diabetes_in_the_Indian_population.md`
- **Cardiovascular Disease (WHO-CVD):**
  - *Source:* WHO CVD Risk Charts for South Asia (2019).
  - *Web Link:* [WHO CVD Risk Chart Working Group](https://www.who.int/docs/default-source/cardiovascular-diseases/south-asia.pdf?sfvrsn=c5b0d9a32)
  - *Local File:* `/references/south-asia-1.png` (lab-based) and `/references/south-asia-2.png` (non-lab-based)
- **Hypertension (ACC/AHA):**
  - *Source:* 2017 ACC/AHA Guideline for the Prevention, Detection, Evaluation, and Management of High Blood Pressure in Adults.
  - *Web Link:* [AHA/ACC 2017 Guidelines](https://www.jacc.org/doi/10.1016/j.jacc.2017.11.006)
  - *Local File:* `/references/2017_ACC_AHA.txt`
- **Chronic Kidney Disease (KDIGO):**
  - *Source:* KDIGO 2012 / 2024 Clinical Practice Guideline for the Evaluation and Management of Chronic Kidney Disease.
  - *Web Link:* [KDIGO CKD Guidelines Heatmap](https://kdigo.org/heat-map/)
  - *Local File:* `/references/kdigo_ckd_epi_formula.md` and KDIGO heatmaps (`/references/kdigo_heatmap (1).png`)



## 🌟 Consumer Tier (New)

The Consumer Tier provides a natural-language chat interface (`/consumer.html`) where patients can type symptoms or upload lab reports. The system safely extracts values, asks follow-up questions for missing required fields (Gap Analysis), and never guesses clinical data. 

**Key Safety Features:**
- **Plausibility Bounds:** Out-of-range clinical values (e.g. BP=50) are intercepted.
- **Polarity Grounding:** The assistant strictly respects stored negative/positive traits (e.g. "sedentary" is not confused with "active").
- **Strict Orchestration:** The LLM still never calculates scores; it only formats inputs for the same deterministic clinical engines used by the Clinician UI.
- **Seamless Triage Handoff:** Once a patient completes the consumer screening, their extracted data and recommended referral are securely placed into a triage queue, instantly appearing on the Clinician Dashboard (`clinician.html`) for doctor review.

## ☁️ Deployment (Render & Vercel)

This repository is configured for easy, zero-downtime deployment:
1. **Backend (Render):** Uses the `render.yaml` Blueprint to automatically deploy the FastAPI service.
2. **Frontend (Vercel):** The `vercel.json` configures Vercel to serve the static frontend app. Make sure to set the **Root Directory** in Vercel to `frontend` so it doesn't accidentally trigger a Python build. The frontend logic dynamically targets your Render URL when deployed.
