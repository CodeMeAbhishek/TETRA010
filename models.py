from dataclasses import dataclass, field
from typing import Optional, List

@dataclass
class MissingInvestigation:
    test_name: str
    reason: str
    guideline_citation: str

@dataclass
class EngineResponse:
    risk_score: Optional[int] = None
    risk_category: Optional[str] = None
    risk_percentage: Optional[str] = None
    missing_inputs: List[MissingInvestigation] = field(default_factory=list)
    referral_recommended: bool = False
    referral_reason: Optional[str] = None
    extra_data: dict = field(default_factory=dict)

@dataclass
class PatientData:
    age: Optional[int] = None
    sex: Optional[str] = None  # "male", "female"
    
    # IDRS Specific
    waist_circumference_cm: Optional[float] = None
    physical_activity: Optional[str] = None # "vigorous", "moderate", "mild", "sedentary"
    family_history_diabetes: Optional[str] = None # "none", "one_parent", "both_parents"
    
    # CVD & Hypertension Specific
    is_smoker: Optional[bool] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    total_cholesterol_mmol_L: Optional[float] = None
    bmi: Optional[float] = None
    has_diabetes: Optional[bool] = None # Known diagnosis or IDRS High
    
    # CKD Specific
    serum_creatinine_mg_dl: Optional[float] = None
    urine_acr_mg_g: Optional[float] = None
    
    # Stroke specifics
    has_previous_stroke_or_tia: Optional[bool] = None
    acute_stroke_type: Optional[str] = None # "ich", "ischemic_tpa_eligible", "ischemic_not_tpa_eligible", None
    hours_since_stroke_onset: Optional[float] = None
    
    # ASCVD Risk for BP treatment
    ascvd_10y_risk_percent: Optional[float] = None
    known_clinical_cvd: Optional[bool] = None
