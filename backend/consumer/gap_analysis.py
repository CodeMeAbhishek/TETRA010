"""
Consumer Tier gap analysis.

Given a partially-filled ConsumerIntakePayload, determines per-engine:
  - can_run: whether the engine has all hard-mandatory fields.
  - missing_required: list of hard-mandatory fields still missing.
  - missing_optional: list of optional fields that would improve results.

Field requirements are derived from reading the actual engine code in
backend/scoring/engine_*.py — see inline comments for source references.
"""

from typing import Dict, List, Set
from backend.consumer.schemas import ConsumerIntakePayload, ExtractedField


# ── Per-engine mandatory field maps ──────────────────────────────────────────
# Source of truth: each engine's early-return / missing-input checks.
#
# IDRS (engine_idrs.py L7-L27):
#   Returns early if ANY of age, sex, waist_circumference_cm, physical_activity,
#   family_history_diabetes is None.
#
# WHO-CVD (engine_who_cvd.py L49-L60):
#   Returns early if ANY of age, sex, is_smoker, systolic_bp is None.
#   Then needs EITHER (total_cholesterol_mmol_L + has_diabetes) for lab chart
#   OR bmi for non-lab fallback. Not hard-mandatory — engine handles gracefully.
#
# HTN (engine_htn.py L6-L10):
#   Returns early if systolic_bp OR diastolic_bp is None.
#
# CKD (engine_ckd.py L37-L99):
#   Never returns early. Three fallback tiers:
#   1. scr + acr + age + sex → full KDIGO grid
#   2. scr + age + sex → G-stage only
#   3. Neither → pre-test probability heuristic
#   So CKD always "can_run" but quality varies.

IDRS_MANDATORY = {"age", "sex", "waist_circumference_cm", "physical_activity", "family_history_diabetes"}
IDRS_OPTIONAL: Set[str] = set()

CVD_MANDATORY = {"age", "sex", "is_smoker", "systolic_bp"}
# At least one of these pairs is needed for a score, but the engine handles the fallback.
CVD_OPTIONAL = {"total_cholesterol_mmol_L", "has_diabetes", "bmi"}

HTN_MANDATORY = {"systolic_bp", "diastolic_bp"}
HTN_OPTIONAL = {"ascvd_10y_risk_percent", "has_diabetes", "known_clinical_cvd"}

# CKD has no hard-mandatory fields — always runs with graceful degradation.
CKD_MANDATORY: Set[str] = set()
CKD_OPTIONAL = {"serum_creatinine_mg_dl", "urine_acr_mg_g", "age", "sex"}


# ── Gap analysis ─────────────────────────────────────────────────────────────

def _field_available(payload: ConsumerIntakePayload, field_name: str) -> bool:
    """
    A field is 'available' for engine scoring only if:
    1. It has a non-null value.
    2. Its source is not "null".
    3. It does NOT require confirmation (i.e., already confirmed or user_stated).
    """
    ef: ExtractedField = getattr(payload, field_name, None)
    if ef is None:
        return False
    if ef.value is None or ef.source == "null":
        return False
    if ef.requires_confirmation:
        return False
    return True


def analyze_gaps(payload: ConsumerIntakePayload) -> Dict[str, dict]:
    """
    Analyze what each engine needs vs. what the payload currently provides.

    Returns:
        {
            "idrs": { "can_run": bool, "missing_required": [...], "missing_optional": [...] },
            "cvd":  { ... },
            "htn":  { ... },
            "ckd":  { ... },
        }
    """
    result = {}

    for engine_name, mandatory, optional in [
        ("idrs", IDRS_MANDATORY, IDRS_OPTIONAL),
        ("cvd",  CVD_MANDATORY,  CVD_OPTIONAL),
        ("htn",  HTN_MANDATORY,  HTN_OPTIONAL),
        ("ckd",  CKD_MANDATORY,  CKD_OPTIONAL),
    ]:
        missing_req = [f for f in sorted(mandatory) if not _field_available(payload, f)]
        missing_opt = [f for f in sorted(optional) if not _field_available(payload, f)]
        can_run = len(missing_req) == 0

        # Custom logic for CVD: Needs EITHER (cholesterol + diabetes) OR bmi
        if engine_name == "cvd" and can_run:
            has_chol = _field_available(payload, "total_cholesterol_mmol_L")
            has_diab = _field_available(payload, "has_diabetes")
            has_bmi = _field_available(payload, "bmi")
            
            if not ((has_chol and has_diab) or has_bmi):
                can_run = False
                if has_chol and not has_diab:
                    missing_req.append("has_diabetes")
                    if "has_diabetes" in missing_opt:
                        missing_opt.remove("has_diabetes")
                else:
                    missing_req.append("bmi")
                    if "bmi" in missing_opt:
                        missing_opt.remove("bmi")

        result[engine_name] = {
            "can_run": can_run,
            "missing_required": missing_req,
            "missing_optional": missing_opt,
        }

    return result


# ── Follow-up question generator ────────────────────────────────────────────

# Human-readable labels for field names
_FIELD_LABELS = {
    "age": "your age",
    "sex": "your biological sex (male/female)",
    "waist_circumference_cm": "your waist circumference in centimeters",
    "physical_activity": "your activity level (vigorous, moderate, mild, or sedentary)",
    "family_history_diabetes": "whether your parents have diabetes (none, one parent, or both)",
    "is_smoker": "whether you smoke",
    "systolic_bp": "your blood pressure (the top number)",
    "diastolic_bp": "your blood pressure (the bottom number)",
    "total_cholesterol_mmol_L": "your total cholesterol level",
    "bmi": "your height and weight (so we can calculate BMI)",
    "has_diabetes": "whether you have been diagnosed with diabetes",
    "serum_creatinine_mg_dl": "your serum creatinine level from a blood test",
    "urine_acr_mg_g": "your urine albumin-creatinine ratio",
    "ascvd_10y_risk_percent": "your 10-year ASCVD risk percentage",
    "known_clinical_cvd": "whether you have been diagnosed with cardiovascular disease",
}

# How many engines each field unblocks when provided
def _compute_field_priority(gap_result: dict) -> List[str]:
    """
    Rank missing fields by how many engines they unblock.
    Returns a sorted list of field names, most impactful first.
    """
    field_scores: Dict[str, int] = {}

    for engine_name, info in gap_result.items():
        for f in info.get("missing_required", []):
            field_scores[f] = field_scores.get(f, 0) + 2  # Required = high priority
        for f in info.get("missing_optional", []):
            field_scores[f] = field_scores.get(f, 0) + 1  # Optional = lower priority

    # Sort by score descending, then alphabetically for tie-breaking
    return sorted(field_scores.keys(), key=lambda f: (-field_scores[f], f))


def get_followup_questions(gap_result: dict, max_questions: int = 4) -> List[str]:
    """
    Generate targeted follow-up questions for the most impactful missing fields.

    Args:
        gap_result: Output from analyze_gaps().
        max_questions: Maximum number of questions to return (default 4).

    Returns:
        List of human-readable question strings.
    """
    priority_fields = _compute_field_priority(gap_result)
    questions = []

    # Combine systolic_bp and diastolic_bp into a single "blood pressure" question
    bp_asked = False
    for field_name in priority_fields:
        if len(questions) >= max_questions:
            break

        if field_name in ("systolic_bp", "diastolic_bp"):
            if not bp_asked:
                questions.append("Do you know your blood pressure reading? (e.g., 120/80)")
                bp_asked = True
            continue

        label = _FIELD_LABELS.get(field_name, field_name.replace("_", " "))
        questions.append(f"Could you tell me {label}?")

    return questions
