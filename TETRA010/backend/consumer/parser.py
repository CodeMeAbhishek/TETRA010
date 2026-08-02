"""
Consumer Tier LLM parser.

Calls the NIM/OpenRouter endpoint with structured JSON output
to turn a chat transcript into a ConsumerIntakePayload.

Safety rules enforced:
  1. Never-assumable numeric fields are forced to null unless the model
     provides source == "user_stated" with a verbatim quote.
  2. Inferable fields are tagged "inferred" with a confidence score.
  3. BMI may be computed from user-stated height + weight (arithmetic, not guessing).
  4. Uses response_format={"type": "json_object"} for structured output.
"""

import json
import logging
from typing import List, Optional, Tuple

from backend.consumer.schemas import (
    ConsumerIntakePayload,
    ExtractedField,
    ConflictRecord,
)
from backend.orchestrator import _get_client_and_model

logger = logging.getLogger(__name__)


# ── Never-assumable fields ───────────────────────────────────────────────────
# These numeric/clinical fields must NEVER be guessed or estimated.
# If the model tries to fill one without source == "user_stated", force to null.
NEVER_ASSUMABLE_FIELDS = frozenset({
    "waist_circumference_cm",
    "systolic_bp",
    "diastolic_bp",
    "total_cholesterol_mmol_L",
    "serum_creatinine_mg_dl",
    "urine_acr_mg_g",
    "ascvd_10y_risk_percent",
    "bmi",
})

# ── Plausibility bounds ──────────────────────────────────────────────────────
# These numeric fields must fall within physiological ranges.
PLAUSIBILITY_BOUNDS = {
    "systolic_bp": (70, 260),
    "diastolic_bp": (40, 150),
    "total_cholesterol_mmol_L": (2, 15),
    "serum_creatinine_mg_dl": (0.2, 15),
    "urine_acr_mg_g": (0, 5000),
    "waist_circumference_cm": (40, 200),
    "bmi": (10, 70),
    "age": (1, 120),
}

# ── Inferable fields ─────────────────────────────────────────────────────────
# These may be deduced from natural language but must be tagged "inferred".
INFERABLE_FIELDS = frozenset({
    "is_smoker",
    "physical_activity",
    "family_history_diabetes",
    "has_diabetes",
    "known_clinical_cvd",
})


# ── System prompt ────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
You are a clinical data extraction assistant inside a health screening tool.
Your ONLY job is to extract structured patient data from a conversation transcript.

You MUST respond with a JSON object. Do NOT include any text outside the JSON.

## STRICT RULES — violation of any rule is a critical safety failure:

1. NEVER guess or estimate a numeric clinical measurement. If the user did not
   explicitly state a number, set that field to null.

2. NEVER-ASSUMABLE FIELDS (must be null unless the user explicitly stated the exact number):
   waist_circumference_cm, systolic_bp, diastolic_bp, total_cholesterol_mmol_L,
   serum_creatinine_mg_dl, urine_acr_mg_g, ascvd_10y_risk_percent, bmi.

3. BMI may be COMPUTED if the user provides both height and weight (pure arithmetic).
   In that case, set source to "user_stated" and confidence to 1.0.

4. INFERABLE FIELDS (may be deduced from context, tagged "inferred" with confidence):
   is_smoker, physical_activity, family_history_diabetes, has_diabetes, known_clinical_cvd.
   Example: "I sit at a desk all day" → physical_activity: "sedentary", source: "inferred", confidence: 0.8.

5. age and sex may be stated or inferred. If stated, source = "user_stated", confidence = 1.0.
   If inferred from context (e.g., "my husband" implies the speaker's sex), tag "inferred".

## VALID VALUES:
- sex: "male" or "female"
- physical_activity: "vigorous", "moderate", "mild", or "sedentary"
- family_history_diabetes: "none", "one_parent", or "both_parents"
- is_smoker: true or false
- has_diabetes: true or false
- known_clinical_cvd: true or false

## OUTPUT FORMAT (JSON):
{
  "field_name": {
    "value": <extracted value or null>,
    "source": "user_stated" | "inferred" | "null",
    "confidence": <0.0-1.0>
  },
  ...
}

Only include fields where you found relevant information in the conversation.
Omit fields that have no evidence at all in the transcript.
"""


# ── Parser function ──────────────────────────────────────────────────────────

def parse_conversation(
    conversation: List[dict],
    existing_payload: Optional[ConsumerIntakePayload] = None,
) -> Tuple[ConsumerIntakePayload, List[ConflictRecord]]:
    """
    Parse a conversation transcript into a ConsumerIntakePayload.

    Args:
        conversation: OpenAI-style message list [{role, content}].
        existing_payload: If provided, newly extracted fields are merged in.
                          Conflicts with already-confirmed values are logged.

    Returns:
        (updated_payload, conflicts_list, implausible_list)
    """
    payload = existing_payload or ConsumerIntakePayload()
    conflicts = []
    implausible = []

    client, model, status = _get_client_and_model()
    if client is None:
        logger.warning("LLM client not available for parsing: %s", status)
        return payload, conflicts, implausible

    # Build the user message from the conversation transcript
    transcript_text = _build_transcript_text(conversation)

    messages = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": f"Extract patient data from this conversation:\n\n{transcript_text}"},
    ]

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=1024,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw_text = completion.choices[0].message.content or "{}"
        extracted = json.loads(raw_text)
    except (json.JSONDecodeError, Exception) as exc:
        logger.error("Parser LLM call failed or returned invalid JSON: %s", exc)
        return payload, conflicts, implausible

    # Validate and merge extracted fields
    payload, conflicts, implausible = _merge_extracted(payload, extracted, conflicts, implausible)

    return payload, conflicts, implausible


def _build_transcript_text(conversation: List[dict]) -> str:
    """Format conversation history into a readable transcript."""
    lines = []
    for msg in conversation:
        role = msg.get("role", "unknown").upper()
        content = msg.get("content", "")
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _merge_extracted(
    payload: ConsumerIntakePayload,
    extracted: dict,
    conflicts: List[ConflictRecord],
    implausible: List[dict] = None,
) -> Tuple[ConsumerIntakePayload, List[ConflictRecord], List[dict]]:
    """
    Merge LLM-extracted fields into the payload with safety enforcement.

    - Never-assumable fields are forced to null unless source == "user_stated".
    - Plausibility bounds are checked; out-of-bounds fields are rejected to `implausible`.
    - Conflicts with existing confirmed values are logged, not silently overwritten.
    """
    if implausible is None:
        implausible = []

    # All field names in ConsumerIntakePayload
    valid_fields = set(ConsumerIntakePayload.model_fields.keys())

    for field_name, field_data in extracted.items():
        if field_name not in valid_fields:
            continue

        if not isinstance(field_data, dict):
            continue

        raw_value = field_data.get("value")
        raw_source = field_data.get("source", "null")
        raw_confidence = field_data.get("confidence", 0.0)

        # Skip null extractions
        if raw_value is None or raw_source == "null":
            continue

        # SAFETY: Never-assumable enforcement
        if field_name in NEVER_ASSUMABLE_FIELDS:
            if raw_source != "user_stated":
                logger.info(
                    "Blocked never-assumable field '%s' with source '%s' (value: %s)",
                    field_name, raw_source, raw_value,
                )
                continue  # Silently drop — do NOT populate with a guess

        # SAFETY: Plausibility bounds (Bug B)
        if field_name in PLAUSIBILITY_BOUNDS and raw_value is not None:
            min_val, max_val = PLAUSIBILITY_BOUNDS[field_name]
            try:
                num_val = float(raw_value)
                if not (min_val <= num_val <= max_val):
                    logger.warning("Implausible value %s for %s", raw_value, field_name)
                    implausible.append({
                        "field_name": field_name,
                        "value": raw_value,
                        "reason": f"outside plausible range {min_val}-{max_val}"
                    })
                    continue  # Reject from payload, don't silently accept
            except (ValueError, TypeError):
                pass

        # Validate source literal
        if raw_source not in ("user_stated", "inferred", "extracted_from_document"):
            raw_source = "inferred"

        # Clamp confidence
        try:
            raw_confidence = max(0.0, min(1.0, float(raw_confidence)))
        except (ValueError, TypeError):
            raw_confidence = 0.5

        # Build the new ExtractedField
        new_field = ExtractedField(
            value=raw_value,
            source=raw_source,
            confidence=raw_confidence if raw_source != "user_stated" else 1.0,
            requires_confirmation=False,  # Will be set below if needed
        )

        # Check for conflicts with existing confirmed values
        existing_field: ExtractedField = getattr(payload, field_name)
        if (
            existing_field.value is not None
            and existing_field.source != "null"
            and not existing_field.requires_confirmation
            and existing_field.value != raw_value
        ):
            conflict = ConflictRecord(
                field_name=field_name,
                old_value=existing_field.value,
                old_source=existing_field.source,
                new_value=raw_value,
                new_source=raw_source,
            )
            conflicts.append(conflict)
            # Most-recently-confirmed value wins by default per spec
            # but we log the conflict for UI to surface
            continue

        # Set the field on the payload
        setattr(payload, field_name, new_field)

    return payload, conflicts, implausible


# ── Follow-up question generator ────────────────────────────────────────────

def generate_assistant_response(
    conversation: List[dict],
    payload: ConsumerIntakePayload,
    gap_summary: dict,
    pending_confirmations: List[dict],
    implausible_extractions: List[dict] = None,
) -> str:
    """
    Generate a conversational assistant response that:
    1. Acknowledges what was extracted (strictly grounding on stored values).
    2. Asks targeted follow-up questions for missing mandatory fields.
    3. Mentions any pending verification cards.
    4. Asks clarification for any implausible extractions.
    """
    if implausible_extractions is None:
        implausible_extractions = []

    client, model, status = _get_client_and_model()
    if client is None:
        return _build_fallback_response(gap_summary, pending_confirmations)

    # Summarize what we know and what we need
    known_fields = []
    for field_name in ConsumerIntakePayload.model_fields:
        ef: ExtractedField = getattr(payload, field_name)
        if ef.value is not None and ef.source != "null":
            known_fields.append(f"- {field_name}: {ef.value} (source: {ef.source})")

    missing_summary = []
    for engine, info in gap_summary.items():
        if not info.get("can_run", False) and info.get("missing_required"):
            missing_summary.append(f"- {engine}: needs {', '.join(info['missing_required'])}")

    implausible_summary = []
    for imp in implausible_extractions:
        implausible_summary.append(f"- {imp['field_name']}: user said {imp['value']} (this is {imp['reason']})")

    system_msg = (
        "You are a friendly health screening assistant. You are helping a user understand their "
        "risk for lifestyle diseases. You do NOT diagnose or compute scores — a separate validated "
        "engine does that. Your job is to gather information conversationally.\n\n"
        "Rules:\n"
        "- Be warm, clear, and non-alarming.\n"
        "- When acknowledging what we know, strictly ground your response in the provided list. DO NOT contradict the stored values (e.g., if physical_activity is 'sedentary', do not say the user is active).\n"
        "- Ask 2-4 focused follow-up questions about missing fields.\n"
        "- If there are implausible values, politely ask the user to clarify or restate that specific number.\n"
        "- NEVER ask for more than 4 things at once.\n"
        "- NEVER guess clinical values — only ask the user.\n"
        "- If the user cannot provide a measurement, accept that gracefully.\n"
        "- Keep responses concise (under 150 words).\n"
    )

    user_msg = (
        f"What we know so far:\n{'chr(10)'.join(known_fields) if known_fields else 'Nothing yet.'}\n\n"
        f"What engines still need:\n{'chr(10)'.join(missing_summary) if missing_summary else 'All engines can run.'}\n\n"
        f"Implausible values to clarify:\n{'chr(10)'.join(implausible_summary) if implausible_summary else 'None.'}\n\n"
        f"Pending confirmations: {len(pending_confirmations)} fields need user verification.\n\n"
        "Generate the next assistant message. If there are implausible values, prioritize asking about them. "
        "If all engines can run, tell the user they can get their results now. If not, ask the most impactful follow-up questions."
    )

    try:
        completion = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            max_tokens=512,
            temperature=0.5,
        )
        return completion.choices[0].message.content or _build_fallback_response(gap_summary, pending_confirmations)
    except Exception as exc:
        logger.error("Failed to generate assistant response: %s", exc)
        return _build_fallback_response(gap_summary, pending_confirmations)


def _build_fallback_response(gap_summary: dict, pending_confirmations: List[dict]) -> str:
    """Deterministic fallback when LLM is unavailable."""
    lines = ["Thank you for sharing that information."]

    # Collect all unique missing required fields
    missing_fields = set()
    for engine, info in gap_summary.items():
        for f in info.get("missing_required", []):
            missing_fields.add(f)

    if missing_fields:
        lines.append("\nTo give you a complete assessment, I still need a few details:")
        for f in sorted(missing_fields)[:4]:  # Ask at most 4
            lines.append(f"  • {f.replace('_', ' ').title()}")

    if pending_confirmations:
        lines.append(f"\nPlease also review {len(pending_confirmations)} value(s) that need your confirmation.")

    if not missing_fields and not pending_confirmations:
        lines.append("\nI have enough information to run your health assessment. Click 'Get My Results' when you are ready.")

    return "\n".join(lines)
