"""
Nidan — Clinical Decision Pipeline Demo
Run: python demo_pipeline.py

This script demonstrates Nidan's core engineering moat:
1. It runs the deterministic clinical scoring engines LOCALLY in Python.
2. It prints the raw JSON output containing exact clinical risk scores.
3. It passes the raw JSON to the LLM (NVIDIA NIM / Claude) for translation/explanation.
This proves that the LLM is just a translator and never calculates clinical scores.
"""

import json
import os
import sys

# Reconfigure stdout to support unicode characters on Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from dotenv import load_dotenv

# Load env variables (for LLM API keys)
load_dotenv()

# Add parent directory to path so python can find backend module
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.scoring.models import PatientData
from backend.orchestrator import run_all_engines, call_llm_orchestration, _clean_payload

def load_patient_by_id(patient_id):
    with open(os.path.join("backend", "data", "synthetic_patients.json"), "r") as f:
        data = json.load(f)
    for p in data["patients"]:
        if p["id"] == patient_id:
            return p
    return None

def main():
    print("=" * 70)
    print("                NIDAN CLINICAL PIPELINE DEMO                 ")
    print("=" * 70)

    # 1. Load patient
    patient_id = "P03_high_risk_full_data"
    print(f"\n[Step 1] Loading Patient Profile: {patient_id}")
    patient_raw = load_patient_by_id(patient_id)
    if not patient_raw:
        print("Error: Patient not found!")
        return

    print(json.dumps(patient_raw, indent=2))

    # Convert to PatientData model
    # Clean the raw fields slightly
    newly_diagnosed_htn = patient_raw["cardio"].get("newly_diagnosed_htn") == "yes"
    p_data = PatientData(
        age=patient_raw["demographics"]["age"],
        sex=patient_raw["demographics"]["sex"],
        waist_circumference_cm=patient_raw["diabetes"].get("waist_circumference_cm"),
        physical_activity=patient_raw["diabetes"].get("physical_activity"),
        family_history_diabetes=patient_raw["diabetes"].get("family_history_diabetes"),
        has_diabetes=patient_raw["diabetes"].get("known_diabetes_diagnosis") == "yes",
        systolic_bp=patient_raw["cardio"].get("systolic_bp"),
        diastolic_bp=patient_raw["cardio"].get("diastolic_bp"),
        is_smoker=patient_raw["cardio"].get("smoking_status") == "smoker",
        total_cholesterol_mmol_L=patient_raw["cardio"].get("total_cholesterol_mmol_l"),
        bmi=patient_raw["cardio"].get("bmi"),
        known_clinical_cvd=patient_raw["cardio"].get("known_clinical_cvd") == "yes",
        serum_creatinine_mg_dl=patient_raw["kidney"].get("serum_creatinine_mg_dl"),
        urine_acr_mg_g=patient_raw["kidney"].get("urine_acr_mg_g"),
        has_previous_stroke_or_tia=patient_raw["stroke"].get("prior_stroke_tia") == "yes",
        acute_stroke_type=patient_raw["stroke"].get("acute_stroke_type"),
        hours_since_stroke_onset=patient_raw["stroke"].get("hours_since_stroke_onset")
    )

    # 2. Run deterministic scoring engines
    print("\n" + "-" * 70)
    print("[Step 2] Running Deterministic Clinical Scoring Engines Locally...")
    print("-" * 70)
    
    # Run the engines
    structured_results = run_all_engines(p_data, is_newly_diagnosed_htn=newly_diagnosed_htn)
    
    clean_results = _clean_payload(structured_results)
    print("\n>>> RAW CLINICAL SCORES (CALCULATED DETERMINISTICALLY BY PYTHON):")
    print(json.dumps(clean_results, indent=2))

    # 3. Call LLM for translation/explanation
    target_language = "Gujarati"
    print("\n" + "-" * 70)
    print(f"[Step 3] Passing Raw JSON to LLM for Native script translation ({target_language})...")
    print("-" * 70)
    
    # Check if API Key is set
    provider_name = os.environ.get("LLM_PROVIDER", "nvidia").lower()
    env_key = "NVIDIA_API_KEY" if provider_name == "nvidia" else "OPENROUTER_API_KEY"
    api_key = os.environ.get(env_key)

    if not api_key:
        print(f"\n[Notice] {env_key} is not set in your .env file.")
        print("This demo runs the Python engines and outputs the raw JSON scores successfully,")
        print("but the AI translation layer is skipped. Set the API key to see the translation.")
        print("=" * 70)
        return

    # Call LLM orchestrator
    print("Calling LLM orchestrator...")
    orchestration_result = call_llm_orchestration(
        patient=p_data,
        language=target_language,
        is_newly_diagnosed_htn=newly_diagnosed_htn
    )

    print("\n>>> AI EXPLANATION & TRANSLATION (NATIVE SCRIPT):")
    print(orchestration_result["llm_explanation"])
    print("=" * 70)

if __name__ == "__main__":
    main()
