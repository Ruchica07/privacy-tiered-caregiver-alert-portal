# AegisCare: Privacy-Tiered Caregiver Alert Portal for Older Adults Living Alone

**Capstone Project — Phase 3 / Review 3 Final Submission**  
**Academic Standing:** Review 1: **35 / 35** | Review 2: **32.2 / 35** | Current Total: **67.2 / 70** | Review 3 Goal: **30 / 30 Remaining**

---

## 📌 1. Project Overview & Problem Statement

Older adults living alone face high risks from undetected emergency situations (such as falls, missed medication, nocturnal wandering, or acute social isolation) while simultaneously desiring to protect their personal privacy and autonomy. Existing smart-home systems either indiscriminately broadcast unredacted, intimate telemetry to family members or flood caregivers with false alarms and technical jargon.

**AegisCare** resolves this conflict through a **privacy-tiered operational alert portal**. The system transforms multi-modal IoT sensor telemetry into explainable, non-medical operational alerts while enforcing:
- Granular, resident-controlled consent matrices per category and caregiver.
- Dynamic disclosure tiers (Tier 0 through Tier 3) enforced strictly on the server.
- Four distinct caregiver role boundaries (Primary, Secondary, Neighbor, Coordinator).
- Programmatic content safety linting to eliminate clinical/prescriptive phraseology.
- Multi-channel notification dispatching with Web Push and SMS sandbox adapters.
- Cryptographic SHA-256 tamper-evident audit chaining.

> [!NOTE]
> **Non-Medical Boundary Disclaimer:** AegisCare operates strictly as an operational and wellbeing support portal. The system is not a medical device, does not provide medical diagnoses, does not prescribe treatments or medication dosages, and is not a substitute for professional clinical care.

---

## 🏗️ 2. System Architecture

```
                                  TELEMETRY SOURCES
                 ┌──────────────────────────────────────────────────┐
                 │ WebHooks (HMAC-SHA256) │ MQTT Topics │ Synthetic │
                 └──────────────────────────────────────────────────┘
                                          │
                                          ▼
                             EDGE INGESTION PIPELINE
                 ┌──────────────────────────────────────────────────┐
                 │ • HMAC-SHA256 Signature Verification             │
                 │ • Sliding-Window Deduplication (O(1) Hash)       │
                 │ • 60s Future Timestamp Clock Skew Rejection      │
                 │ • Exponential Moving Average Noise Smoothing     │
                 │ • Sensor Baseline Drift Advisory Detection       │
                 └──────────────────────────────────────────────────┘
                                          │
                                          ▼
                               PERSISTENCE & STORAGE
                 ┌──────────────────────────────────────────────────┐
                 │ SQLite + SQLAlchemy ORM (signals, recipients)    │
                 └──────────────────────────────────────────────────┘
                                          │
                                          ▼
                             DETERMINISTIC RULES ENGINE
                 ┌──────────────────────────────────────────────────┐
                 │ 7 Explainable Anomaly Rules across 6 Categories  │
                 │ (No Black-Box ML; Strict Operational Bounds)     │
                 └──────────────────────────────────────────────────┘
                                          │
                                          ▼
                             PRIVACY & CONSENT FILTER
                 ┌──────────────────────────────────────────────────┐
                 │ Matrix Gating (Resident Consent x Caregiver Role)│
                 │ Dynamic Redaction: Tier 0 (Redacted) to Tier 3   │
                 └──────────────────────────────────────────────────┘
                                          │
                                          ▼
                            CONTENT SAFETY LINTER PASS
                 ┌──────────────────────────────────────────────────┐
                 │ 42+ Banned Medical Terms Stripped & Sanitized    │
                 │ (Applied to Evidence Summary AND Action Steps)   │
                 └──────────────────────────────────────────────────┘
                                          │
                                          ▼
                           LIVE NOTIFICATION DISPATCHER
                 ┌──────────────────────────────────────────────────┐
                 │ • Deterministic Idempotency Key Deduplication    │
                 │ • Bounded Retries with Exponential Backoff       │
                 │ • Web Push Sandbox Adapter (SIMULATION)          │
                 │ • SMS Sandbox Adapter (SIMULATION)               │
                 └──────────────────────────────────────────────────┘
                                          │
                                          ▼
                          TAMPER-EVIDENT SHA-256 AUDIT CHAIN
                 ┌──────────────────────────────────────────────────┐
                 │ Continuous Hash Chain: prev_hash -> entry_hash   │
                 │ Cryptographic Non-Repudiation & Verification API │
                 └──────────────────────────────────────────────────┘
```

---

## 🛠️ 3. Technology Stack

- **Backend:** Python 3.10+, FastAPI, Pydantic, Starlette Middleware
- **Persistence:** SQLite, SQLAlchemy ORM
- **Security & Cryptography:** PyJWT (HS256/RS256), PBKDF2-HMAC-SHA256 password hashing, HMAC-SHA256 webhook signatures, SHA-256 tamper-evident hash chaining
- **External Interfaces:** HTTP REST (30 application endpoints), WebHooks, MQTT broker adapter
- **Frontend Dashboard:** React 18, Vite, Vanilla CSS design system (Fleet overview, Alert feeds, Audit verifier, Consent manager)
- **Testing & Benchmark:** Pytest (158 automated tests), custom stress evaluation & load testing harnesses

---

## 📁 4. Project Directory Structure

```
capstone-project/
├── api/                      # FastAPI backend server
│   ├── auth.py               # JWT authentication, PBKDF2 hashing, server-side RBAC
│   ├── oidc_auth.py          # [Phase 3] Enterprise OIDC token validator & adapter
│   ├── middleware.py         # [Phase 3] Correlation ID & structured error middleware
│   ├── database.py           # SQLite database & SQLAlchemy ORM models
│   ├── data_store.py         # Data access layer & SHA-256 audit chaining
│   ├── main.py               # 34 registered routes (30 REST + 4 OpenAPI/docs)
│   ├── mqtt_adapter.py       # MQTT IoT ingestion adapter
│   └── routes/               # Modular router directory
├── engine/                   # Core privacy, rules, and notification engine
│   ├── consent_filter.py     # Privacy tier redaction & consent lookup
│   ├── content_linter.py     # 42+ banned medical terms regex sanitizer
│   ├── ingestion.py          # Edge ingestion, HMAC, deduplication, EMA noise filter
│   ├── models.py             # Domain models & audit hash utilities
│   ├── notification_dispatcher.py # [Phase 3] Live notification dispatcher & sandbox adapters
│   ├── rules.py              # 7 deterministic anomaly detection rules
│   └── tests/                # 13 automated test suites (158 tests passing)
├── eval/                     # Evaluation, stress testing, and load benchmarks
│   ├── composite_stress_eval.py # [Phase 3] 8 compound failure scenarios
│   ├── load_test.py          # [Phase 3] Local load benchmark (100–5000 events)
│   ├── metrics.py            # Phase 1 baseline evaluation suite
│   ├── advanced_metrics.py   # Phase 2 stress evaluation suite
│   └── stakeholder_evaluation.py # Simulated SUS usability evaluation
├── data/                     # Datasets and SQLite database
│   ├── sample_dataset.json   # 30-day multi-resident baseline dataset
│   ├── advanced_stress_dataset.json # Phase 2 noise & packet-drop dataset
│   └── portal.db             # Operational SQLite database
├── docs/                     # Comprehensive technical documentation
│   ├── api.md                # [Phase 3] Complete REST API endpoint reference
│   ├── database_schema.md    # [Phase 3] Database tables, columns, indexes
│   ├── testing.md            # [Phase 3] Granular unit & regression testing documentation
│   ├── error_boundaries.md   # [Phase 3] Error handling & failure matrix
│   ├── stakeholder_protocol.md # [Phase 3] Simulated SUS usability protocol (Human=0)
│   ├── phase3_completion_audit.md # [Phase 3] Final capstone verification audit
│   ├── review_3_documentation.md # [Phase 3] Review 3 submission report
│   ├── review_2_documentation.md # Review 2 submission report
│   └── limitations.md        # Assumptions, boundaries, and future work
└── frontend/                 # React 18 + Vite dashboard
    ├── src/components/       # AlertFeed, FleetDashboard, AuditVerifier, ConsentMatrix
    └── package.json          # Node dependencies
```

---

## 🚀 5. Getting Started & Setup Instructions

### Prerequisites
- Python 3.10+
- Node.js 18+ and npm

### 1. Backend Startup
```bash
# Install backend dependencies
pip install -r requirements.txt

# Run the complete test suite (158 tests)
python -m pytest engine/tests/ -v

# Start FastAPI dev server on port 8000
python -m uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
API Documentation will be available at: [http://localhost:8000/docs](http://localhost:8000/docs)

### 2. Frontend Startup
```bash
# Navigate to frontend directory & install dependencies
cd frontend
npm install

# Run frontend dev server
npm run dev

# Or build production bundle
npm run build
```
Frontend will be available at: [http://localhost:5173](http://localhost:5173)

---

## 🔒 6. Privacy-Tiered Disclosure Model

| Disclosure Tier | Privacy-Safe Definition | Typical Content |
| :---: | :--- | :--- |
| **Tier 0** | **Withheld / Redacted Indicator** | Generic system active indicator; specific anomaly and context are completely withheld. |
| **Tier 1** | **Standard Operational Alert** | High-level category, severity badge, and non-medical suggested next action. |
| **Tier 2** | **Detailed Contextual Timeline** | Operational trend durations, departure hours, and baseline comparison. |
| **Tier 3** | **Higher-Detail Contextual Summary** | Qualitative wellness summary over historical windows, available strictly when consented. |

---

## 👥 7. Pre-Seeded Demonstration User Accounts

| Username | Password | Caregiver ID | Role | Assigned Residents |
| :--- | :--- | :--- | :--- | :--- |
| `jane.smith` | `AegisCare2026!` | `cg_001` | Primary Caregiver | Eleanor Vance (`cr_001`) |
| `bob.smith` | `AegisCare2026!` | `cg_002` | Secondary Caregiver | Eleanor Vance (`cr_001`) |
| `maria.garcia` | `AegisCare2026!` | `cg_003` | Neighbor / Community | Eleanor Vance (`cr_001`) |
| `dr.sarah.chen` | `AegisCare2026!` | `cg_004` | Care Coordinator | All Residents (`cr_001`, `cr_002`, `cr_003`) |
| `admin` | `AegisCare2026!` | `admin_001` | System Administrator | All Residents |

---

## 📊 8. Verified Benchmark & Evaluation Metrics

| Metric | Target Baseline | Measured Result | Verification Method | Status |
| :--- | :---: | :---: | :--- | :---: |
| **Automated Test Suite** | 100% Pass | **158 / 158 Passed (100.0%)** | `python -m pytest engine/tests/ -v` | **PASS** |
| **Frontend Production Build** | Zero Errors | **Clean Build in 4.23s** | `npm --prefix frontend run build` | **PASS** |
| **Actionability Rate** | $\ge 90.0\%$ | **100.0%** | `python eval/metrics.py` | **PASS** |
| **Privacy Compliance Rate** | $\ge 95.0\%$ | **100.0%** | `python eval/metrics.py` | **PASS** |
| **Unnecessary Disclosure Rate** | $\le 5.0\%$ | **0.0%** | `python eval/metrics.py` | **PASS** |
| **Alert Delivery Accuracy** | $\ge 90.0\%$ | **100.0%** | `python eval/metrics.py` | **PASS** |
| **Content Linter Violations** | 0 violations | **0 violations** | `python eval/metrics.py` | **PASS** |
| **Composite Stress Pass Rate** | $\ge 90.0\%$ | **8 / 8 Passed (100.0%)** | `python eval/composite_stress_eval.py` | **PASS** |
| **Audit Chain Tamper Detection**| 100% Detection | **100.0% Verified** | `GET /api/audit/verify` | **PASS** |
| **Human Usability Participants**| Documented Boundary | **0 (Strictly Simulated SUS)**| [`docs/stakeholder_protocol.md`](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/stakeholder_protocol.md) | **VERIFIED** |

---

## 📖 9. Detailed Documentation Links

- **[REST API Reference](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/api.md)** — OpenAPI schemas, parameters, and responses for all 31 routes.
- **[Database Schema](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/database_schema.md)** — Relational structure, columns, indexes, and privacy relevance.
- **[Testing & Regression Documentation](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/testing.md)** — Granular test breakdown across all 158 automated test cases.
- **[Error Boundaries & Failure Matrix](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/error_boundaries.md)** — Input validations and system mitigations for 28+ error modes.
- **[Simulated Stakeholder Protocol](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/stakeholder_protocol.md)** — Usability protocol, personas, tasks, and Human=0 boundary.
- **[Phase 3 Completion Audit](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/phase3_completion_audit.md)** — Traceability matrix across all capstone and review deliverables.
- **[Review 3 Submission Report](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/review_3_documentation.md)** — Comprehensive academic capstone report.
