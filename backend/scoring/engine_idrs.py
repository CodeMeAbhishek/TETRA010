from backend.scoring.models import PatientData, EngineResponse, MissingInvestigation

def run_idrs_engine(patient: PatientData) -> EngineResponse:
    response = EngineResponse()
    missing = []
    
    if patient.age is None:
        missing.append("Age")
    if patient.sex is None:
        missing.append("Sex")
    if patient.waist_circumference_cm is None:
        missing.append("Waist Circumference")
    if patient.physical_activity is None:
        missing.append("Physical Activity")
    if patient.family_history_diabetes is None:
        missing.append("Family History of Diabetes")
        
    if missing:
        response.extra_data["error"] = f"Missing mandatory IDRS inputs: {', '.join(missing)}"
        if "Waist Circumference" in missing:
            # Waist circumference is strictly mandatory field
            response.missing_inputs.append(MissingInvestigation(
                test_name="Waist Circumference",
                reason="Waist circumference is a strictly mandatory field for IDRS (Asian Indian phenotype).",
                guideline_citation="ICMR-INDIAB / MDRF-IDRS"
            ))
        return response

    # --- Compute each component's points independently ---
    age_pts = 0
    if patient.age < 35:
        age_pts = 0
    elif 35 <= patient.age <= 49:
        age_pts = 20
    else:
        age_pts = 30

    waist = patient.waist_circumference_cm
    waist_pts = 0
    if patient.sex == "female":
        if waist < 80:
            waist_pts = 0
        elif 80 <= waist <= 89:
            waist_pts = 10
        else:
            waist_pts = 20
    elif patient.sex == "male":
        if waist < 90:
            waist_pts = 0
        elif 90 <= waist <= 99:
            waist_pts = 10
        else:
            waist_pts = 20

    act = patient.physical_activity.lower()
    activity_pts = 0
    if act == "vigorous":
        activity_pts = 0
    elif act == "moderate":
        activity_pts = 10
    elif act == "mild":
        activity_pts = 20
    elif act == "sedentary":
        activity_pts = 30

    fam = patient.family_history_diabetes.lower()
    family_pts = 0
    if fam == "none":
        family_pts = 0
    elif fam == "one_parent":
        family_pts = 10
    elif fam == "both_parents":
        family_pts = 20

    score = age_pts + waist_pts + activity_pts + family_pts
    response.risk_score = score

    # Risk Category
    if score < 30:
        response.risk_category = "Low Risk"
    elif 30 <= score <= 50:
        response.risk_category = "Moderate Risk"
    else:
        response.risk_category = "High Risk"
        response.referral_recommended = True
        response.referral_reason = "IDRS High Risk (>=60) requires referral if no prior diagnosis."

    if response.risk_category in ["Moderate Risk", "High Risk"]:
        response.missing_inputs.append(MissingInvestigation(
            test_name="Fasting Capillary Blood Glucose and/or OGTT",
            reason=f"IDRS score is {score} ({response.risk_category}), indicating need for definitive glucose test.",
            guideline_citation="ICMR-INDIAB / MDRF-IDRS"
        ))

    # Correct per-component breakdown for LLM explainability payload
    response.extra_data["age_pts"] = age_pts
    response.extra_data["waist_pts"] = waist_pts
    response.extra_data["activity_pts"] = activity_pts
    response.extra_data["family_pts"] = family_pts
    response.extra_data["total"] = score

    return response
