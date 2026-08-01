from typing import List, Dict

def determine_referral(engine_responses: Dict[str, 'EngineResponse']) -> dict:
    """
    Evaluates responses from all engines to determine if a referral is needed.
    """
    referral_needed = False
    reasons = []
    
    # 1. WHO CVD Engine
    cvd_resp = engine_responses.get("cvd")
    if cvd_resp and cvd_resp.referral_recommended:
        referral_needed = True
        reasons.append(cvd_resp.referral_reason)
        
    # 2. Hypertension Engine (Stage 2 or Acute Stroke)
    htn_resp = engine_responses.get("htn")
    if htn_resp and htn_resp.referral_recommended:
        referral_needed = True
        reasons.append(htn_resp.referral_reason)
        
    # 3. CKD Engine (G3b+ or A3)
    ckd_resp = engine_responses.get("ckd")
    if ckd_resp and ckd_resp.referral_recommended:
        referral_needed = True
        reasons.append(ckd_resp.referral_reason)
        
    # 4. IDRS Engine (High risk)
    idrs_resp = engine_responses.get("idrs")
    if idrs_resp and idrs_resp.referral_recommended:
        referral_needed = True
        reasons.append(idrs_resp.referral_reason)
        
    return {
        "referral_recommended": referral_needed,
        "reasons": reasons
    }
