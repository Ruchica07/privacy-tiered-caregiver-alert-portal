# AegisCare — Database Schema & Data Models Documentation (Phase 3)

This document provides complete technical documentation of the SQLite relational database schema and SQLAlchemy ORM models powering the AegisCare portal (`data/portal.db`).

---

## 1. Entity-Relationship Overview

```
 ┌───────────────────┐       1:N       ┌───────────────────┐
 │  care_recipients  │ ───────────────>│  consent_records  │
 └───────────────────┘                 └───────────────────┘
           │ 1:N                                 │
           │                                     │ Constrains Access
           ├───────────────────┐                 │
           │                   │                 ▼
           ▼                   ▼        ┌───────────────────┐
 ┌───────────────────┐ ┌───────────────┐│      alerts       │
 │      signals      │ │  caregivers   │└───────────────────┘
 └───────────────────┘ └───────────────┘         │
           │                   │                 │
           └───────────────────┼─────────────────┘
                               │
                               ▼
                     ┌───────────────────┐
                     │     audit_log     │ (SHA-256 Chained)
                     └───────────────────┘
```

---

## 2. Table Specifications

### 2.1 `care_recipients`
* **Purpose:** Stores demographic profiles, activity baselines, check-in windows, and hardware heartbeat expectations for older adults living alone.
* **Primary Key:** `id` (VARCHAR 64)
* **Privacy Sensitivity:** HIGH (Resident identity and baseline behavior norms)

| Column Name | Type | Nullable | Indexed | Description & Constraints |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `VARCHAR(64)` | No | Yes (PK) | Unique recipient identifier (e.g. `cr_001`). |
| `name` | `VARCHAR(128)` | No | No | Full name of the resident (e.g. "Eleanor Vance"). |
| `baseline_activity_mean` | `FLOAT` | Yes | No | Statistical mean daily activity score (default `50.0`). |
| `baseline_activity_stddev` | `FLOAT` | Yes | No | Standard deviation of daily activity (default `10.0`). |
| `expected_checkin_window_hours` | `FLOAT` | Yes | No | Nominal interval between active check-ins (default `4.0`). |
| `expected_medication_window_hours`| `FLOAT` | Yes | No | Nominal interval between medication events (default `12.0`). |
| `night_hours_start` | `INTEGER` | Yes | No | Night safety window start hour in 24h format (default `22`). |
| `night_hours_end` | `INTEGER` | Yes | No | Night safety window end hour in 24h format (default `6`). |
| `social_contact_expected_days` | `INTEGER` | Yes | No | Maximum expected interval between social interactions (default `3`). |
| `device_heartbeat_expected_hours` | `FLOAT` | Yes | No | Sensor gateway keep-alive reporting interval (default `2.0`). |

---

### 2.2 `caregivers`
* **Purpose:** Stores caregiver profiles, role classifications, and assigned resident rosters.
* **Primary Key:** `id` (VARCHAR 64)
* **Privacy Sensitivity:** MEDIUM (Caregiver contact identity and role privileges)

| Column Name | Type | Nullable | Indexed | Description & Constraints |
| :--- | :--- | :---: | :---: | :--- |
| `id` | `VARCHAR(64)` | No | Yes (PK) | Unique caregiver identifier (e.g. `cg_001`). |
| `name` | `VARCHAR(128)` | No | No | Caregiver full name (e.g. "Jane Smith"). |
| `role` | `VARCHAR(64)` | No | No | Role classification: `primary_caregiver`, `secondary_caregiver`, `neighbor_community`, `care_coordinator_professional`, `admin`. |
| `care_recipient_ids_json` | `TEXT` | Yes | No | JSON array of assigned care recipient IDs (e.g. `["cr_001"]`). |

---

### 2.3 `consent_records`
* **Purpose:** Implements granular resident consent settings dictating maximum allowable disclosure tiers per caregiver and information category.
* **Primary Key:** `consent_id` (VARCHAR 64)
* **Privacy Sensitivity:** CRITICAL (Governs all server-side redaction and data disclosure)

| Column Name | Type | Nullable | Indexed | Description & Constraints |
| :--- | :--- | :---: | :---: | :--- |
| `consent_id` | `VARCHAR(64)` | No | Yes (PK) | Unique consent rule identifier. |
| `care_recipient_id` | `VARCHAR(64)` | No | Yes | Associated care recipient identifier. |
| `caregiver_id` | `VARCHAR(64)` | No | Yes | Target caregiver identifier granted access. |
| `category` | `VARCHAR(64)` | No | No | Information category: `activity_engagement`, `location_safety`, `social_isolation_signal`, `medication_adherence`, `vitals_summary`, `routine_consistency`. |
| `max_tier` | `INTEGER` | Yes | No | Maximum permitted disclosure tier ($0 \le \text{tier} \le 3$). |
| `consent_status` | `VARCHAR(32)` | Yes | No | Current status: `granted`, `revoked`, `pending`. |
| `granted_at` | `VARCHAR(64)` | Yes | No | ISO 8601 timestamp when consent was granted. |
| `expires_at` | `VARCHAR(64)` | Yes | No | ISO 8601 timestamp when consent expires (`NULL` for permanent). |
| `override_reason` | `TEXT` | Yes | No | Optional documentation for emergency or administrative override. |

---

### 2.4 `signals`
* **Purpose:** Normalized time-series repository of IoT sensor readings, active check-ins, and gateway heartbeats.
* **Primary Key:** `signal_id` (VARCHAR 64)
* **Privacy Sensitivity:** HIGH (Raw time-series behavior signals)

| Column Name | Type | Nullable | Indexed | Description & Constraints |
| :--- | :--- | :---: | :---: | :--- |
| `signal_id` | `VARCHAR(64)` | No | Yes (PK) | Unique signal event identifier. |
| `care_recipient_id` | `VARCHAR(64)` | No | Yes | Associated care recipient identifier. |
| `signal_type` | `VARCHAR(64)` | No | Yes | Type: `check_in`, `activity_score`, `medication_event`, `location_event`, `social_contact`, `vitals_reading`, `device_heartbeat`. |
| `timestamp` | `VARCHAR(64)` | No | Yes | ISO 8601 UTC timestamp of signal event. |
| `value` | `FLOAT` | Yes | No | Numerical measurement or score (if applicable). |
| `metadata_json` | `TEXT` | Yes | No | JSON object with context (e.g. `{"left_home": true, "returned_home": false}`). |

---

### 2.5 `alerts`
* **Purpose:** Stores explainable operational alerts generated by the deterministic rules engine.
* **Primary Key:** `alert_id` (VARCHAR 64)
* **Privacy Sensitivity:** HIGH (Contains non-redacted master alert details before role filtering)

| Column Name | Type | Nullable | Indexed | Description & Constraints |
| :--- | :--- | :---: | :---: | :--- |
| `alert_id` | `VARCHAR(64)` | No | Yes (PK) | Unique alert identifier (e.g. `alt_001`). |
| `care_recipient_id` | `VARCHAR(64)` | No | Yes | Associated care recipient identifier. |
| `alert_type` | `VARCHAR(64)` | No | No | Classification: `adherence_alert`, `pattern_alert`, `safety_alert`, `isolation_alert`, `data_gap`. |
| `category` | `VARCHAR(64)` | No | No | Category mapping matching consent records. |
| `severity` | `VARCHAR(32)` | No | No | Severity ranking: `low`, `medium`, `high`, `critical`. |
| `rule_fired` | `VARCHAR(128)`| No | No | Specific deterministic rule name (e.g. `missed_checkin`, `night_wandering`). |
| `evidence_summary` | `TEXT` | No | No | Human-readable non-medical evidence explanation. |
| `generated_at` | `VARCHAR(64)` | No | Yes | ISO 8601 UTC alert generation timestamp. |
| `requires_tier` | `INTEGER` | Yes | No | Minimum disclosure tier required to view full evidence ($0 \dots 3$). |
| `is_data_gap` | `BOOLEAN` | Yes | No | True if alert represents a hardware/connectivity gap rather than a wellness event. |
| `trend_info` | `TEXT` | Yes | No | Contextual trend explanation (Tier 2/3). |
| `clinical_note` | `TEXT` | Yes | No | Qualitative wellness summary note (Tier 3 only). |
| `evidence_data_json` | `TEXT` | Yes | No | JSON structured evidence parameters for audit drill-down. |
| `actionable_step` | `TEXT` | Yes | No | Suggested non-medical next step for caregivers. |

---

### 2.6 `audit_log`
* **Purpose:** Cryptographic SHA-256 tamper-evident hash chain logging all data disclosures, ingestion events, consent updates, and notification dispatches.
* **Primary Key:** `audit_id` (VARCHAR 64)
* **Privacy Sensitivity:** CRITICAL (Immutable compliance record)

| Column Name | Type | Nullable | Indexed | Description & Constraints |
| :--- | :--- | :---: | :---: | :--- |
| `audit_id` | `VARCHAR(64)` | No | Yes (PK) | Unique audit entry identifier. |
| `timestamp` | `VARCHAR(64)` | No | Yes | ISO 8601 UTC timestamp of the logged event. |
| `event_type` | `VARCHAR(64)` | No | Yes | Event classification: `alert_filtered`, `consent_updated`, `webhook_ingest`, `notification_dispatched`, `user_login`, `rules_executed`. |
| `actor_id` | `VARCHAR(64)` | No | No | ID of caregiver, resident, or system service initiating action. |
| `care_recipient_id` | `VARCHAR(64)` | No | Yes | Target care recipient identifier. |
| `details_json` | `TEXT` | Yes | No | Canonical JSON payload containing event metadata. |
| `prev_hash` | `VARCHAR(64)` | No | No | SHA-256 hash of the preceding audit record (`"0"*64` for genesis). |
| `entry_hash` | `VARCHAR(64)` | No | No | $\text{SHA-256}(\text{prev\_hash} \parallel \text{audit\_id} \parallel \text{ts} \parallel \text{actor} \parallel \text{type} \parallel \text{details})$. |
