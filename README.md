# AegisCare: Privacy-Tiered Caregiver Alert Portal for Older Adults Living Alone

**Capstone Project — Phase 2 / Review 2 Submission** | **82% Complete**

---

## 📌 Project Overview

**AegisCare** is a privacy-preserving smart-home alerting and monitoring portal designed for older adults living alone. The system operates strictly as an **operational and wellbeing support portal** (not a medical device or emergency medical service).

### Core Problem & Innovation
Older adults living alone often wish to share non-invasive wellbeing status with informal family caregivers, neighbors, and care coordinators without compromising personal autonomy or leaking sensitive medical data. 

AegisCare introduces:
1. **Tiered Privacy Architecture (Tier 0 to Tier 3)**:
   - **Tier 0 (Status Indicator)**: Binary availability indicator (e.g., *Normal / Check Needed*).
   - **Tier 1 (Categorical Summary)**: Category label and high-level non-clinical status.
   - **Tier 2 (Evidence & Trends)**: Operational evidence (e.g., timestamp bounds, counts) and actionable next steps.
   - **Tier 3 (Higher-Detail Contextual Information)**: Higher-detail contextual information, available only when explicitly permitted by the care recipient's consent settings.
   *(Note: AegisCare is strictly an operational and wellbeing support portal. The system does not diagnose diseases, prescribe medication, or recommend clinical treatments. Vitals-related metrics are presented strictly within operational/privacy boundaries, and consent remains the controlling authorization mechanism.)*
2. **Deterministic Rules Engine**: Detects operational anomalies (e.g., missed check-in windows, abnormal nocturnal departures, social isolation, sensor data gaps) without generating medical diagnoses.
3. **Automated Content Linter**: Programmatically strips clinical terminology, raw vital metrics, and diagnostic phraseology before alert rendering.
4. **Dynamic Caregiver Consent Matrix**: Granular, per-category, per-caregiver permissions controlled by the care recipient, enforced server-side.
5. **Auditable Decision Log**: Complete audit trails for every access evaluation and consent update.

---

## 📊 Benchmark Evaluation (Synthetic Datasets)

Evaluated against a reproducible 30-day synthetic telemetry benchmark dataset (3 simulated care recipients, 12 synthetic caregiver persona profiles across 4 roles, 24 generated alerts, 21 ground-truth anomaly events, and 164 tier-filtered caregiver renders; Human Participants = 0).

| Evaluation Metric | Baseline | Review 1 Target | Measured Privacy-Tiered Result | Status |
|---|---|---|---|---|
| **Actionability Rate** | 52.0% | &ge; 90.0% | **100.0%** | **Pass** |
| **Privacy Compliance Rate** | 55.0% | &ge; 95.0% | **100.0%** | **Pass** |
| **Unnecessary Disclosure Rate** | 45.0% | &le; 5.0% | **0.0%** | **Pass** |
| **Alert Delivery Accuracy** | 62.5% | &ge; 90.0% | **100.0%** | **Pass** |
| **Freshness Detection Rate** | 70.0% | &ge; 95.0% | **100.0%** | **Pass** |
| **Alert Recall** | 78.0% | &ge; 90.0% | **100.0%** | **Pass** |
| **Content Linter Violations** | 18 | 0 violations | **0 violations** | **Pass** |

---

## 🏗️ Project Architecture & Structure

```
capstone-project/
├── api/                      # FastAPI backend server (Phase 1 + Phase 2)
│   ├── auth.py               # [Phase 2] JWT auth, PBKDF2 hashing, RBAC
│   ├── database.py           # SQLite / SQLAlchemy ORM + schema migration
│   ├── data_store.py         # DB storage with SHA-256 audit hash chaining
│   ├── main.py               # 31 API endpoints (27 application REST + 4 OpenAPI/docs)
│   ├── mqtt_adapter.py       # [Phase 2] MQTT/IoT ingestion adapter
│   └── routes/               # API sub-routers
├── data/                     # Dataset generators and sample data
│   ├── generate_synthetic.py # Reproducible 30-day telemetry generator
│   ├── generate_advanced_synthetic.py # [Phase 2] Stress-injected benchmark
│   ├── sample_dataset.json   # Benchmark synthetic dataset (2,609 signals)
│   └── advanced_stress_dataset.json  # [Phase 2] Edge case stress dataset
├── docs/                     # Project documentation & review reports
│   ├── review_1_documentation.md # Review 1 audit & verification
│   ├── review_2_documentation.md # [Phase 2] Review 2 audit & verification
│   ├── demo_script.md        # Step-by-step viva & demo guide
│   ├── limitations.md        # Assumptions & scope boundaries
│   ├── requirements.md       # Formal college project specification
│   └── validation.md         # Requirements-to-test traceability matrix
├── engine/                   # Core privacy & rules engine
│   ├── consent_filter.py     # Server-side privacy tier filtering & redaction
│   ├── content_linter.py     # Regex-based medical terminology sanitization
│   ├── ingestion.py          # [Phase 2] HMAC WebHook pipeline & edge handling
│   ├── models.py             # Domain models, audit hash functions
│   ├── rules.py              # Deterministic anomaly detection rules
│   └── tests/                # Automated pytest test suite (135 tests)
├── eval/                     # Evaluation benchmark execution & results
│   ├── metrics.py            # Quantitative evaluation script (5 metrics)
│   ├── advanced_metrics.py   # [Phase 2] Stress evaluation (6 metrics)
│   ├── stakeholder_evaluation.py # [Phase 2] SUS usability protocol
│   └── results_table.md      # Generated benchmark results
├── frontend/                 # React (Vite) Web Portal
│   ├── src/components/       # AlertFeed, FleetDashboard, Audit, Metrics, Consent
│   ├── package.json          # Frontend dependencies
│   └── vite.config.js        # Vite configuration
├── requirements.txt          # Python dependencies (incl. pyjwt, httpx)
└── README.md                 # Project README
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Backend Setup
```bash
# Install Python dependencies
pip install -r requirements.txt

# (Optional) Regenerate synthetic dataset
python data/generate_synthetic.py

# Start the FastAPI backend server
python -m uvicorn api.main:app --port 8000 --host 127.0.0.1 --reload
```
*Backend API will be accessible at: `http://127.0.0.1:8000`*  
*Swagger Documentation: `http://127.0.0.1:8000/docs`*

### 2. Frontend Setup
```bash
cd frontend
npm install
npm run dev
```
*Frontend Portal will be accessible at: `http://localhost:5173`*

---

## 🧪 Running Tests & Evaluation

### Run Automated Unit & Integration Tests (135 Tests — Phase 2)
```bash
python -m pytest engine/tests/ -v
# Expected: 135 passed, 0 failed
```

### Run Quantitative Evaluation Benchmark
```bash
python eval/metrics.py
```

---

## 🛡️ Privacy & Compliance Guarantees
- **Strict Least-Privilege**: Unconsented categories default to Tier 0 or complete withholding.
- **Fail-Safe Revocation**: Immediate mid-stream withholding upon consent revocation.
- **Zero Raw Diagnosis Leak**: All textual alerts pass automated content linting to guarantee non-clinical operational phrasing.
- **Role Constraints**: Even professional roles (care coordinators) cannot view categories without explicit resident consent.
