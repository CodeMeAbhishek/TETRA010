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

    score = 0
    
    # Age score
    if patient.age < 35:
        score += 0
    elif 35 <= patient.age <= 49:
        score += 20
    else:
        score += 30
        
    # Waist score
    waist = patient.waist_circumference_cm
    if patient.sex == "female":
        if waist < 80: score += 0
        elif 80 <= waist <= 89: score += 10
        else: score += 20
    elif patient.sex == "male":
        if waist < 90: score += 0
        elif 90 <= waist <= 99: score += 10
        else: score += 20
        
    # Activity score
    act = patient.physical_activity.lower()
    if act == "vigorous": score += 0
    elif act == "moderate": score += 10
    elif act == "mild": score += 20
    elif act == "sedentary": score += 30
    
    # Family history score
    fam = patient.family_history_diabetes.lower()
    if fam == "none": score += 0
    elif fam == "one_parent": score += 10
    elif fam == "both_parents": score += 20
    
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
        
    response.extra_data["age_pts"] = score # Note: we could store individual points if requested by LLM payload
    
    return response
