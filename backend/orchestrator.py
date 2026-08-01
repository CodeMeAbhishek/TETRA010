import json
from typing import Dict, List
from backend.scoring.models import PatientData, EngineResponse
from backend.scoring.engine_idrs import run_idrs_engine
from backend.scoring.engine_who_cvd import run_who_cvd_engine
from backend.scoring.engine_htn import run_htn_engine
from backend.scoring.engine_ckd import run_ckd_engine
from backend.scoring.missing_investigations import aggregate_missing_investigations
from backend.scoring.referral_engine import determine_referral

def run_all_engines(patient: PatientData, is_newly_diagnosed_htn: bool = False) -> Dict[str, dict]:
    """
    Runs all 4 deterministic scoring engines safely and structuredly.
    The LLM never runs this code or calculates these values directly.
    """
    idrs_resp = run_idrs_engine(patient)
    cvd_resp = run_who_cvd_engine(patient)
    htn_resp = run_htn_engine(patient, is_newly_diagnosed=is_newly_diagnosed_htn, 
                              ckd_stage=None, # In a real graph, we run CKD first to pass here
                              ckd_acr=patient.urine_acr_mg_g)
                              
    ckd_resp = run_ckd_engine(patient, htn_category=htn_resp.risk_category, idrs_category=idrs_resp.risk_category)
    
    # Rerun HTN if CKD gave us a stage, just to resolve cross-module targets accurately
    if ckd_resp.extra_data.get("G_stage"):
        htn_resp = run_htn_engine(patient, is_newly_diagnosed=is_newly_diagnosed_htn, 
                                  ckd_stage=ckd_resp.extra_data.get("G_stage"), 
                                  ckd_acr=patient.urine_acr_mg_g)
                                  
    engines = {
        "idrs": idrs_resp,
        "cvd": cvd_resp,
        "htn": htn_resp,
        "ckd": ckd_resp
    }
    
    # Shared Services
    missing = aggregate_missing_investigations(list(engines.values()))
    referral = determine_referral(engines)
    
    # Serialize structure
    structured_output = {
        "idrs_diabetes_risk": idrs_resp.__dict__,
        "who_cvd_risk": cvd_resp.__dict__,
        "hypertension_risk": htn_resp.__dict__,
        "ckd_kdigo_risk": ckd_resp.__dict__,
        "missing_investigations": missing,
        "referral_decision": referral
    }
    return structured_output

def generate_llm_prompts(structured_data: dict, language: str = "English") -> str:
    """
    Creates the prompt for the Claude API based STRICTLY on the deterministic JSON.
    """
    
    system_prompt = (
        "You are a medical explainer AI. You are strictly forbidden from calculating "
        "any clinical scores, diagnosing, or inventing risk numbers. Your ONLY job is "
        "to take the provided structured JSON containing deterministic risk scores, "
        "missing investigations, and referral decisions, and explain them in plain language. "
        f"Respond in {language}. If a regional language like Hindi/Gujarati is chosen, "
        "ensure medical terms are easily understood by a patient or health worker."
    )
    
    user_prompt = f"""
    Please explain the following clinical scoring results to the patient and health worker, 
    and draft a referral note if a referral is recommended.
    
    Structured Clinical Data:
    {json.dumps(structured_data, indent=2, default=str)}
    
    Required Sections in your response:
    1. Patient-Friendly Explanation: What do these scores mean?
    2. Action Plan: What lifestyle changes or next steps are needed based on the treatment recommendations?
    3. Missing Investigations: A clear list of tests needed, explaining WHY based on the provided guideline citations.
    4. Referral Note: If referral_decision.referral_recommended is true, draft a short clinical referral note to a specialist, citing the specific reasons provided.
    """
    
    return system_prompt + "\n\n---\n\n" + user_prompt

# Mock LLM API call
def call_llm_orchestration(patient: PatientData, language: str = "Hindi") -> str:
    structured_data = run_all_engines(patient)
    
    prompt = generate_llm_prompts(structured_data, language)
    
    # In a real system, you would do:
    # response = anthropic_client.messages.create(
    #     model="claude-3-opus-20240229",
    #     system=system_prompt,
    #     messages=[{"role": "user", "content": user_prompt}]
    # )
    # return response.content
    
    return "LLM Prompt successfully generated. Waiting for API integration."
