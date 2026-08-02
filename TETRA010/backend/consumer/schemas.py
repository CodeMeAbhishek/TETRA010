"""
Consumer Tier data schemas.

Wraps every clinical field in an ExtractedField that carries provenance
(source, confidence, confirmation status) alongside the raw value.
The explainer layer can later use this metadata to distinguish
"we know this" from "we estimated this" in patient-facing output.
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal, Union, List
from backend.scoring.models import PatientData


# ── Core wrapper type ────────────────────────────────────────────────────────

class ExtractedField(BaseModel):
    """
    Every clinical datum the consumer tier handles is wrapped in this type
    so that provenance travels with the value all the way to the explainer.
    """
    value: Optional[Union[float, int, str, bool]] = None
    source: Literal[
        "user_stated",
        "inferred",
        "extracted_from_document",
        "null",
    ] = "null"
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="1.0 for user_stated; model-assigned for inferred/extracted; 0.0 for null",
    )
    requires_confirmation: bool = Field(
        default=False,
        description=(
            "True when a mandatory-for-an-engine field was populated via "
            "'inferred' or 'extracted_from_document' — must be confirmed "
            "before the field is used in scoring."
        ),
    )


# ── Conflict tracking ────────────────────────────────────────────────────────

class ConflictRecord(BaseModel):
    """Logged when a new extraction disagrees with an already-confirmed value."""
    field_name: str
    old_value: Optional[Union[float, int, str, bool]] = None
    old_source: str = "null"
    new_value: Optional[Union[float, int, str, bool]] = None
    new_source: str = "null"
    resolved: bool = False
    resolution: Optional[str] = None  # "kept_old" | "accepted_new" | "user_edited"


# ── Consumer intake payload ──────────────────────────────────────────────────

class ConsumerIntakePayload(BaseModel):
    """
    Mirrors PatientData minus the acute-stroke-only fields
    (has_previous_stroke_or_tia, acute_stroke_type, hours_since_stroke_onset)
    which are Clinician Tier only.

    Each field is an ExtractedField carrying provenance metadata.
    """
    # Demographics
    age: ExtractedField = Field(default_factory=ExtractedField)
    sex: ExtractedField = Field(default_factory=ExtractedField)

    # IDRS (Diabetes)
    waist_circumference_cm: ExtractedField = Field(default_factory=ExtractedField)
    physical_activity: ExtractedField = Field(default_factory=ExtractedField)
    family_history_diabetes: ExtractedField = Field(default_factory=ExtractedField)

    # CVD & Hypertension
    is_smoker: ExtractedField = Field(default_factory=ExtractedField)
    systolic_bp: ExtractedField = Field(default_factory=ExtractedField)
    diastolic_bp: ExtractedField = Field(default_factory=ExtractedField)
    total_cholesterol_mmol_L: ExtractedField = Field(default_factory=ExtractedField)
    bmi: ExtractedField = Field(default_factory=ExtractedField)
    has_diabetes: ExtractedField = Field(default_factory=ExtractedField)

    # CKD
    serum_creatinine_mg_dl: ExtractedField = Field(default_factory=ExtractedField)
    urine_acr_mg_g: ExtractedField = Field(default_factory=ExtractedField)

    # ASCVD risk (for HTN Stage 1 treatment decision)
    ascvd_10y_risk_percent: ExtractedField = Field(default_factory=ExtractedField)
    known_clinical_cvd: ExtractedField = Field(default_factory=ExtractedField)

    def _is_usable(self, ef: ExtractedField) -> bool:
        """A field is usable for scoring only if it has a value AND is confirmed."""
        if ef.value is None or ef.source == "null":
            return False
        if ef.requires_confirmation:
            return False
        return True

    def to_patient_data(self) -> PatientData:
        """
        Convert to the engine-facing PatientData dataclass.
        Only confirmed fields are passed through; unconfirmed fields become None.
        Stroke-only fields are always None (Consumer Tier excludes them).
        """
        def val_or_none(ef: ExtractedField):
            return ef.value if self._is_usable(ef) else None

        return PatientData(
            age=int(val_or_none(self.age)) if self._is_usable(self.age) else None,
            sex=val_or_none(self.sex),
            waist_circumference_cm=float(val_or_none(self.waist_circumference_cm)) if self._is_usable(self.waist_circumference_cm) else None,
            physical_activity=val_or_none(self.physical_activity),
            family_history_diabetes=val_or_none(self.family_history_diabetes),
            is_smoker=val_or_none(self.is_smoker),
            systolic_bp=int(val_or_none(self.systolic_bp)) if self._is_usable(self.systolic_bp) else None,
            diastolic_bp=int(val_or_none(self.diastolic_bp)) if self._is_usable(self.diastolic_bp) else None,
            total_cholesterol_mmol_L=float(val_or_none(self.total_cholesterol_mmol_L)) if self._is_usable(self.total_cholesterol_mmol_L) else None,
            bmi=float(val_or_none(self.bmi)) if self._is_usable(self.bmi) else None,
            has_diabetes=val_or_none(self.has_diabetes),
            serum_creatinine_mg_dl=float(val_or_none(self.serum_creatinine_mg_dl)) if self._is_usable(self.serum_creatinine_mg_dl) else None,
            urine_acr_mg_g=float(val_or_none(self.urine_acr_mg_g)) if self._is_usable(self.urine_acr_mg_g) else None,
            # Stroke-only fields — Consumer Tier never fills these
            has_previous_stroke_or_tia=None,
            acute_stroke_type=None,
            hours_since_stroke_onset=None,
            # ASCVD / CVD flags
            ascvd_10y_risk_percent=float(val_or_none(self.ascvd_10y_risk_percent)) if self._is_usable(self.ascvd_10y_risk_percent) else None,
            known_clinical_cvd=val_or_none(self.known_clinical_cvd),
        )


# ── API request/response models ─────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Request body for POST /consumer/chat."""
    conversation: List[dict] = Field(
        ...,
        description="OpenAI-style message list: [{role: 'user'|'assistant', content: str}]",
    )
    current_payload: Optional[ConsumerIntakePayload] = None


class ChatResponse(BaseModel):
    """Response body for POST /consumer/chat."""
    assistant_message: str
    updated_payload: ConsumerIntakePayload
    pending_confirmations: List[dict] = Field(default_factory=list)
    conflicts: List[ConflictRecord] = Field(default_factory=list)
    gap_summary: dict = Field(default_factory=dict)


class UploadReportResponse(BaseModel):
    """Response body for POST /consumer/upload-report."""
    extracted_fields: dict = Field(default_factory=dict)
    message: str = ""


class ConfirmFieldRequest(BaseModel):
    """Request body for POST /consumer/confirm-field."""
    field_name: str
    confirmed_value: Optional[Union[float, int, str, bool]] = None
    was_edited: bool = False
    current_payload: ConsumerIntakePayload


class ConfirmFieldResponse(BaseModel):
    """Response body for POST /consumer/confirm-field."""
    updated_field: ExtractedField
    updated_payload: ConsumerIntakePayload


class AssessRequest(BaseModel):
    """Request body for POST /consumer/assess."""
    payload: ConsumerIntakePayload
    language: str = "English"


class AssessResponse(BaseModel):
    """Response body for POST /consumer/assess."""
    structured_data: dict
    llm_explanation: str
    provenance: ConsumerIntakePayload
