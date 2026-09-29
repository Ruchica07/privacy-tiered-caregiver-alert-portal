# AegisCare — Comprehensive Testing Documentation (Phase 3)

This document provides a granular, file-by-file technical breakdown of all automated test suites, testing methodologies, error boundaries, regression suites, and evaluation harnesses in AegisCare.

---

## 1. Test Suite Execution & Verified Baseline

### Standard Backend Test Runner Command:
```bash
python -m pytest engine/tests/ -v
```

### Full Evaluation Suite Execution:
```bash
python eval/composite_stress_eval.py
python eval/load_test.py
python eval/metrics.py
python eval/advanced_metrics.py
python eval/stakeholder_evaluation.py
```

### Frontend Production Build Command:
```bash
npm --prefix frontend run build
```

---

## 2. Test File Inventory & Granular Breakdown

| Test File | Total Tests | Functionality Tested | Test Categories & Edge Cases |
| :--- | :---: | :--- | :--- |
| **`test_content_linter.py`** | **48** | Non-medical terminology enforcement, 42+ banned medical/clinical patterns, regex tokenization, and fallback sanitization. | **Positive:** Compliant non-medical phrases pass unmodified.<br>**Negative:** Clinical diagnoses ("stroke", "hypertension"), medication names ("lisinopril", "insulin"), and raw vitals rejected.<br>**Edge Cases:** Punctuation splitting, mixed capitalization, borderline phrasing. |
| **`test_consent_filter.py`** | **24** | Dynamic Tier 0–3 disclosure redaction, caregiver role permissions, time-based consent expiration, and access summaries. | **Positive:** Primary caregiver receives Tier 2; Coordinator receives Tier 3 when consented.<br>**Negative:** Unconsented categories withheld (Tier 0).<br>**Edge Cases:** Expired consent timestamps, mid-stream consent revocation. |
| **`test_rules.py`** | **17** | Deterministic anomaly detection rules across 6 signal categories, explainable alert generation, and data gap triggers. | **Positive:** Missed check-in, night wandering, activity drop correctly fire alerts.<br>**Negative:** Normal baseline activity produces 0 alerts.<br>**Edge Cases:** Data storm (multiple concurrent anomalies remain separate operational alerts), total sensor outage. |
| **`test_database_and_e2e.py`** | **17** | SQLite CRUD persistence, SQLAlchemy ORM models, differential disclosure across all 4 caregiver roles, and edge-case lifecycle. | **Positive:** End-to-end signal ingestion to alert rendering across 4 roles.<br>**Negative:** Professional coordinator cannot bypass resident consent.<br>**Edge Cases:** Sensor gap vs health event distinction, data storm non-synthesis. |
| **`test_webhook_and_ingestion.py`** | **10** | HMAC-SHA256 signature verification, multi-vendor schema normalization, clock-skew filtering, EMA noise smoothing, and baseline drift. | **Positive:** Valid signatures accepted, Home Assistant schema parsed.<br>**Negative:** Tampered body or wrong secret rejected with HTTP 401; future timestamps (>60s) rejected with HTTP 422.<br>**Edge Cases:** Duplicate `event_id` sliding-window suppression. |
| **`test_auth_and_rbac.py`** | **8** | PyJWT HS256 token lifecycle, PBKDF2 salted password hashing, server-side RBAC, and anti-impersonation guards. | **Positive:** Valid credentials generate signed JWT; authorized caregiver accesses alerts.<br>**Negative:** Tampered token signature raises HTTP 401; caregiver requesting another caregiver's alerts blocked with HTTP 403. |
| **`test_notification_dispatcher.py`** | **8** | Multi-channel notification pipeline (Web Push & SMS Sandbox Adapters), idempotency deduplication, retry policy, tier redaction. | **Positive:** Permitted alerts dispatched with sandbox metadata.<br>**Negative:** Unconsented categories withheld at dispatcher boundary.<br>**Edge Cases:** Duplicate dispatch suppressed by idempotency key; bounded exponential retry on transient failure; double linter sanitization on summary + action. |
| **`test_oidc_auth.py`** | **6** | Enterprise-ready OpenID Connect (OIDC) Bearer token validation, standard claims verification, and role mapping. | **Positive:** Valid OIDC claims (`sub`, `iss`, `aud`, `exp`, `role`) validated into caregiver profile.<br>**Negative:** Expired token, untrusted issuer, audience mismatch, tampered signature, and invalid role claims rejected with HTTP 401. |
| **`test_observability_and_errors.py`** | **5** | Correlation ID tracking (`X-Correlation-ID`) on all responses, client propagation, and standardized error envelopes. | **Positive:** Unique correlation ID auto-generated and propagated.<br>**Negative:** Validation (422), Authentication (401), Authorization (403), and Not Found (404) return standardized error envelope without stack trace leakage. |
| **`test_advanced_synthetic_eval.py`** | **4** | Noise tolerance, sensor drift baseline tracking, and 30-day multi-resident synthetic dataset generation. | **Positive:** Ground-truth anomaly injection verified across 21 benchmark events. |
| **`test_tamper_evident_audit.py`** | **4** | Cryptographic SHA-256 hash chaining (`prev_hash` $\to$ `entry_hash`), deterministic hashing, and tamper detection. | **Positive:** Sequential chain passes verification.<br>**Negative:** Altering a record payload in SQLite or deleting an intermediate row is immediately detected. |
| **`test_phase3_regression.py`** | **4** | End-to-end Phase 3 integration: Ingestion $\to$ Rules $\to$ Privacy $\to$ Notifications $\to$ Audit, and composite stress runner. | **Positive:** 100% pass on 8 composite stress scenarios; live dispatch endpoint tested via FastAPI TestClient. |
| **`test_mqtt_and_fleet.py`** | **3** | IoT MQTT topic parsing (`aegiscare/{id}/{type}`), message ingestion pipeline, and coordinator fleet aggregation. | **Positive:** MQTT payload mapped to normalized signal; fleet overview aggregates alerts and freshness. |
| **Total Test Suite** | **158** | **100% Automated Coverage** | **All 158 Tests Pass with Zero Regressions** |

---

## 3. Evaluation & Stress Test Suite Execution

### 3.1 Composite Stress Evaluation (`eval/composite_stress_eval.py`)
Evaluates 8 compound failure scenarios:
1. Duplicate + Delayed Event (Idempotency + clock skew tolerance)
2. Out-of-Order + Stale Telemetry (Chronological sorting integrity)
3. Missing Field + Malformed Payload (Edge schema isolation)
4. Sensor Drift + High-Frequency Noise (EMA filter + drift advisory)
5. Network Interruption + Packet Burst (Data storm responsiveness)
6. Multiple Simultaneous Anomalies (Non-medical separation)
7. Consent Restriction + Alert Generation (Dispatch privacy boundary)
8. Sensor Data Gap + Subsequent Recovery (System alert auto-clearing)

* **Output Artifacts:** `eval/phase3_stress_results.json`, `eval/phase3_stress_report.md`
* **Pass Rate:** **8/8 Scenarios Passed (100.0%)**

### 3.2 Ingestion Load Benchmark (`eval/load_test.py`)
Benchmarks local ingestion throughput and p95 latency across 100, 500, 1,000, and 5,000 events in an isolated test environment.
* **Output Artifacts:** `eval/load_test_results.json`, `eval/load_test_report.md`
* **Performance:** Sub-millisecond latency per event; zero packet loss.
