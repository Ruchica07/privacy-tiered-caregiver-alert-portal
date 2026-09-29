# AegisCare — REST API Specification & Endpoint Reference (Phase 3)

This document provides complete documentation of all **34 registered FastAPI routes** in the AegisCare portal (comprising **30 application REST routes** and **4 built-in OpenAPI/docs routes**).

---

## 1. Route Summary & Categorization

* **Total Registered FastAPI Routes:** `34`
* **Application REST Endpoints:** `30`
* **Documentation & OpenAPI Routes:** `4` (`/openapi.json`, `/docs`, `/docs/oauth2-redirect`, `/redoc`)

```
Authentication & Identity (3):
  POST  /api/auth/login
  GET   /api/auth/me
  POST  /api/auth/oidc/validate

Edge Ingestion & Telemetry (3):
  POST  /api/v1/ingest/webhook
  POST  /api/v1/ingest/mqtt
  POST  /api/synthetic/signals

Care Roster & Fleet Monitoring (5):
  GET   /api/care-recipients
  GET   /api/caregivers
  GET   /api/caregivers/{recipient_id}
  GET   /api/fleet-overview
  GET   /api/data-status/{care_recipient_id}

Rules Engine & Alert Generation (2):
  POST  /api/run-rules/{care_recipient_id}
  POST  /api/run-rules-all

Alerts & Privacy Evidence (3):
  GET   /api/alerts
  GET   /api/alerts/{alert_id}/evidence
  GET   /api/all-alerts-raw

Consent & Permission Governance (3):
  GET   /api/consent/{care_recipient_id}
  PUT   /api/consent/{care_recipient_id}
  GET   /api/access-summary

Cryptographic Tamper-Evident Audit (4):
  GET   /api/audit/{care_recipient_id}
  GET   /api/audit/verify
  GET   /api/audit-verify
  GET   /api/audit/{care_recipient_id}/verify

Notification Dispatcher (2):
  POST  /api/notifications/dispatch
  GET   /api/notifications/history

Evaluation Benchmarks & Safety (2):
  GET   /api/evaluation-metrics
  GET   /api/stakeholder-metrics
  GET   /api/advanced-evaluation-metrics
  GET   /api/ground-truth
  POST  /api/lint-check
```

---

## 2. Authentication & Identity Endpoints

### `POST /api/auth/login`
* **Purpose:** Authenticates caregiver credentials and issues a signed HS256 JWT bearer access token.
* **Auth Requirement:** None (Public login endpoint).
* **Request Body:**
  ```json
  {
    "username": "jane.smith",
    "password": "AegisCare2026!"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in_seconds": 86400,
    "user": {
      "caregiver_id": "cg_001",
      "username": "jane.smith",
      "name": "Jane Smith",
      "role": "primary_caregiver",
      "care_recipient_ids": ["cr_001"]
    }
  }
  ```
* **Error Cases:** `401 Unauthorized` (`AUTHENTICATION_ERROR`) on invalid username or password.

---

### `GET /api/auth/me`
* **Purpose:** Retrieves identity, role, and assigned care recipients for the currently authenticated user.
* **Auth Requirement:** Bearer JWT Token (`Authorization: Bearer <token>`).
* **Response (200 OK):** Returns authenticated user profile dict.

---

### `POST /api/auth/oidc/validate`
* **Purpose:** Validates external OpenID Connect (OIDC) Bearer tokens against standard claims (`iss`, `aud`, `sub`, `exp`, role mapping).
* **Auth Requirement:** None.
* **Request Body:**
  ```json
  {
    "token": "eyJhbGciOiJIUzI1NiIs..."
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "is_valid": true,
    "status": "validated",
    "caregiver_profile": {
      "caregiver_id": "cg_001",
      "username": "jane.smith",
      "name": "Jane Smith",
      "role": "primary_caregiver",
      "care_recipient_ids": ["cr_001"],
      "auth_provider": "OIDC",
      "issuer": "https://auth.aegiscare.internal/oauth2/v1"
    }
  }
  ```
* **Error Cases:** `401 Unauthorized` on expired, untrusted issuer, audience mismatch, or tampered signature.

---

## 3. Edge Ingestion & Telemetry Endpoints

### `POST /api/v1/ingest/webhook`
* **Purpose:** Authenticated ingestion gateway for external vendor IoT devices, home gateways, and smart sensors.
* **Headers:** `X-Signature-256` (HMAC-SHA256 signature of raw request body).
* **Request Body:**
  ```json
  {
    "care_recipient_id": "cr_001",
    "signal_type": "activity_score",
    "timestamp": "2026-09-29T14:30:00Z",
    "value": 48.5,
    "event_id": "evt_wh_1001",
    "metadata": {"sensor": "living_room_pir"}
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "success": true,
    "status": "ingested",
    "signal_id": "sig_9a8b7c6d5e4f",
    "event_id": "evt_wh_1001",
    "noise_smoothed": false,
    "drift_detected": false,
    "audit_entry_hash": "a1b2c3d4..."
  }
  ```
* **Error Cases:**
  - `401 Unauthorized`: Invalid HMAC-SHA256 signature.
  - `422 Unprocessable Entity`: Future timestamp exceeding 60.0s clock skew.
  - `400 Bad Request`: Missing required fields or unknown signal type.

---

### `POST /api/v1/ingest/mqtt`
* **Purpose:** Ingests normalized IoT telemetry published over MQTT topics (`aegiscare/{care_recipient_id}/{signal_type}`).
* **Request Body:**
  ```json
  {
    "topic": "aegiscare/cr_001/device_heartbeat",
    "payload": {"status": "online", "battery_pct": 98.0},
    "qos": 1
  }
  ```
* **Response (200 OK):** Status object confirming signal mapping, deduplication check, and storage.

---

## 4. Care Roster & Fleet Overview Endpoints

### `GET /api/fleet-overview`
* **Purpose:** Multi-resident dashboard summary for professional care coordinators.
* **Auth Requirement:** Optional Bearer token or `caregiver_id` query parameter.
* **Response (200 OK):**
  ```json
  {
    "fleet": [
      {
        "care_recipient_id": "cr_001",
        "name": "Eleanor Vance",
        "status_badge": "Operational Normal",
        "status_type": "normal",
        "freshness": "fresh",
        "total_active_alerts": 1,
        "severity_counts": {"critical": 0, "high": 0, "medium": 1, "low": 0},
        "overall_tier_label": "Tier 2",
        "baseline_activity_mean": 50.0
      }
    ],
    "total_recipients": 3,
    "coordinator_id": "cg_004"
  }
  ```

---

## 5. Alerts & Privacy Filtering Endpoints

### `GET /api/alerts`
* **Purpose:** Retrieves the tier-filtered, consent-checked alert feed for a designated caregiver.
* **Parameters:** `caregiver_id` (Query, required).
* **Security Guard:** Server-side anti-impersonation checks that authenticated token identity matches requested `caregiver_id`.
* **Response (200 OK):**
  ```json
  {
    "alerts": [
      {
        "alert_id": "alt_001",
        "care_recipient_id": "cr_001",
        "alert_type": "adherence_alert",
        "category": "activity_engagement",
        "severity": "medium",
        "evidence_summary": "No check-in received in the last 6.0 hours (expected every 4 hours).",
        "actionable_step": "Consider calling to check in on daily routine.",
        "disclosed_tier": 2,
        "tier_label": "Detailed Context",
        "generated_at": "2026-09-29T12:00:00Z"
      }
    ],
    "total": 1
  }
  ```

---

## 6. Live Notification Dispatcher Endpoints (Phase 3)

### `POST /api/notifications/dispatch`
* **Purpose:** Dispatches an alert notification to a caregiver over Web Push or SMS Sandbox adapters after applying server-side consent filtering, tier redaction, content linting, and idempotency deduplication.
* **Request Body:**
  ```json
  {
    "alert_id": "alt_001",
    "caregiver_id": "cg_001",
    "channel": "web_push",
    "recipient_contact": "jane.smith@push.local"
  }
  ```
* **Response (200 OK):**
  ```json
  {
    "dispatch_id": "disp_8f7e6d5c",
    "idempotency_key": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "status": "delivered_sandbox",
    "is_duplicate": false,
    "disclosed_tier": 2,
    "attempts": 1,
    "channel": "web_push",
    "provider_meta": {
      "adapter": "WebPushSandboxAdapter",
      "environment": "SANDBOX / SIMULATION",
      "is_sandbox": true
    },
    "payload": {
      "alert_id": "alt_001",
      "evidence_summary": "No check-in received in the last 6.0 hours (expected every 4 hours).",
      "actionable_step": "Consider calling to check in on daily routine."
    }
  }
  ```

---

## 7. Cryptographic Tamper-Evident Audit Endpoints

### `GET /api/audit/verify` (also `/api/audit-verify`)
* **Purpose:** Cryptographically verifies the continuous SHA-256 hash chain across all audit log rows.
* **Parameters:** `care_recipient_id` (Query, optional).
* **Response (200 OK):**
  ```json
  {
    "is_valid": true,
    "total_records_checked": 142,
    "verified_at": "2026-09-29T15:00:00Z",
    "status": "chain_valid_unmodified"
  }
  ```
