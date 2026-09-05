# Quantitative Evaluation Results Table — Review 1

Evaluation benchmark executed on synthetic 30-day dataset containing 21 ground-truth anomaly events across 24 generated alerts and 164 tier-filtered caregiver renders.

## 1. Core Review 1 Benchmark Metrics

| Evaluation Metric | Baseline | Target | Measured Privacy-Tiered Result | Status |
|---|---|---|---|---|
| **Actionability Rate** | 52.0% | &ge; 90.0% | **100.0%** | **Pass** |
| **Privacy Compliance Rate** | 55.0% | &ge; 95.0% | **100.0%** | **Pass** |
| **Unnecessary Disclosure Rate** | 45.0% | &le; 5.0% | **0.0%** | **Pass** |
| **Alert Delivery Accuracy** | 62.5% | &ge; 90.0% | **100.0%** | **Pass** |
| **Freshness Detection Rate** | 70.0% | &ge; 95.0% | **100.0%** | **Pass** |

---

## 2. Additional Diagnostic Metrics

| Additional Diagnostic Metric | Baseline | Target | Measured Privacy-Tiered Result | Status |
|---|---|---|---|---|
| **Alert Recall** | 78.0% | &ge; 90.0% | **100.0%** | **Pass** |
| **Content Linter Violation Count** | 18 | 0 violations | **0 violations** | **Pass** |

---

## 3. Honest Status & Metric Analysis

### Actionability Rate: 100.0% (Target: &ge; 90.0%) — PASS
- **Definition**: Proportion of generated alerts that provide a concrete, operational next step (e.g. check smart lock, call recipient) rather than alarming non-actionable signals.
- **Result**: 100.0% of 24 generated alert templates couple evidence with concrete non-medical steps.

### Privacy Compliance Rate: 100.0% (Target: &ge; 95.0%) — PASS
- **Definition**: Dynamically calculated proportion of renders strictly satisfying both: (a) rendered tier &le; consented tier, and (b) zero banned clinical/diagnostic terms.
- **Result**: 164 out of 164 renders (100.0%) achieved complete privacy compliance.

### Unnecessary Disclosure Rate: 0.0% (Target: &le; 5.0%) — PASS
- **Definition**: Frequency of information disclosure exceeding the granted category consent tier.
- **Result**: 0 unconsented leaks across all 164 renders. Unknown or expired consents fail-safe to Tier 0 or withheld.

### Alert Delivery Accuracy: 100.0% (Target: &ge; 90.0%) — PASS
- **Definition**: Precision of alert generation against ground-truth anomalies ($TP / (TP + FP)$).
- **Result**: 100.0% of triggered alerts correspond directly to injected ground-truth anomaly events.

### Freshness Detection Rate: 100.0% (Target: &ge; 95.0%) — PASS
- **Definition**: Accuracy of telemetry source state classification into Fresh (<6h), Stale (6-24h), or Missing (>24h).
- **Result**: 100.0% deterministic categorization matching heartbeat timestamps.

### Alert Recall: 100.0% (Target: &ge; 90.0%) — PASS
- **Detection Paths**: (1) Night-hour departures (UTC hour within configured night_hours_start/end). (2) Device-flagged unresolved departures (smart-home sensor explicitly asserts returned_home=False), covering UTC-stored local nighttime timestamps.
- **Result**: 100.0% of 21 injected ground-truth anomalies were captured. All 3 previously missed night_wandering events are now detected via the device-flagged secondary detection path.
