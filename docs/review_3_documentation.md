# AegisCare — Review 3 Final Capstone Submission Documentation

**Project Title:** AegisCare — Privacy-Tiered Caregiver Alert Portal for Older Adults Living Alone  
**Repository:** [https://github.com/Ruchica07/privacy-tiered-caregiver-alert-portal](https://github.com/Ruchica07/privacy-tiered-caregiver-alert-portal)  
**Academic Standing:**
- **Review 1:** 35 / 35 marks (100%)
- **Review 2:** 32.2 / 35 marks (92%)
- **Current Total:** 67.2 / 70 marks
- **Phase 3 Objective:** Complete the remaining 30 marks to achieve final capstone readiness.

---

## 1. Project Overview & Problem Statement

Older adults living alone face dual challenges: the risk of undetected emergencies (e.g. falls, missed medication, night wandering) and the rapid erosion of autonomy caused by invasive, continuous surveillance. Existing consumer monitoring systems either broadcast unredacted, intimate telemetry to all family members or flood caregivers with false alarms and technical jargon.

**AegisCare** resolves this tension through a **privacy-tiered operational alert architecture**. The system transforms multi-modal IoT sensor telemetry into explainable, non-medical operational alerts while cryptographically enforcing resident consent settings, four distinct caregiver role boundaries, dynamic redaction (Tier 0 through Tier 3), and immutable audit logging.

---

## 2. Review 1 & Review 2 Feedback Resolution

### Review 1 Feedback Addressed:
1. **OAuth2 / OIDC Token Integration:** Developed `api/oidc_auth.py` and `POST /api/auth/oidc/validate`, allowing enterprise IdP tokens (Okta, Azure AD, Auth0) to be validated against standard OIDC claims (`iss`, `aud`, `sub`, `exp`, `role`) with server-side RBAC enforcement.
2. **Subtle Composite Failure Anomaly Generation:** Implemented `eval/composite_stress_eval.py` evaluating 8 compound failure scenarios (drift+noise, duplicate+delayed, network burst, consent restrictions, data gap recovery).

### Review 2 Feedback Addressed:
1. **Granular Unit Testing Documentation:** Created [`docs/testing.md`](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/testing.md) documenting all 158 tests across 13 test suites with positive, negative, and edge-case breakdowns.
2. **Error Boundary & Failure Handling Matrix:** Created [`docs/error_boundaries.md`](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/error_boundaries.md) mapping 28+ failure modes from input validation to safe user-facing state and audit logging.
3. **Comprehensive API Reference:** Created [`docs/api.md`](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/api.md) documenting all 34 registered FastAPI routes (30 application REST + 4 docs routes).
4. **Database Schema Documentation:** Created [`docs/database_schema.md`](file:///c:/Users/Administrator/Desktop/capstone%20project%20clg/docs/database_schema.md) detailing all 6 SQLAlchemy tables, indexes, and privacy relevance.
5. **Expanded Code Comments:** Added comprehensive architectural docstrings explaining the security rationale across all modules.

---

## 3. End-to-End System Architecture

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

## 4. Privacy-Tiered Disclosure Model

| Disclosure Tier | Designation | Information Disclosed | Authorized Caregiver Roles |
| :---: | :--- | :--- | :--- |
| **Tier 0** | **Withheld / Redacted Indicator** | Confirmation that system is monitoring; alert details completely withheld. | Neighbor (on unconsented categories), Revoked Consent. |
| **Tier 1** | **Standard Operational Alert** | High-level operational category, severity badge, and suggested non-medical next step. | Secondary Caregiver, Trusted Neighbor (urgent safety only). |
| **Tier 2** | **Detailed Contextual Timeline** | Operational trend timelines, adherence durations, departure hours, and baseline comparison. | Primary Caregiver (e.g. adult daughter). |
| **Tier 3** | **Higher-Detail Contextual Summary** | Qualitative wellness overview summaries across historical monitoring windows. | Professional Care Coordinator (strictly when consented). |

> [!NOTE]
> **Privacy-Safe Tier 3 Definition:** In accordance with AegisCare's non-medical boundary, Tier 3 provides *higher-detail contextual information available only when explicitly permitted by care recipient consent settings*. It does **NOT** provide clinical diagnosis, medical treatment, or prescriptive drug dosage recommendations.

---

## 5. Verification & Testing Summary

* **Automated Backend Test Suite:** **158 passed, 0 failed** (`python -m pytest engine/tests/ -v`)
* **Frontend Production Build:** **Compiled in 4.23s with 0 errors** (`npm --prefix frontend run build`)
* **Composite Stress Evaluation:** **8/8 compound scenarios passed (100.0%)**
* **Local Ingestion Load Benchmark:** Tested across **100, 500, 1,000, and 5,000 events** with sub-millisecond per-event latency.
* **Cryptographic Tamper Verification:** Verified continuous SHA-256 chain integrity on `data/portal.db`.

---

## 6. Research Limitations & Future Work

1. **Simulated Usability Boundary:** Human participants = 0. All usability metrics are generated from an automated simulated stakeholder evaluation harness. Real human trials remain future work pending IRB approval.
2. **Sandbox Notification Adapters:** Web Push and SMS adapters operate in a sandbox simulation mode. Live SMS or push notifications require external gateway API keys (e.g. Twilio, Firebase Cloud Messaging).
3. **Enterprise OIDC Deployment:** The OIDC adapter implements standard claim validation; connecting to live enterprise identity providers (Okta, Azure AD) requires organization-specific client secrets and endpoints.
4. **In-Memory Idempotency Cache:** Notification deduplication uses an in-memory registry for demonstration; production deployment requires distributed transactional backing (e.g. Redis).
