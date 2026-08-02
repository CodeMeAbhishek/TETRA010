"""
Orchestrator: runs all deterministic scoring engines, then calls the LLM layer
(NVIDIA NIM or OpenRouter) for multilingual explanation.

Provider selection via environment variables:
  LLM_PROVIDER  = "nvidia"     → uses NVIDIA NIM (default)
                  "openrouter" → uses OpenRouter free tier

  NVIDIA_API_KEY      — from https://build.nvidia.com  (free credits on signup)
  OPENROUTER_API_KEY  — from https://openrouter.ai/keys (free, no card needed)
"""

import os
import json
from openai import OpenAI
from typing import Dict
from backend.scoring.models import PatientData, EngineResponse
from backend.scoring.engine_idrs import run_idrs_engine
from backend.scoring.engine_who_cvd import run_who_cvd_engine
from backend.scoring.engine_htn import run_htn_engine
from backend.scoring.engine_ckd import run_ckd_engine
from backend.scoring.missing_investigations import aggregate_missing_investigations
from backend.scoring.referral_engine import determine_referral


# ── Provider configuration ──────────────────────────────────────────────────
_PROVIDERS = {
    "nvidia": {
        "base_url": "https://integrate.api.nvidia.com/v1",
        "env_key":  "NVIDIA_API_KEY",
        "model":    "meta/llama-3.1-8b-instruct",   # 8B: lower latency on free NIM tier
    },
    "openrouter": {
        "base_url": "https://openrouter.ai/api/v1",
        "env_key":  "OPENROUTER_API_KEY",
        "model":    "meta-llama/llama-3.1-8b-instruct:free",
    },
}


def _get_client_and_model() -> tuple[OpenAI | None, str, str]:
    """
    Returns (client, model_name, provider_label).
    Returns (None, "", reason_string) if no key is configured.
    """
    provider_name = os.environ.get("LLM_PROVIDER", "nvidia").lower()
    config = _PROVIDERS.get(provider_name, _PROVIDERS["nvidia"])

    api_key = os.environ.get(config["env_key"])
    if not api_key:
        return None, "", (
            f"[LLM disabled — {config['env_key']} not set. "
            f"Set it in your .env file to enable {provider_name.upper()} explanations.]"
        )

    client = OpenAI(
        base_url=config["base_url"],
        api_key=api_key,
    )
    return client, config["model"], provider_name


# ── Deterministic engine pipeline ───────────────────────────────────────────
def run_all_engines(patient: PatientData, is_newly_diagnosed_htn: bool = False) -> Dict[str, dict]:
    """
    Runs all 4 deterministic scoring engines in dependency order.
    CKD uses HTN+IDRS categories; HTN is re-run once CKD G-stage is known
    so that cross-module BP targets are resolved correctly.
    The LLM never runs this code or calculates any value here.
    """
    idrs_resp = run_idrs_engine(patient)
    cvd_resp  = run_who_cvd_engine(patient)

    # First HTN pass — CKD stage unknown yet
    htn_resp = run_htn_engine(
        patient,
        is_newly_diagnosed=is_newly_diagnosed_htn,
        ckd_stage=None,
        ckd_acr=patient.urine_acr_mg_g,
    )

    # CKD run — uses HTN and IDRS categories for pre-test probability
    ckd_resp = run_ckd_engine(
        patient,
        htn_category=htn_resp.risk_category,
        idrs_category=idrs_resp.risk_category,
    )

    # Second HTN pass — resolve cross-module BP targets now that CKD stage is known
    ckd_g_stage = ckd_resp.extra_data.get("G_stage")
    if ckd_g_stage:
        htn_resp = run_htn_engine(
            patient,
            is_newly_diagnosed=is_newly_diagnosed_htn,
            ckd_stage=ckd_g_stage,
            ckd_acr=patient.urine_acr_mg_g,
        )

    engines = {
        "idrs": idrs_resp,
        "cvd":  cvd_resp,
        "htn":  htn_resp,
        "ckd":  ckd_resp,
    }

    missing  = aggregate_missing_investigations(list(engines.values()))
    referral = determine_referral(engines)

    return {
        "idrs_diabetes_risk": idrs_resp.__dict__,
        "who_cvd_risk":       cvd_resp.__dict__,
        "hypertension_risk":  htn_resp.__dict__,
        "ckd_kdigo_risk":     ckd_resp.__dict__,
        "missing_investigations": missing,
        "referral_decision":  referral,
    }


# ── Prompt builder ───────────────────────────────────────────────────────────
def _clean_payload(structured_data: dict) -> dict:
    """
    Builds a compact, clean dict the LLM prompt receives.
    Strips internal Python objects; keeps only what the model needs to explain.
    """
    def mi_to_dict(mi) -> dict:
        """MissingInvestigation dataclass → plain dict."""
        if hasattr(mi, 'test_name'):
            return {
                "test": mi.test_name,
                "reason": mi.reason,
                "source": mi.guideline_citation,
            }
        return mi  # already a dict (from aggregator)

    idrs = structured_data.get("idrs_diabetes_risk", {})
    htn  = structured_data.get("hypertension_risk", {})
    cvd  = structured_data.get("who_cvd_risk", {})
    ckd  = structured_data.get("ckd_kdigo_risk", {})
    ref  = structured_data.get("referral_decision", {})
    miss = structured_data.get("missing_investigations", [])

    return {
        "diabetes_idrs": {
            "score":    idrs.get("risk_score"),
            "category": idrs.get("risk_category"),
            "breakdown": {
                "age_pts":      idrs.get("extra_data", {}).get("age_pts"),
                "waist_pts":    idrs.get("extra_data", {}).get("waist_pts"),
                "activity_pts": idrs.get("extra_data", {}).get("activity_pts"),
                "family_pts":   idrs.get("extra_data", {}).get("family_pts"),
            },
        },
        "hypertension": {
            "category":   htn.get("risk_category"),
            "treatment":  htn.get("extra_data", {}).get("treatment_recommendation"),
            "reassess_in": htn.get("extra_data", {}).get("reassess_timeline"),
            "cross_module_targets": htn.get("extra_data", {}).get("cross_module_targets", []),
            "acute_stroke_action":  htn.get("extra_data", {}).get("acute_stroke_action"),
        },
        "cvd_10yr_risk": {
            "risk_percent": cvd.get("risk_percentage"),
            "chart_used":   cvd.get("extra_data", {}).get("chart_used"),
        },
        "ckd_kdigo": {
            "egfr":     ckd.get("extra_data", {}).get("eGFR"),
            "g_stage":  ckd.get("extra_data", {}).get("G_stage"),
            "a_stage":  ckd.get("extra_data", {}).get("A_stage"),
            "risk_color": ckd.get("risk_category"),
        },
        "missing_investigations": [
            mi_to_dict(m) for m in miss
        ],
        "referral": {
            "recommended": ref.get("referral_recommended", False),
            "reasons":     ref.get("reasons", []),
        },
    }


def _build_messages(structured_data: dict, language: str) -> list[dict]:
    """
    Returns an OpenAI-format messages list with system + user roles.
    Compatible with NVIDIA NIM and OpenRouter (both use OpenAI chat API format).
    """
    system_content = (
        "You are a medical explainer AI embedded in a clinical decision support tool. "
        "You are STRICTLY FORBIDDEN from calculating any clinical scores, diagnosing patients, "
        "or inventing risk numbers. Your ONLY job is to take the structured JSON provided — which "
        "contains deterministic risk scores computed by validated medical algorithms — and explain "
        "them clearly. "
        f"Respond entirely in the requested language: {language}. "
        "CRITICAL: You MUST write using the native script and native characters of the requested language "
        "(e.g., Gujarati script for Gujarati, Devanagari script for Hindi/Marathi, Tamil script for Tamil, "
        "Telugu script for Telugu, Kannada script for Kannada). "
        "DO NOT use Latin characters, Hinglish, or any transliterated representation. "
        "If a regional language is requested, ensure medical terms are explained in plain words a patient or village health worker can understand. "
        "Do not add any score values beyond what the JSON contains."
    )

    clean = _clean_payload(structured_data)

    user_content = f"""Clinical scoring results (JSON):
{json.dumps(clean, indent=2)}

Write your response with exactly these four sections:

1. **Patient-Friendly Summary** — What do these scores mean in plain language? Avoid jargon.
2. **Action Plan** — What specific lifestyle changes or next steps does the patient need?
3. **Missing Investigations** — For each item in missing_investigations, state the test name and WHY it is needed, citing the source field.
4. **Referral Note** — If referral.recommended is true, write a short clinical referral note citing each reason verbatim. If false, write "No referral required at this time."
"""

    return [
        {"role": "system", "content": system_content},
        {"role": "user",   "content": user_content},
    ]



# ── Public entry point ───────────────────────────────────────────────────────
def call_llm_orchestration(
    patient: PatientData,
    language: str = "English",
    is_newly_diagnosed_htn: bool = False,
) -> dict:
    """
    Entry point called by the API layer.
    Returns {"structured_data": {...}, "llm_explanation": "..."}.
    """
    structured_data = run_all_engines(patient, is_newly_diagnosed_htn=is_newly_diagnosed_htn)
    client, model, status = _get_client_and_model()

    if client is None:
        # status is the disabled-message string in this case
        return {"structured_data": structured_data, "llm_explanation": status}

    messages = _build_messages(structured_data, language)

    completion = client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=2048,
        temperature=0.3,  # Low temperature for consistent medical explanation
    )

    llm_text = completion.choices[0].message.content or ""
    return {
        "structured_data":  structured_data,
        "llm_explanation":  llm_text,
    }
