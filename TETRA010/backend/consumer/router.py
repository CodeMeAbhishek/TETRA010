"""
Consumer Tier API router.

Provides four endpoints under /consumer:
  POST /consumer/chat           — conversational intake
  POST /consumer/upload-report  — lab report image extraction
  POST /consumer/confirm-field  — confirm/edit an extracted value
  POST /consumer/assess         — run engines + explainer

All scoring goes through the existing engines in backend/scoring/.
This router never computes a clinical score itself.
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, UploadFile, HTTPException
from backend.consumer.schemas import (
    ConsumerIntakePayload,
    ExtractedField,
    ConflictRecord,
    ChatRequest,
    ChatResponse,
    UploadReportResponse,
    ConfirmFieldRequest,
    ConfirmFieldResponse,
    AssessRequest,
    AssessResponse,
)
from backend.consumer.parser import parse_conversation, generate_assistant_response
from backend.consumer.gap_analysis import analyze_gaps, get_followup_questions
from backend.consumer.document_extraction import extract_from_document

from backend.scoring.models import PatientData
from backend.scoring.engine_idrs import run_idrs_engine
from backend.scoring.engine_who_cvd import run_who_cvd_engine
from backend.scoring.engine_htn import run_htn_engine
from backend.scoring.engine_ckd import run_ckd_engine
from backend.scoring.missing_investigations import aggregate_missing_investigations
from backend.scoring.referral_engine import determine_referral
from backend.orchestrator import _get_client_and_model, _build_messages

logger = logging.getLogger(__name__)

consumer_router = APIRouter(prefix="/consumer", tags=["Consumer Tier"])


# ── POST /consumer/chat ─────────────────────────────────────────────────────

@consumer_router.post("/chat", response_model=ChatResponse)
def consumer_chat(request: ChatRequest):
    """
    Accept a conversation turn, extract patient data, run gap analysis,
    and return an assistant response with any pending verification prompts.
    """
    payload = request.current_payload or ConsumerIntakePayload()

    # 1. Parse the conversation to extract structured fields
    updated_payload, conflicts, implausible = parse_conversation(
        conversation=request.conversation,
        existing_payload=payload,
    )

    # 2. Identify fields needing confirmation
    pending_confirmations = _get_pending_confirmations(updated_payload)

    # 3. Run gap analysis
    gap_summary = analyze_gaps(updated_payload)

    # 4. Generate assistant response
    assistant_message = generate_assistant_response(
        conversation=request.conversation,
        payload=updated_payload,
        gap_summary=gap_summary,
        pending_confirmations=pending_confirmations,
        implausible_extractions=implausible,
    )

    return ChatResponse(
        assistant_message=assistant_message,
        updated_payload=updated_payload,
        pending_confirmations=pending_confirmations,
        conflicts=conflicts,
        gap_summary=gap_summary,
    )


# ── POST /consumer/upload-report ────────────────────────────────────────────

@consumer_router.post("/upload-report", response_model=UploadReportResponse)
async def upload_report(file: UploadFile = File(...)):
    """
    Accept an image of a lab report, run document extraction,
    and return extracted fields as pending verification cards.

    Extracted values are NOT applied to the payload yet — the user
    must confirm each one via /consumer/confirm-field first.
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail="Only image files are accepted (JPEG, PNG, etc.).",
        )

    image_bytes = await file.read()
    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="Empty file uploaded.")

    extraction_result = extract_from_document(image_bytes)

    # Convert raw extraction to ExtractedField format
    # All document-extracted fields require confirmation (safety rule #3)
    extracted_fields = {}
    for field_name, field_data in extraction_result.get("fields", {}).items():
        extracted_fields[field_name] = ExtractedField(
            value=field_data.get("value"),
            source="extracted_from_document",
            confidence=field_data.get("confidence", 0.5),
            requires_confirmation=True,  # ALWAYS true for document extraction
        ).model_dump()

    message = ""
    if extraction_result.get("error"):
        message = extraction_result["error"]
    elif not extracted_fields:
        message = "No clinical values could be extracted from this image."
    else:
        message = f"Extracted {len(extracted_fields)} field(s). Please review and confirm each value."

    return UploadReportResponse(
        extracted_fields=extracted_fields,
        message=message,
    )


# ── POST /consumer/confirm-field ────────────────────────────────────────────

@consumer_router.post("/confirm-field", response_model=ConfirmFieldResponse)
def confirm_field(request: ConfirmFieldRequest):
    """
    Confirm or edit a pending field value.

    If was_edited is True, the source becomes "user_stated" with confidence 1.0.
    If was_edited is False, the original source stays but requires_confirmation
    is set to False.
    """
    payload = request.current_payload
    field_name = request.field_name

    # Validate field name exists on the payload
    if field_name not in ConsumerIntakePayload.model_fields:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown field: {field_name}",
        )

    existing_field: ExtractedField = getattr(payload, field_name)

    if request.was_edited:
        # User edited the value — treat as user_stated
        updated_field = ExtractedField(
            value=request.confirmed_value,
            source="user_stated",
            confidence=1.0,
            requires_confirmation=False,
        )
    else:
        # User confirmed the extracted value as-is
        updated_field = ExtractedField(
            value=existing_field.value if request.confirmed_value is None else request.confirmed_value,
            source=existing_field.source,
            confidence=existing_field.confidence,
            requires_confirmation=False,
        )

    setattr(payload, field_name, updated_field)

    return ConfirmFieldResponse(
        updated_field=updated_field,
        updated_payload=payload,
    )


# ── POST /consumer/assess ──────────────────────────────────────────────────

@consumer_router.post("/assess", response_model=AssessResponse)
def consumer_assess(request: AssessRequest):
    """
    Run all four deterministic scoring engines with the confirmed payload,
    then pass results to the existing LLM explainer.

    Engine execution order replicates orchestrator.py::run_all_engines:
      1. IDRS (diabetes)
      2. WHO-CVD
      3. HTN — first pass (CKD stage unknown)
      4. CKD (uses HTN + IDRS categories for pre-test probability)
      5. HTN — second pass (if CKD G-stage now known, re-evaluate BP targets)
    """
    # Convert payload → PatientData (only confirmed fields pass through)
    patient = request.payload.to_patient_data()

    # ── Run engines in dependency order ──────────────────────────────
    # This replicates the exact logic from orchestrator.py L64-L116

    idrs_resp = run_idrs_engine(patient)
    cvd_resp = run_who_cvd_engine(patient)

    # HTN pass 1 — CKD stage unknown
    htn_resp = run_htn_engine(
        patient,
        is_newly_diagnosed=False,
        ckd_stage=None,
        ckd_acr=patient.urine_acr_mg_g,
    )

    # CKD — uses HTN and IDRS categories for pre-test probability
    ckd_resp = run_ckd_engine(
        patient,
        htn_category=htn_resp.risk_category,
        idrs_category=idrs_resp.risk_category,
    )

    # HTN pass 2 — resolve cross-module BP targets with CKD G-stage
    ckd_g_stage = ckd_resp.extra_data.get("G_stage")
    if ckd_g_stage:
        htn_resp = run_htn_engine(
            patient,
            is_newly_diagnosed=False,
            ckd_stage=ckd_g_stage,
            ckd_acr=patient.urine_acr_mg_g,
        )

    engines = {
        "idrs": idrs_resp,
        "cvd": cvd_resp,
        "htn": htn_resp,
        "ckd": ckd_resp,
    }

    missing = aggregate_missing_investigations(list(engines.values()))
    referral = determine_referral(engines)

    structured_data = {
        "idrs_diabetes_risk": idrs_resp.__dict__,
        "who_cvd_risk": cvd_resp.__dict__,
        "hypertension_risk": htn_resp.__dict__,
        "ckd_kdigo_risk": ckd_resp.__dict__,
        "missing_investigations": missing,
        "referral_decision": referral,
    }

    # ── LLM explanation ──────────────────────────────────────────────
    client, model, status = _get_client_and_model()
    llm_explanation = ""

    if client is None:
        llm_explanation = status
    else:
        try:
            messages = _build_messages(structured_data, request.language)
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=2048,
                temperature=0.3,
            )
            llm_explanation = completion.choices[0].message.content or ""
        except Exception as exc:
            logger.error("LLM explanation call failed: %s", exc)
            llm_explanation = f"[LLM explanation unavailable: {exc}]"

    return AssessResponse(
        structured_data=structured_data,
        llm_explanation=llm_explanation,
        provenance=request.payload,
    )


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_pending_confirmations(payload: ConsumerIntakePayload) -> list:
    """Return a list of fields that still need user confirmation."""
    pending = []
    for field_name in ConsumerIntakePayload.model_fields:
        ef: ExtractedField = getattr(payload, field_name)
        if ef.requires_confirmation and ef.value is not None:
            pending.append({
                "field_name": field_name,
                "value": ef.value,
                "source": ef.source,
                "confidence": ef.confidence,
            })
    return pending
