import unittest
from backend.scoring.models import PatientData, EngineResponse
from backend.scoring.engine_idrs import run_idrs_engine
from backend.scoring.engine_who_cvd import run_who_cvd_engine
from backend.scoring.engine_htn import run_htn_engine
from backend.scoring.engine_ckd import run_ckd_engine
from backend.scoring.missing_investigations import aggregate_missing_investigations
from backend.scoring.referral_engine import determine_referral

class TestScoringEngines(unittest.TestCase):

    def test_idrs_missing_waist(self):
        p = PatientData(age=40, sex="male", physical_activity="mild", family_history_diabetes="none")
        resp = run_idrs_engine(p)
        self.assertIn("Missing mandatory IDRS inputs", resp.extra_data.get("error", ""))
        self.assertEqual(len(resp.missing_inputs), 1)
        self.assertEqual(resp.missing_inputs[0].test_name, "Waist Circumference")

    def test_idrs_low_risk(self):
        p = PatientData(age=30, sex="male", waist_circumference_cm=80, physical_activity="vigorous", family_history_diabetes="none")
        resp = run_idrs_engine(p)
        self.assertEqual(resp.risk_category, "Low Risk")
        self.assertEqual(resp.risk_score, 0)
        self.assertFalse(resp.referral_recommended)

    def test_idrs_high_risk(self):
        p = PatientData(age=55, sex="female", waist_circumference_cm=95, physical_activity="sedentary", family_history_diabetes="both_parents")
        resp = run_idrs_engine(p)
        self.assertEqual(resp.risk_category, "High Risk")
        self.assertEqual(resp.risk_score, 100) # 30 + 20 + 30 + 20 = 100
        self.assertTrue(resp.referral_recommended)
        
    def test_who_cvd_chart_selection(self):
        # Lab based
        p1 = PatientData(age=50, sex="male", is_smoker=True, systolic_bp=150, total_cholesterol_mmol_L=5.0, has_diabetes=False)
        resp1 = run_who_cvd_engine(p1)
        self.assertEqual(resp1.extra_data["chart_used"], "lab_based")
        self.assertEqual(resp1.risk_percentage, "10%")
        
        # Non lab based
        p2 = PatientData(age=50, sex="male", is_smoker=True, systolic_bp=150, bmi=26, has_diabetes=False)
        resp2 = run_who_cvd_engine(p2)
        self.assertEqual(resp2.extra_data["chart_used"], "non_lab_based")
        self.assertEqual(resp2.risk_percentage, "12%")
        
        # Test BMI gap fix (34.5 should map to 30-35, not fail)
        p3 = PatientData(age=60, sex="male", is_smoker=True, systolic_bp=185, bmi=34.5)
        resp3 = run_who_cvd_engine(p3)
        self.assertEqual(resp3.extra_data["chart_used"], "non_lab_based")
        self.assertEqual(resp3.risk_percentage, "29%")

    def test_htn_stage2(self):
        p = PatientData(systolic_bp=145, diastolic_bp=85)
        resp = run_htn_engine(p)
        self.assertEqual(resp.risk_category, "Stage 2 Hypertension")
        self.assertTrue(resp.referral_recommended)
        
    def test_htn_acute_stroke(self):
        p = PatientData(systolic_bp=230, diastolic_bp=100, acute_stroke_type="ich")
        resp = run_htn_engine(p)
        self.assertTrue(resp.referral_recommended)
        self.assertIn("acute_care_flag", resp.extra_data)
        
    def test_ckd_full(self):
        p = PatientData(serum_creatinine_mg_dl=1.0, urine_acr_mg_g=400, age=50, sex="male")
        resp = run_ckd_engine(p)
        # 1.0 mg/dL for 50yo male -> ~91.7 eGFR -> G1
        # ACR 400 -> A3
        self.assertEqual(resp.extra_data["G_stage"], "G1")
        self.assertEqual(resp.extra_data["A_stage"], "A3")
        self.assertEqual(resp.risk_category, "Orange")
        self.assertTrue(resp.referral_recommended) # A3 triggers referral
        
    def test_ckd_exhaustive_grid(self):
        from backend.scoring.engine_ckd import get_kdigo_risk
        expected = {
            "G1": {"A1": "Green", "A2": "Yellow", "A3": "Orange"},
            "G2": {"A1": "Green", "A2": "Yellow", "A3": "Orange"},
            "G3a": {"A1": "Yellow", "A2": "Orange", "A3": "Red"},
            "G3b": {"A1": "Orange", "A2": "Red", "A3": "Red"},
            "G4": {"A1": "Orange", "A2": "Red", "A3": "Red"},
            "G5": {"A1": "Red", "A2": "Red", "A3": "Red"}
        }
        for g, a_dict in expected.items():
            for a, color in a_dict.items():
                self.assertEqual(get_kdigo_risk(g, a), color, f"Mismatch at {g}+{a}")
                
    def test_ckd_graceful_missing_both(self):
        p = PatientData(age=55, has_diabetes=True)
        # Simulate HTN Stage 1
        resp = run_ckd_engine(p, htn_category="Stage 1 Hypertension")
        self.assertEqual(len(resp.missing_inputs), 1)
        self.assertIn("Serum Creatinine", resp.missing_inputs[0].test_name)

    def test_missing_investigations_aggregator(self):
        p1 = PatientData(age=55, sex="female", waist_circumference_cm=95, physical_activity="sedentary", family_history_diabetes="both_parents")
        resp_idrs = run_idrs_engine(p1) # Missing investigation for High Risk IDRS
        
        p2 = PatientData(systolic_bp=135, diastolic_bp=80)
        resp_htn = run_htn_engine(p2, is_newly_diagnosed=True) # 8 missing for newly diag HTN
        
        aggregated = aggregate_missing_investigations([resp_idrs, resp_htn])
        self.assertGreater(len(aggregated), 0)
        # One from IDRS, 8 from HTN -> 9
        self.assertEqual(len(aggregated), 9)
        
    def test_referral_engine(self):
        p_htn = PatientData(systolic_bp=145, diastolic_bp=85)
        resp_htn = run_htn_engine(p_htn)
        
        ref = determine_referral({"htn": resp_htn, "cvd": EngineResponse(), "idrs": EngineResponse(), "ckd": EngineResponse()})
        self.assertTrue(ref["referral_recommended"])
        self.assertEqual(len(ref["reasons"]), 1)
        
    def test_referral_engine_all_branches(self):
        resp_cvd = EngineResponse()
        resp_cvd.referral_recommended = True
        resp_cvd.referral_reason = "CVD high risk"
        
        resp_ckd = EngineResponse()
        resp_ckd.referral_recommended = True
        resp_ckd.referral_reason = "CKD high risk"
        
        resp_idrs = EngineResponse()
        resp_idrs.referral_recommended = True
        resp_idrs.referral_reason = "IDRS high risk"
        
        ref = determine_referral({"cvd": resp_cvd, "ckd": resp_ckd, "idrs": resp_idrs})
        self.assertTrue(ref["referral_recommended"])
        self.assertEqual(len(ref["reasons"]), 3)
        self.assertIn("CVD high risk", ref["reasons"])
        
    def test_missing_investigations_dedup(self):
        from backend.scoring.models import MissingInvestigation
        r1 = EngineResponse()
        r1.missing_inputs.append(MissingInvestigation("Test A", "Reason 1", "Guide 1"))
        
        r2 = EngineResponse()
        # Same test name, different reason
        r2.missing_inputs.append(MissingInvestigation("Test A", "Reason 2", "Guide 2"))
        # Exact same reason and guide to test complete dedup branch
        r2.missing_inputs.append(MissingInvestigation("Test A", "Reason 1", "Guide 1"))
        
        agg = aggregate_missing_investigations([r1, r2])
        self.assertEqual(len(agg), 1)
        self.assertEqual(len(agg[0]["reasons"]), 2)
        self.assertEqual(len(agg[0]["guideline_citations"]), 2)
        
    def test_htn_acute_stroke_branches(self):
        # ICH, SBP 150-220, onset <= 6h
        p1 = PatientData(systolic_bp=200, diastolic_bp=100, acute_stroke_type="ich", hours_since_stroke_onset=4)
        resp1 = run_htn_engine(p1)
        self.assertIn("Do NOT recommend immediate lowering", resp1.extra_data["acute_stroke_action"])
        
        # Ischemic tPA eligible
        p2 = PatientData(systolic_bp=190, diastolic_bp=100, acute_stroke_type="ischemic_tpa_eligible")
        resp2 = run_htn_engine(p2)
        self.assertIn("Lower BP to <185/110", resp2.extra_data["acute_stroke_action"])
        
        # Ischemic not tPA eligible, SBP >= 220
        p3 = PatientData(systolic_bp=230, diastolic_bp=100, acute_stroke_type="ischemic_not_tpa_eligible")
        resp3 = run_htn_engine(p3)
        self.assertIn("reasonably lower BP by ~15%", resp3.extra_data["acute_stroke_action"])
        
        # Ischemic not tPA eligible, SBP < 220
        p4 = PatientData(systolic_bp=200, diastolic_bp=100, acute_stroke_type="ischemic_not_tpa_eligible")
        resp4 = run_htn_engine(p4)
        self.assertIn("Withhold new antihypertensives", resp4.extra_data["acute_stroke_action"])

if __name__ == "__main__":
    unittest.main()
