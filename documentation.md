# Internal Team Documentation & Progress Tracker

This document serves as the internal wiki for our team members. It tracks what we have built, answers common architectural questions (FAQs), and outlines our immediate next steps.

---

## 📈 Progress Updates (As of August 2026)

**1. Scoring Engines Fully Implemented & Tested**
*   **WHO-CVD**: Digitized the South Asia lab and non-lab charts into JSON. We successfully resolved the `BMI 30-35` gap bug and flattened the non-lab structure to perfectly match the source images.
*   **CKD (KDIGO)**: Implemented the CKD-EPI 2021 formula. We exhaustively verified all 18 permutations of the G×A heatmap against the official KDIGO source image (fixing standard G4+A1 and G3b+A2 mismatches).
*   **Hypertension**: Fully mapped the 2017 ACC/AHA guidelines, including deep coverage for Acute Stroke protocols (ICH vs Ischemic).
*   **Diabetes**: Implemented the MDRF-IDRS score, correctly enforcing Waist Circumference as a mandatory input for the Asian Indian phenotype.

**2. Shared Services Online**
*   **Missing Investigations Aggregator**: Deduplicates missing lab requests across all 5 conditions. (e.g., if HTN and CKD both need Serum Creatinine, the patient is only asked once).
*   **Referral Engine**: Aggregates risk from all engines and generates a single, coherent referral recommendation with specific clinical justifications.

**3. Codebase Restructuring & Quality**
*   Moved all clinical logic into `/backend/scoring/` to keep the architecture clean.
*   Achieved **86% Test Coverage**, including 100% coverage on the missing investigations and referral engines.

**4. LLM API & REST Layer Fully Integrated**
*   Wrapped the orchestrator in a **FastAPI** application (`main.py` & `/backend/api.py`).
*   Integrated **NVIDIA NIM** and **OpenRouter** APIs to generate multilingual explanations using Llama 3.1 8B Instruct based purely on the deterministic JSON.

**5. Frontend UI Built**
*   Built a lightweight, responsive HTML/JS/CSS frontend in `/frontend/` providing a clinical dashboard, gauges, missing tests alerts, and LLM text display.

---

## ❓ Frequently Asked Questions (FAQs)

**Q: Why are we hardcoding medical grids (like WHO-CVD and KDIGO) into JSON files instead of letting Claude read the charts?**
**A:** LLMs are prone to hallucination, especially with complex numerical matrices. By digitizing the charts into JSON and looking up values deterministically in Python, we guarantee 100% accuracy. The LLM is only used to *explain* the result, never to *calculate* it. 

**Q: How do we handle patients with missing data (like no lab results)?**
**A:** Our engines use "Graceful Degradation." For example, if a patient lacks a lipid panel, the WHO-CVD engine automatically falls back to the BMI-based non-lab chart. If a patient lacks eGFR/ACR, the CKD engine checks their HTN/Diabetes pre-test probability and flags exactly which test they need to order.

**Q: Can we add a new disease score?**
**A:** Yes! Just add a new file (e.g., `engine_asthma.py`) in `/backend/scoring/`, ensure it returns an `EngineResponse` object, and plug it into `orchestrator.py`. The `aggregate_missing_investigations` and `determine_referral` functions will automatically pick up its outputs.

---

## 🚀 Next Steps In-Depth

Now that the backend clinical scoring foundation is rock-solid, our next sprint focuses on integration and user experience.

### 1. Edge-Case Validation
*   **Next Action:** Have a clinician or medical student on the team try to "break" the scoring logic by inputting contradictory edge cases. Add any discovered bugs as unit tests in `test_engines.py` and patch the engines.

### 2. Live Testing & Deployment
*   **Next Action:** Package the application into a Docker container for easier deployment, and conduct user testing with actual primary healthcare workers to evaluate the UX of the frontend dashboard.
