"""
FastAPI REST layer for the Nidan clinical decision support backend.
Single endpoint: POST /analyze
Accepts PatientData-compatible JSON, returns structured clinical scores + LLM explanation.
"""

import os
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typing import Optional

load_dotenv()  # loads ANTHROPIC_API_KEY from .env if present

from backend.scoring.models import PatientData
from backend.orchestrator import call_llm_orchestration

app = FastAPI(
    title="Nidan — Clinical Decision Support API",
    description=(
        "Deterministic rule-based risk scoring for Diabetes (IDRS), Cardiovascular Disease "
        "(WHO-CVD South Asia), Hypertension (2017 ACC/AHA), and CKD (KDIGO). "
        "LLM layer provides multilingual explanation only — never computes scores."
    ),
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production; open for hackathon demo
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    """
    Mirror of PatientData dataclass as a Pydantic model so FastAPI can validate + document it.
    All fields are optional — engines handle graceful degradation internally.
    """
    # Demographics
    age: Optional[int] = Field(None, ge=1, le=120, description="Patient age in years")
    sex: Optional[str] = Field(None, pattern="^(male|female)$", description="'male' or 'female'")

    # IDRS (Diabetes)
    waist_circumference_cm: Optional[float] = Field(None, gt=0, description="Waist circumference in cm")
    physical_activity: Optional[str] = Field(
        None,
        pattern="^(vigorous|moderate|mild|sedentary)$",
        description="'vigorous', 'moderate', 'mild', or 'sedentary'"
    )
    family_history_diabetes: Optional[str] = Field(
        None,
        pattern="^(none|one_parent|both_parents)$",
        description="'none', 'one_parent', or 'both_parents'"
    )

    # CVD & Hypertension
    is_smoker: Optional[bool] = None
    systolic_bp: Optional[int] = Field(None, ge=40, le=300, description="Systolic BP in mm Hg")
    diastolic_bp: Optional[int] = Field(None, ge=20, le=200, description="Diastolic BP in mm Hg")
    total_cholesterol_mmol_L: Optional[float] = Field(None, gt=0, description="Total cholesterol in mmol/L")
    bmi: Optional[float] = Field(None, gt=0, description="BMI in kg/m²")
    has_diabetes: Optional[bool] = Field(None, description="Known diabetes diagnosis")

    # CKD
    serum_creatinine_mg_dl: Optional[float] = Field(None, gt=0, description="Serum creatinine in mg/dL")
    urine_acr_mg_g: Optional[float] = Field(None, ge=0, description="Urine albumin-creatinine ratio in mg/g")

    # Stroke
    has_previous_stroke_or_tia: Optional[bool] = None
    acute_stroke_type: Optional[str] = Field(
        None,
        pattern="^(ich|ischemic_tpa_eligible|ischemic_not_tpa_eligible)$",
        description="Acute stroke type if applicable"
    )
    hours_since_stroke_onset: Optional[float] = Field(None, ge=0)

    # ASCVD risk (for HTN Stage 1 treatment decision)
    ascvd_10y_risk_percent: Optional[float] = Field(None, ge=0, le=100)
    known_clinical_cvd: Optional[bool] = None

    # Request options
    language: str = Field("English", description="Language for LLM explanation")
    is_newly_diagnosed_htn: bool = Field(
        False,
        description="Set True to trigger the full ACC/AHA basic testing panel for newly diagnosed HTN"
    )


@app.get("/health")
def health_check():
    return {"status": "ok", "service": "Nidan Clinical Decision Support API"}


@app.post("/analyze")
def analyze_patient(request: AnalyzeRequest):
    """
    Core endpoint. Accepts patient data, runs all scoring engines deterministically,
    then calls the LLM layer (if API key is set) for multilingual explanation.

    Returns:
      - structured_data: raw engine outputs (scores, categories, missing investigations, referral decision)
      - llm_explanation: plain-language explanation from Claude
    """
    try:
        patient = PatientData(
            age=request.age,
            sex=request.sex,
            waist_circumference_cm=request.waist_circumference_cm,
            physical_activity=request.physical_activity,
            family_history_diabetes=request.family_history_diabetes,
            is_smoker=request.is_smoker,
            systolic_bp=request.systolic_bp,
            diastolic_bp=request.diastolic_bp,
            total_cholesterol_mmol_L=request.total_cholesterol_mmol_L,
            bmi=request.bmi,
            has_diabetes=request.has_diabetes,
            serum_creatinine_mg_dl=request.serum_creatinine_mg_dl,
            urine_acr_mg_g=request.urine_acr_mg_g,
            has_previous_stroke_or_tia=request.has_previous_stroke_or_tia,
            acute_stroke_type=request.acute_stroke_type,
            hours_since_stroke_onset=request.hours_since_stroke_onset,
            ascvd_10y_risk_percent=request.ascvd_10y_risk_percent,
            known_clinical_cvd=request.known_clinical_cvd,
        )

        result = call_llm_orchestration(
            patient=patient,
            language=request.language,
            is_newly_diagnosed_htn=request.is_newly_diagnosed_htn,
        )
        return result

    except Exception as exc:
        # Surface the error clearly — never silently swallow in a clinical tool
        raise HTTPException(status_code=500, detail=str(exc))

# ── Consumer Tier router (must be registered BEFORE the catch-all static mount) ──
from backend.consumer.router import consumer_router
app.include_router(consumer_router)

# Serve the frontend statically so users can access the app at http://localhost:8000/
frontend_path = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

