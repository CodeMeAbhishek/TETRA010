from models import PatientData, EngineResponse, MissingInvestigation

def run_htn_engine(patient: PatientData, is_newly_diagnosed: bool = False, ckd_stage: str = None, ckd_acr: float = None) -> EngineResponse:
    response = EngineResponse()
    
    if patient.systolic_bp is None or patient.diastolic_bp is None:
        response.missing_inputs.append(MissingInvestigation(
            "Blood Pressure", "Required for HTN category assessment", "2017 ACC/AHA"
        ))
        return response
        
    sbp = patient.systolic_bp
    dbp = patient.diastolic_bp
    
    # 1. Categorization (Higher wins)
    cat = "Normal BP"
    if sbp >= 140 or dbp >= 90:
        cat = "Stage 2 Hypertension"
    elif (130 <= sbp <= 139) or (80 <= dbp <= 89):
        cat = "Stage 1 Hypertension"
    elif (120 <= sbp <= 129) and dbp < 80:
        cat = "Elevated BP"
    elif sbp < 120 and dbp < 80:
        cat = "Normal BP"
        
    response.risk_category = cat
    
    # Acute Stroke BP logic
    if patient.acute_stroke_type:
        handle_acute_stroke(patient, response, sbp, dbp)
        return response # Acute stroke logic supersedes regular outpatient treatment logic
        
    # 2. Treatment Decision Logic
    treatment = ""
    reassess = ""
    
    if cat == "Normal BP":
        treatment = "Promote optimal lifestyle habits"
        reassess = "1 year"
    elif cat == "Elevated BP":
        treatment = "Initiate nonpharmacological therapy (lifestyle changes)"
        reassess = "3-6 months"
    elif cat == "Stage 1 Hypertension":
        risk_high = (patient.ascvd_10y_risk_percent and patient.ascvd_10y_risk_percent >= 10.0) or patient.known_clinical_cvd
        if risk_high:
            treatment = "Initiate nonpharmacological therapy AND BP-lowering medication"
            reassess = "1 month"
        else:
            treatment = "Initiate nonpharmacological therapy (lifestyle changes)"
            reassess = "3-6 months"
    elif cat == "Stage 2 Hypertension":
        treatment = "Promptly initiate nonpharmacological therapy AND BP-lowering medication (2 agents of different classes)"
        reassess = "1 month"
        response.referral_recommended = True
        response.referral_reason = "Stage 2 Hypertension requires immediate multi-agent medical management."
        
    response.extra_data["treatment_recommendation"] = treatment
    response.extra_data["reassess_timeline"] = reassess
    
    # Missing Investigations for newly diagnosed
    if is_newly_diagnosed and cat in ["Stage 1 Hypertension", "Stage 2 Hypertension"]:
        tests = [
            "Fasting blood glucose", "Complete blood count (CBC)", "Lipid profile", 
            "Serum creatinine with eGFR", "Serum sodium, potassium, and calcium", 
            "Thyroid-stimulating hormone (TSH)", "Urinalysis", "Electrocardiogram (ECG)"
        ]
        for t in tests:
            response.missing_inputs.append(MissingInvestigation(
                test_name=t,
                reason="Basic testing panel for newly diagnosed hypertension to evaluate cardiovascular risk and secondary causes.",
                guideline_citation="2017 ACC/AHA"
            ))
            
    # Cross-Module Targets
    targets = []
    if ckd_stage in ["G3a", "G3b", "G4", "G5"] or (ckd_stage in ["G1", "G2"] and ckd_acr and ckd_acr >= 300):
        targets.append("Target <130/80 mm Hg, first-line ACEi/ARB (CKD present)")
    if patient.has_diabetes:
        targets.append("Target <130/80 mm Hg, first-line thiazide/ACEi/ARB/CCB (Diabetes present)")
    if patient.has_previous_stroke_or_tia:
        targets.append("Target <130/80 mm Hg, first-line thiazide + ACEi/ARB combo (Secondary stroke prevention)")
        
    if targets:
        response.extra_data["cross_module_targets"] = targets
        
    return response

def handle_acute_stroke(patient, response, sbp, dbp):
    stroke_type = patient.acute_stroke_type
    response.extra_data["acute_care_flag"] = True
    
    if stroke_type == "ich":
        if sbp > 220:
            response.extra_data["acute_stroke_action"] = "Continuous IV drug infusion and close BP monitoring."
        elif 150 <= sbp <= 220 and patient.hours_since_stroke_onset and patient.hours_since_stroke_onset <= 6:
            response.extra_data["acute_stroke_action"] = "FLAG: Do NOT recommend immediate lowering of SBP to <140 mm Hg (potentially harmful)."
    elif stroke_type == "ischemic_tpa_eligible":
        response.extra_data["acute_stroke_action"] = "Lower BP to <185/110 mm Hg BEFORE tPA. Maintain <180/105 mm Hg for 24h after."
    elif stroke_type == "ischemic_not_tpa_eligible":
        if sbp >= 220 or dbp >= 120:
            response.extra_data["acute_stroke_action"] = "May reasonably lower BP by ~15% in first 24h."
        else:
            response.extra_data["acute_stroke_action"] = "Withhold new antihypertensives for 48-72h."
    
    response.referral_recommended = True
    response.referral_reason = "Acute stroke protocol activated. Requires immediate acute-care."
