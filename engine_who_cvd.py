import json
import os
from models import PatientData, EngineResponse, MissingInvestigation

def load_who_cvd_charts() -> dict:
    chart_path = os.path.join(os.path.dirname(__file__), "who_cvd_charts.json")
    with open(chart_path, "r") as f:
        return json.load(f)

CHARTS = load_who_cvd_charts()

def get_age_band(age: int) -> str:
    if age < 40:
        return None # WHO charts start at 40
    elif 40 <= age <= 44: return "40-44"
    elif 45 <= age <= 49: return "45-49"
    elif 50 <= age <= 54: return "50-54"
    elif 55 <= age <= 59: return "55-59"
    elif 60 <= age <= 64: return "60-64"
    elif 65 <= age <= 69: return "65-69"
    else: return "70-74"

def get_sbp_band(sbp: int) -> str:
    if sbp < 120: return "<120"
    elif 120 <= sbp <= 139: return "120-139"
    elif 140 <= sbp <= 159: return "140-159"
    elif 160 <= sbp <= 179: return "160-179"
    else: return ">=180"

def get_chol_band(chol: float) -> str:
    if chol < 4.0: return "<4"
    if chol < 5.0: return "4-4.9"
    if chol < 6.0: return "5-5.9"
    if chol < 7.0: return "6-6.9"
    return ">=7"

def get_bmi_band(bmi: float) -> str:
    if bmi < 20: return "<20"
    if bmi < 25: return "20-24"
    if bmi < 30: return "25-29"
    if bmi < 35: return "30-34"
    return ">=35"

def run_who_cvd_engine(patient: PatientData) -> EngineResponse:
    response = EngineResponse()
    
    # Required inputs for either chart
    missing = []
    if patient.age is None:
        missing.append(MissingInvestigation("Age", "Required for WHO CVD risk calculation", "WHO CVD Guidelines"))
    if patient.sex not in ["male", "female"]:
        missing.append(MissingInvestigation("Sex", "Required for WHO CVD risk calculation", "WHO CVD Guidelines"))
    if patient.is_smoker is None:
        missing.append(MissingInvestigation("Smoking Status", "Required for WHO CVD risk calculation", "WHO CVD Guidelines"))
    if patient.systolic_bp is None:
        missing.append(MissingInvestigation("Systolic BP", "Required for WHO CVD risk calculation", "WHO CVD Guidelines"))
    if patient.has_diabetes is None:
        missing.append(MissingInvestigation("Diabetes Status", "Required for WHO CVD risk calculation", "WHO CVD Guidelines"))
        
    if missing:
        response.missing_inputs.extend(missing)
        return response
        
    if patient.age < 40:
        response.extra_data["message"] = "Patient is under 40; WHO CVD risk charts are generally for age >= 40."
        return response

    age_band = get_age_band(patient.age)
    sbp_band = get_sbp_band(patient.systolic_bp)
    diabetes_key = "diabetes_yes" if patient.has_diabetes else "diabetes_no"
    smoker_key = "smoker" if patient.is_smoker else "non_smoker"
    sex_key = patient.sex
    
    # Decide which chart
    if patient.total_cholesterol_mmol_L is not None:
        chart_type = "lab_based"
        chol_band = get_chol_band(patient.total_cholesterol_mmol_L)
        try:
            risk = CHARTS["lab_based"][diabetes_key][sex_key][smoker_key][age_band][sbp_band][chol_band]
            response.risk_percentage = risk
            response.extra_data["chart_used"] = "lab_based"
        except KeyError:
            response.extra_data["error"] = "Error looking up lab-based risk."
    elif patient.bmi is not None:
        chart_type = "non_lab_based"
        bmi_band = get_bmi_band(patient.bmi)
        try:
            risk = CHARTS["non_lab_based"][diabetes_key][sex_key][smoker_key][age_band][sbp_band][bmi_band]
            response.risk_percentage = risk
            response.extra_data["chart_used"] = "non_lab_based"
        except KeyError:
            response.extra_data["error"] = "Error looking up non-lab-based risk."
    else:
        response.missing_inputs.append(MissingInvestigation(
            "Lipid Panel or BMI", 
            "BMI or lipid panel required to calculate WHO CVD Risk", 
            "WHO CVD Guidelines"
        ))
        
    if response.risk_percentage:
        try:
            risk_val = int(response.risk_percentage.replace("%", ""))
            if risk_val >= 20:
                response.referral_recommended = True
                response.referral_reason = f"WHO CVD risk is {response.risk_percentage} (Threshold >=20%)"
        except ValueError:
            pass
            
    return response
