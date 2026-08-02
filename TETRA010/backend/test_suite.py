import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.scoring.models import PatientData
from backend.scoring.engine_idrs import run_idrs_engine
from backend.scoring.engine_htn import run_htn_engine
from backend.scoring.engine_who_cvd import run_who_cvd_engine
from backend.scoring.engine_ckd import run_ckd_engine

def test_all_patients():
    data_path = os.path.join(os.path.dirname(__file__), "data", "synthetic_patients.json")
    if not os.path.exists(data_path):
        print(f"File not found: {data_path}")
        return

    with open(data_path, "r") as f:
        data = json.load(f)

    for i, p in enumerate(data.get("patients", [])):
        print(f"--- Running Patient {i+1}: {p['id']} ---")
        
        patient = PatientData(
            age=p["demographics"].get("age"),
            sex=p["demographics"].get("sex"),
            
            waist_circumference_cm=p["diabetes"].get("waist_circumference_cm"),
            physical_activity=p["diabetes"].get("physical_activity"),
            family_history_diabetes=p["diabetes"].get("family_history_diabetes"),
            has_diabetes=p["diabetes"].get("known_diabetes_diagnosis") == "yes",
            
            systolic_bp=p["cardio"].get("systolic_bp"),
            diastolic_bp=p["cardio"].get("diastolic_bp"),
            is_smoker=p["cardio"].get("smoking_status") == "smoker",
            total_cholesterol_mmol_L=p["cardio"].get("total_cholesterol_mmol_l"),
            bmi=p["cardio"].get("bmi"),
            known_clinical_cvd=p["cardio"].get("known_clinical_cvd") == "yes",
            
            serum_creatinine_mg_dl=p["kidney"].get("serum_creatinine_mg_dl"),
            urine_acr_mg_g=p["kidney"].get("urine_acr_mg_g"),
            
            has_previous_stroke_or_tia=p["stroke"].get("prior_stroke_tia") == "yes",
            acute_stroke_type=p["stroke"].get("acute_stroke_type", "none")
        )
        
        idrs_res = run_idrs_engine(patient)
        htn_res = run_htn_engine(patient)
        who_res = run_who_cvd_engine(patient)
        ckd_res = run_ckd_engine(patient, htn_category=htn_res.risk_category, idrs_category=idrs_res.risk_category)
        
        print(f"IDRS: {idrs_res.risk_category} | Score: {idrs_res.risk_score}")
        print(f"HTN: {htn_res.risk_category}")
        print(f"WHO CVD: {who_res.risk_category} ({who_res.extra_data.get('chart_used', 'N/A')})")
        print(f"CKD: {ckd_res.risk_category} | eGFR: {ckd_res.extra_data.get('eGFR', 'N/A')} G:{ckd_res.extra_data.get('G_stage', 'N/A')} A:{ckd_res.extra_data.get('A_stage', 'N/A')}")
        print("Expected Info:", p["expected"])
        print("\n")

if __name__ == "__main__":
    test_all_patients()
