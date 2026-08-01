import json
import os
from backend.scoring.models import PatientData, EngineResponse, MissingInvestigation

def load_kdigo_grid() -> dict:
    grid_path = os.path.join(os.path.dirname(__file__), "kdigo_ckd_grid.json")
    with open(grid_path, "r") as f:
        return json.load(f)

KDIGO_GRID = load_kdigo_grid()

def calculate_egfr(scr: float, age: int, sex: str) -> float:
    k = 0.7 if sex == "female" else 0.9
    a = -0.241 if sex == "female" else -0.302
    ratio = scr / k
    egfr = 142 * (min(ratio, 1) ** a) * (max(ratio, 1) ** -1.200) * (0.9938 ** age)
    if sex == "female":
        egfr *= 1.012
    return egfr

def get_g_stage(egfr: float) -> str:
    if egfr >= 90: return "G1"
    if 60 <= egfr <= 89: return "G2"
    if 45 <= egfr <= 59: return "G3a"
    if 30 <= egfr <= 44: return "G3b"
    if 15 <= egfr <= 29: return "G4"
    return "G5"

def get_a_stage(acr: float) -> str:
    if acr < 30: return "A1"
    if 30 <= acr <= 300: return "A2"
    return "A3"

def get_kdigo_risk(g_stage: str, a_stage: str) -> str:
    return KDIGO_GRID.get(g_stage, {}).get(a_stage, "Unknown")

def run_ckd_engine(patient: PatientData, htn_category: str = None, idrs_category: str = None) -> EngineResponse:
    response = EngineResponse()
    
    scr = patient.serum_creatinine_mg_dl
    acr = patient.urine_acr_mg_g
    age = patient.age
    sex = patient.sex
    
    # 1. Both available
    if scr is not None and acr is not None and age is not None and sex in ["male", "female"]:
        egfr = calculate_egfr(scr, age, sex)
        g_stage = get_g_stage(egfr)
        a_stage = get_a_stage(acr)
        risk_color = get_kdigo_risk(g_stage, a_stage)
        
        response.extra_data["eGFR"] = egfr
        response.extra_data["G_stage"] = g_stage
        response.extra_data["A_stage"] = a_stage
        response.risk_category = risk_color
        
        if risk_color == "Red" or g_stage in ["G3b", "G4", "G5"] or a_stage == "A3":
            response.referral_recommended = True
            response.referral_reason = f"KDIGO risk is {risk_color} (G-stage: {g_stage}, A-stage: {a_stage})."
            
    # 2. Creatinine only
    elif scr is not None and age is not None and sex in ["male", "female"]:
        egfr = calculate_egfr(scr, age, sex)
        g_stage = get_g_stage(egfr)
        
        response.extra_data["eGFR"] = egfr
        response.extra_data["G_stage"] = g_stage
        response.missing_inputs.append(MissingInvestigation(
            "Urine ACR",
            "Urine ACR not available - recommend to complete KDIGO risk grid.",
            "KDIGO CKD Guidelines"
        ))
        
        if g_stage in ["G3b", "G4", "G5"]:
            response.referral_recommended = True
            response.referral_reason = f"KDIGO G-stage is {g_stage} (High risk)."

    # 3. Neither available (or missing basic demographics)
    else:
        # Check pre-test probability
        # Criteria: Diabetes (IDRS Mod/High or known) AND HTN (Stage 1+) AND Age >= 50 AND/OR Fam Hist
        has_diabetes = patient.has_diabetes or idrs_category in ["Moderate Risk", "High Risk"]
        has_htn = htn_category in ["Stage 1 Hypertension", "Stage 2 Hypertension"]
        age_risk = (patient.age and patient.age >= 50)
        fam_risk = (patient.family_history_diabetes in ["one_parent", "both_parents"])
        
        if has_diabetes and has_htn and (age_risk or fam_risk):
            response.missing_inputs.append(MissingInvestigation(
                "Serum Creatinine (eGFR) and Urine ACR",
                "High pre-test probability for CKD — recommend serum creatinine (eGFR) + urine ACR.",
                "KDIGO CKD Guidelines"
            ))
        elif has_diabetes or has_htn:
            response.missing_inputs.append(MissingInvestigation(
                "Serum Creatinine (eGFR) and Urine ACR",
                "Moderate pre-test probability for CKD — recommend testing to establish baseline.",
                "KDIGO CKD Guidelines"
            ))
            
    return response
