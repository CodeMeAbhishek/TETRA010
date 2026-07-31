import unittest
from models import PatientData, EngineResponse
from engine_idrs import run_idrs_engine
from engine_who_cvd import run_who_cvd_engine
from engine_htn import run_htn_engine
from engine_ckd import run_ckd_engine
from missing_investigations import aggregate_missing_investigations
from referral_engine import determine_referral

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
        self.assertEqual(resp1.risk_percentage, "<5%")
        
        # Non lab based
        p2 = PatientData(age=50, sex="male", is_smoker=True, systolic_bp=150, bmi=26, has_diabetes=False)
        resp2 = run_who_cvd_engine(p2)
        self.assertEqual(resp2.extra_data["chart_used"], "non_lab_based")
        self.assertEqual(resp2.risk_percentage, "<5%")

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

if __name__ == "__main__":
    unittest.main()
