"""
Consumer Tier unit tests.

Mirrors the unittest style of test_engines.py for consistency.
Tests cover:
  1. Parser never-assumable enforcement
  2. Parser user-stated extraction
  3. Gap analysis — IDRS missing mandatory
  4. Gap analysis — CKD graceful (always runs)
  5. Gap analysis — WHO-CVD partial (non-lab fallback)
  6. Confirmation gate on to_patient_data()
  7. Conflict detection
  8. End-to-end sparse assessment
"""

import unittest
from backend.consumer.schemas import (
    ConsumerIntakePayload,
    ExtractedField,
    ConflictRecord,
)
from backend.consumer.gap_analysis import analyze_gaps, get_followup_questions
from backend.consumer.parser import (
    _merge_extracted,
    NEVER_ASSUMABLE_FIELDS,
)


class TestParserSafety(unittest.TestCase):
    """Parser must never populate never-assumable fields without user_stated source."""

    def test_never_assumable_blocked_when_inferred(self):
        """LLM tries to fill a BP value via 'inferred' — must be rejected."""
        payload = ConsumerIntakePayload()
        extracted = {
            "systolic_bp": {"value": 140, "source": "inferred", "confidence": 0.7},
            "diastolic_bp": {"value": 90, "source": "inferred", "confidence": 0.7},
            "bmi": {"value": 28.5, "source": "inferred", "confidence": 0.6},
        }
        updated, conflicts, impl = _merge_extracted(payload, extracted, [])
        # All never-assumable fields must remain null
        self.assertIsNone(updated.systolic_bp.value)
        self.assertIsNone(updated.diastolic_bp.value)
        self.assertIsNone(updated.bmi.value)

    def test_bug_b_plausibility_bounds(self):
        """Bug B: Out-of-bounds values are rejected and added to implausible_extractions."""
        payload = ConsumerIntakePayload()
        # Out-of-range
        extracted_out = {
            "systolic_bp": {"value": 50, "source": "user_stated", "confidence": 1.0},
            "age": {"value": 150, "source": "user_stated", "confidence": 1.0},
        }
        updated, conflicts, implausible = _merge_extracted(payload, extracted_out, [])
        self.assertIsNone(updated.systolic_bp.value)
        self.assertIsNone(updated.age.value)
        self.assertEqual(len(implausible), 2)
        
        # In-range
        extracted_in = {
            "systolic_bp": {"value": 120, "source": "user_stated", "confidence": 1.0},
            "age": {"value": 45, "source": "user_stated", "confidence": 1.0},
        }
        updated_in, conflicts_in, implausible_in = _merge_extracted(payload, extracted_in, [])
        self.assertEqual(updated_in.systolic_bp.value, 120)
        self.assertEqual(updated_in.age.value, 45)
        self.assertEqual(len(implausible_in), 0)

    def test_never_assumable_accepted_when_user_stated(self):
        """User explicitly says 'my BP is 140/90' — must be accepted."""
        payload = ConsumerIntakePayload()
        extracted = {
            "systolic_bp": {"value": 140, "source": "user_stated", "confidence": 1.0},
            "diastolic_bp": {"value": 90, "source": "user_stated", "confidence": 1.0},
        }
        updated, conflicts, impl = _merge_extracted(payload, extracted, [])
        self.assertEqual(updated.systolic_bp.value, 140)
        self.assertEqual(updated.systolic_bp.source, "user_stated")
        self.assertEqual(updated.diastolic_bp.value, 90)

    def test_vague_conversation_no_numerics(self):
        """Conversation with no explicit numbers — all never-assumable fields stay null."""
        payload = ConsumerIntakePayload()
        # Simulate LLM extracting only inferable fields from "I feel tired, I sit all day"
        extracted = {
            "physical_activity": {"value": "sedentary", "source": "inferred", "confidence": 0.8},
            "waist_circumference_cm": {"value": 95, "source": "inferred", "confidence": 0.3},
        }
        updated, conflicts, impl = _merge_extracted(payload, extracted, [])
        # physical_activity is inferable — should be accepted
        self.assertEqual(updated.physical_activity.value, "sedentary")
        self.assertEqual(updated.physical_activity.source, "inferred")
        # waist_circumference_cm is never-assumable — must be rejected
        self.assertIsNone(updated.waist_circumference_cm.value)

    def test_all_never_assumable_fields_covered(self):
        """Verify the NEVER_ASSUMABLE_FIELDS set matches the spec."""
        expected = {
            "waist_circumference_cm", "systolic_bp", "diastolic_bp",
            "total_cholesterol_mmol_L", "serum_creatinine_mg_dl",
            "urine_acr_mg_g", "ascvd_10y_risk_percent", "bmi",
        }
        self.assertEqual(NEVER_ASSUMABLE_FIELDS, expected)


class TestGapAnalysis(unittest.TestCase):
    """Gap analysis must correctly identify per-engine requirements."""

    def test_idrs_missing_mandatory(self):
        """Payload with only age — IDRS cannot run."""
        payload = ConsumerIntakePayload(
            age=ExtractedField(value=55, source="user_stated", confidence=1.0),
        )
        gaps = analyze_gaps(payload)
        self.assertFalse(gaps["idrs"]["can_run"])
        missing = gaps["idrs"]["missing_required"]
        self.assertIn("waist_circumference_cm", missing)
        self.assertIn("physical_activity", missing)
        self.assertIn("family_history_diabetes", missing)
        self.assertIn("sex", missing)

    def test_idrs_complete(self):
        """All IDRS mandatory fields filled — IDRS can run."""
        payload = ConsumerIntakePayload(
            age=ExtractedField(value=55, source="user_stated", confidence=1.0),
            sex=ExtractedField(value="female", source="user_stated", confidence=1.0),
            waist_circumference_cm=ExtractedField(value=92, source="user_stated", confidence=1.0),
            physical_activity=ExtractedField(value="sedentary", source="inferred", confidence=0.8),
            family_history_diabetes=ExtractedField(value="one_parent", source="user_stated", confidence=1.0),
        )
        gaps = analyze_gaps(payload)
        self.assertTrue(gaps["idrs"]["can_run"])
        self.assertEqual(gaps["idrs"]["missing_required"], [])

    def test_ckd_always_can_run(self):
        """CKD has no hard-mandatory fields — always can_run."""
        payload = ConsumerIntakePayload()  # Empty payload
        gaps = analyze_gaps(payload)
        self.assertTrue(gaps["ckd"]["can_run"])
        self.assertEqual(gaps["ckd"]["missing_required"], [])
        # But optional fields should be listed
        self.assertGreater(len(gaps["ckd"]["missing_optional"]), 0)

    def test_cvd_partial_with_bmi_fallback(self):
        """Payload with age, sex, is_smoker, systolic_bp, bmi — CVD can run (non-lab)."""
        payload = ConsumerIntakePayload(
            age=ExtractedField(value=50, source="user_stated", confidence=1.0),
            sex=ExtractedField(value="male", source="user_stated", confidence=1.0),
            is_smoker=ExtractedField(value=False, source="user_stated", confidence=1.0),
            systolic_bp=ExtractedField(value=130, source="user_stated", confidence=1.0),
            bmi=ExtractedField(value=26.0, source="user_stated", confidence=1.0),
        )
        gaps = analyze_gaps(payload)
        self.assertTrue(gaps["cvd"]["can_run"])

    def test_htn_missing_diastolic(self):
        """HTN requires both systolic and diastolic — missing one blocks it."""
        payload = ConsumerIntakePayload(
            systolic_bp=ExtractedField(value=130, source="user_stated", confidence=1.0),
        )
        gaps = analyze_gaps(payload)
        self.assertFalse(gaps["htn"]["can_run"])
        self.assertIn("diastolic_bp", gaps["htn"]["missing_required"])

    def test_followup_questions(self):
        """Follow-up questions prioritize fields that unblock the most engines."""
        payload = ConsumerIntakePayload()  # Empty
        gaps = analyze_gaps(payload)
        questions = get_followup_questions(gaps)
        self.assertGreater(len(questions), 0)
        self.assertLessEqual(len(questions), 4)


class TestConfirmationGate(unittest.TestCase):
    """Fields with requires_confirmation=True must not pass into engine calls."""

    def test_unconfirmed_field_excluded_from_patient_data(self):
        """A field pending confirmation produces None in PatientData."""
        payload = ConsumerIntakePayload(
            age=ExtractedField(value=50, source="user_stated", confidence=1.0),
            sex=ExtractedField(value="male", source="user_stated", confidence=1.0),
            systolic_bp=ExtractedField(
                value=140,
                source="extracted_from_document",
                confidence=0.9,
                requires_confirmation=True,  # Not yet confirmed
            ),
        )
        patient_data = payload.to_patient_data()
        self.assertEqual(patient_data.age, 50)
        self.assertEqual(patient_data.sex, "male")
        # systolic_bp should be None because it's unconfirmed
        self.assertIsNone(patient_data.systolic_bp)

    def test_confirmed_field_included_in_patient_data(self):
        """A confirmed field passes through to PatientData."""
        payload = ConsumerIntakePayload(
            systolic_bp=ExtractedField(
                value=140,
                source="extracted_from_document",
                confidence=0.9,
                requires_confirmation=False,  # Confirmed
            ),
        )
        patient_data = payload.to_patient_data()
        self.assertEqual(patient_data.systolic_bp, 140)

    def test_unconfirmed_field_excluded_from_gap_analysis(self):
        """Gap analysis treats unconfirmed fields as unavailable."""
        payload = ConsumerIntakePayload(
            systolic_bp=ExtractedField(
                value=140,
                source="extracted_from_document",
                confidence=0.9,
                requires_confirmation=True,
            ),
            diastolic_bp=ExtractedField(
                value=90, source="user_stated", confidence=1.0,
            ),
        )
        gaps = analyze_gaps(payload)
        # HTN should NOT be runnable — systolic_bp is unconfirmed
        self.assertFalse(gaps["htn"]["can_run"])
        self.assertIn("systolic_bp", gaps["htn"]["missing_required"])


class TestConflictDetection(unittest.TestCase):
    """Conflicting values from different sources must be logged, not silently overwritten."""

    def test_conflict_on_different_value(self):
        """Two extractions with different systolic_bp → conflict recorded."""
        payload = ConsumerIntakePayload(
            systolic_bp=ExtractedField(
                value=130,
                source="user_stated",
                confidence=1.0,
                requires_confirmation=False,
            ),
        )
        # New extraction says 150
        extracted = {
            "systolic_bp": {"value": 150, "source": "user_stated", "confidence": 1.0},
        }
        updated, conflicts, impl = _merge_extracted(payload, extracted, [])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0].field_name, "systolic_bp")
        self.assertEqual(conflicts[0].old_value, 130)
        self.assertEqual(conflicts[0].new_value, 150)
        # Old value should be preserved (most-recently-confirmed wins)
        self.assertEqual(updated.systolic_bp.value, 130)

    def test_no_conflict_on_same_value(self):
        """Same value from different extraction — no conflict."""
        payload = ConsumerIntakePayload(
            age=ExtractedField(value=55, source="user_stated", confidence=1.0),
        )
        extracted = {
            "age": {"value": 55, "source": "user_stated", "confidence": 1.0},
        }
        updated, conflicts, impl = _merge_extracted(payload, extracted, [])
        self.assertEqual(len(conflicts), 0)


class TestEndToEndSparse(unittest.TestCase):
    """
    Sparse conversation: age 55 + "I don't exercise" + "no family diabetes".
    Expected:
      - IDRS cannot run (no waist circumference, no sex)
      - CVD cannot run (no BP, no smoking status)
      - HTN cannot run (no BP)
      - CKD runs with pre-test probability only
    """

    def test_sparse_payload_gap_analysis(self):
        payload = ConsumerIntakePayload(
            age=ExtractedField(value=55, source="user_stated", confidence=1.0),
            physical_activity=ExtractedField(value="sedentary", source="inferred", confidence=0.8),
            family_history_diabetes=ExtractedField(value="none", source="user_stated", confidence=1.0),
        )
        gaps = analyze_gaps(payload)

        # IDRS: missing sex, waist
        self.assertFalse(gaps["idrs"]["can_run"])
        self.assertIn("waist_circumference_cm", gaps["idrs"]["missing_required"])
        self.assertIn("sex", gaps["idrs"]["missing_required"])

        # CVD: missing sex, is_smoker, systolic_bp
        self.assertFalse(gaps["cvd"]["can_run"])

        # HTN: missing BP
        self.assertFalse(gaps["htn"]["can_run"])

        # CKD: always can_run (graceful degradation)
        self.assertTrue(gaps["ckd"]["can_run"])

    def test_sparse_payload_engine_execution(self):
        """Run engines with sparse confirmed data — only CKD produces meaningful output."""
        from backend.scoring.engine_idrs import run_idrs_engine
        from backend.scoring.engine_who_cvd import run_who_cvd_engine
        from backend.scoring.engine_htn import run_htn_engine
        from backend.scoring.engine_ckd import run_ckd_engine

        payload = ConsumerIntakePayload(
            age=ExtractedField(value=55, source="user_stated", confidence=1.0),
            physical_activity=ExtractedField(value="sedentary", source="inferred", confidence=0.8),
            family_history_diabetes=ExtractedField(value="none", source="user_stated", confidence=1.0),
        )
        patient = payload.to_patient_data()

        # IDRS: should report missing mandatory fields
        idrs = run_idrs_engine(patient)
        self.assertIn("error", idrs.extra_data)
        self.assertIsNone(idrs.risk_score)

        # CVD: should report missing inputs
        cvd = run_who_cvd_engine(patient)
        self.assertGreater(len(cvd.missing_inputs), 0)

        # HTN: should report missing BP
        htn = run_htn_engine(patient)
        self.assertGreater(len(htn.missing_inputs), 0)
        self.assertIsNone(htn.risk_category)

        # CKD: should run (pre-test probability fallback)
        ckd = run_ckd_engine(patient, htn_category=None, idrs_category=None)
        # With no diabetes, no HTN, no creatinine — CKD returns empty/minimal
        # but does NOT crash
        self.assertIsNotNone(ckd)


class TestAssistantGeneration(unittest.TestCase):
    def test_bug_a_polarity_hallucination(self):
        """Bug A: Assistant must not contradict stored polarity (e.g. sedentary != active)."""
        from backend.consumer.parser import generate_assistant_response
        from backend.orchestrator import _get_client_and_model
        
        client, _, _ = _get_client_and_model()
        if client is None:
            self.skipTest("No LLM client configured, skipping generation test.")
            
        payload = ConsumerIntakePayload(
            physical_activity=ExtractedField(value="sedentary", source="user_stated", confidence=1.0)
        )
        response = generate_assistant_response(
            conversation=[{"role": "user", "content": "I don't exercise much."}],
            payload=payload,
            gap_summary={"idrs": {"can_run": False, "missing_required": ["age", "waist_circumference_cm"]}},
            pending_confirmations=[]
        )
        
        lower_resp = response.lower()
        if "active" in lower_resp:
            # If it uses 'active', it must be negated
            self.assertTrue(
                "not active" in lower_resp or "less active" in lower_resp or "inactive" in lower_resp or "isn't active" in lower_resp,
                f"Response hallucinates 'active' without negation for a sedentary user: {response}"
            )


class TestDemoScenariosProgrammatic(unittest.TestCase):
    def setUp(self):
        from fastapi.testclient import TestClient
        from backend.api import app
        self.client = TestClient(app)

    def test_medium_three_conditions_replay(self):
        """Replay medium_three_conditions and assert engines score."""
        turns = [
            "I'm a 58-year-old woman. My blood pressure was 148 over 92 last time I checked, and I'm a smoker.",
            "My waist is 92 cm, I only do light walking a few times a week, and no one in my family has diabetes.",
            "I weigh 78 kg and I'm 160 cm tall. I don't know my cholesterol number though."
        ]
        conversation = []
        payload = None
        
        for turn in turns:
            conversation.append({"role": "user", "content": turn})
            resp = self.client.post("/consumer/chat", json={
                "conversation": conversation,
                "current_payload": payload
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            payload = data["updated_payload"]
            conversation.append({"role": "assistant", "content": data["assistant_message"]})
            
        resp = self.client.post("/consumer/assess", json={
            "payload": payload,
            "language": "English"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        struct = data["structured_data"]
        
        self.assertIn("idrs_diabetes_risk", struct)
        self.assertIn("who_cvd_risk", struct)
        self.assertIn("hypertension_risk", struct)
        self.assertIn("ckd_kdigo_risk", struct)

    def test_minimal_declines_replay(self):
        """Replay minimal_declines and assert no fabricated scores."""
        turns = [
            "I'm 39 years old, that's really all I know off the top of my head.",
            "I'd rather just see what you can tell me with what I've given you."
        ]
        conversation = []
        payload = None
        for turn in turns:
            conversation.append({"role": "user", "content": turn})
            resp = self.client.post("/consumer/chat", json={
                "conversation": conversation,
                "current_payload": payload
            })
            self.assertEqual(resp.status_code, 200)
            data = resp.json()
            payload = data["updated_payload"]
            conversation.append({"role": "assistant", "content": data["assistant_message"]})
            
        resp = self.client.post("/consumer/assess", json={
            "payload": payload,
            "language": "English"
        })
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        struct = data["structured_data"]
        
        for eng in ["idrs_diabetes_risk", "who_cvd_risk", "hypertension_risk"]:
            res = struct.get(eng, {})
            self.assertTrue(len(res.get("missing_inputs", [])) > 0 or "error" in res.get("extra_data", {}))


if __name__ == "__main__":
    unittest.main()
