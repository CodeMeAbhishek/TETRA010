# TETRA010: Clinical Decision Support System

## 1. Overview
This repository contains a clinical decision support system for primary healthcare. It identifies and stratifies the risk of lifestyle diseases. The core system operates locally and uses a deterministic rules engine. 

## 2. Architecture
The system uses a strict two-layer architecture to ensure medical accuracy.

* **Layer 1: Deterministic Scoring Engine**
  The system calculates clinical scores using Python functions. These functions strictly follow established medical guidelines. The Large Language Model (LLM) does not calculate any clinical scores.

* **Layer 2: LLM Orchestration**
  The LLM receives the calculated scores as structured JSON data. It translates these scores into patient-friendly explanations in multiple languages. It also generates referral notes based on the deterministic data.

## 3. Supported Clinical Modules
The scoring engine evaluates risk for five conditions:

* **Diabetes:** Uses the Indian Diabetes Risk Score (MDRF-IDRS).
* **Cardiovascular Disease:** Uses the WHO South Asia Risk Charts (2019). It supports both laboratory and non-laboratory data.
* **Hypertension:** Uses the 2017 ACC/AHA guidelines. It calculates blood pressure categories and treatment timelines.
* **Chronic Kidney Disease (CKD):** Uses the CKD-EPI 2021 equation and the KDIGO GxA heatmap.
* **Stroke:** Uses the ACC/AHA acute stroke and secondary prevention guidelines.

## 4. Project Structure
* `backend/scoring/`: The deterministic clinical engines.
* `backend/api.py`: The FastAPI server.
* `backend/orchestrator.py`: The integration layer for the LLM API.
* `frontend/`: The user interface (HTML, CSS, JavaScript).
* `test_engines.py`: The unit test suite.
* `references/`: The medical guidelines and source documents.

## 5. How to Run the Application

**Step 1: Install dependencies**
```bash
pip install fastapi uvicorn pydantic openai python-dotenv
```

**Step 2: Configure the API key**
Copy the template file to create your environment configuration.
```bash
cp .env.example .env
```
Open the `.env` file and add your NVIDIA NIM or OpenRouter API key.

**Step 3: Start the server**
```bash
python main.py
```

**Step 4: Access the application**
Open a web browser and go to `http://localhost:8000/`.

## 6. How to Run Tests
The repository includes unit tests to validate the clinical logic against medical guidelines. Run the tests with this command:
```bash
python -m unittest test_engines.py -v
```
