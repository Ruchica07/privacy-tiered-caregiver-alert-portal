# Requirements Specification — Privacy-Tiered Caregiver Alert Portal

## 1. Purpose

This document specifies the requirements for a **privacy-tiered caregiver alert portal** that enables family caregivers to receive actionable, operational alerts about an older adult's wellbeing — without exposing unnecessary private health information. The system enforces consent-based, role-based disclosure tiers so that each caregiver sees only what the care recipient (or their authorized representative) has explicitly consented to share.

> **THIS IS NOT A MEDICAL DEVICE.** This system is not FDA-validated, not clinically certified, and generates no diagnostic output. Every alert is an *operational signal* ("no check-in detected," "pattern deviates from baseline") and must never be interpreted as, or confusable with, a clinical or diagnostic statement. See Section 8 (Non-Goals) for the full out-of-scope statement.

---

## 2. Actors

| Actor | Description | Interaction Mode |
|-------|-------------|-----------------|
| **Care Recipient** (older adult) | The person being monitored. Low digital confidence. Not expected to operate complex dashboards. | Passive — wearables, sensors, simple check-ins (simulated by synthetic data in this prototype) |
| **Primary Caregiver** | Family member with day-to-day care responsibility. Lives with or near the care recipient. | Active — receives alerts, views dashboard, manages consent on behalf of care recipient |
| **Secondary Caregiver** | Backup family member. Needs to act but has less ongoing context. | Active — receives alerts at a lower tier |
| **Neighbor / Community Helper** | Non-family helper. Minimal disclosure appropriate. | Active — receives only binary wellness pings |
| **Care Coordinator / Professional** | Licensed or verified professional (e.g., social worker, home-health nurse). | Active — may see clinical summaries if consented, still not raw records |
| **System Administrator** | Oversees consent configuration, audit trails, system health. | Active — full audit access, no clinical data access beyond what roles allow |

---

## 3. Caregiver Roles & Default Tiers

| Role ID | Role Name | Default Tier | Rationale |
|---------|-----------|-------------|-----------|
| `primary_caregiver` | Primary Caregiver | Tier 2 (Operational + Trend) | Day-to-day responsibility, needs trend context |
| `secondary_caregiver` | Secondary Caregiver | Tier 1 (Operational only) | Backup, needs to act but less context |
| `neighbor_community` | Neighbor / Community | Tier 0 (Wellness ping only) | Not family, minimal disclosure |
| `care_coordinator_professional` | Care Coordinator / Professional | Tier 3 (Operational + Trend + Clinical summary) | Professional role, if licensed/verified |

The care recipient (or admin on their behalf) can **override** the default tier per-caregiver, per-category. A caregiver can never be granted access *above* Tier 3 in this prototype.

---

## 4. Information Categories

| Category ID | Category Name | Description | Sensitivity |
|-------------|--------------|-------------|-------------|
| `activity_engagement` | Activity & Engagement | Movement, check-ins, routine adherence | Low–Medium |
| `medication_adherence` | Medication Adherence | Took / missed a scheduled check-in. **NOT** which medication or dose unless explicitly consented. | Medium |
| `vitals_summary` | Vitals Summary | Qualitative: "within normal range" / "flagged." **NOT** raw numeric values unless explicitly consented. | Medium–High |
| `location_safety` | Location & Safety | In expected zone or not (e.g., left home unexpectedly at night). | Medium |
| `social_isolation_signal` | Social & Isolation | No outgoing calls/visits in N days. | Low–Medium |
| `diagnosis_conditions` | Diagnosis & Conditions | Explicit clinical/diagnostic information. Highest sensitivity. Opt-in only, never shown to non-professional roles by default. | **Highest** |

---

## 5. Disclosure Tiers (Privacy Ladder)

### Tier 0 — Wellness Ping
- Binary "all okay" / "needs attention" only.
- No category detail, no timestamps of specific events, no trend data.
- **Suitable for**: neighbors, community helpers, anyone with minimal consent.

### Tier 1 — Operational Alert
- What *kind* of thing needs attention (category-level).
- Example: "Medication check-in missed."
- No clinical detail, no raw values, no trend data.
- **Suitable for**: secondary caregivers, limited-consent roles.

### Tier 2 — Operational + Trend
- Tier 1 content plus a trend indicator ("this is the 3rd missed check-in this week").
- Includes freshness/confidence metadata.
- Still no raw clinical values.
- **Suitable for**: primary caregivers with active consent.

### Tier 3 — Clinical Summary (Opt-in, Restricted Roles)
- Tier 2 content plus qualitative clinical context ("flagged outside normal range").
- **Still never**: raw diagnoses, medication names, numeric vitals in this prototype.
- Raw data pass-through is **explicitly out of scope** — see Section 8.
- **Suitable for**: care coordinators/professionals with explicit consent + role verification.

---

## 6. Consent Model

### 6.1 Consent Record Structure

Each care recipient has a **consent matrix**: `caregiver_id × information_category × tier`, with:

| Field | Type | Description |
|-------|------|-------------|
| `consent_id` | UUID | Unique identifier |
| `care_recipient_id` | string | The older adult |
| `caregiver_id` | string | The caregiver being granted/denied access |
| `category` | enum | One of the 6 information categories |
| `max_tier` | int (0–3) | Maximum tier this caregiver can see for this category |
| `consent_status` | enum | `granted` / `revoked` / `pending` |
| `granted_at` | datetime | When consent was granted |
| `expires_at` | datetime | When consent expires (null = no expiry) |
| `override_reason` | string (optional) | Free text, e.g., "Dr. approved sharing vitals summary with daughter" |

### 6.2 Consent Rules

- **Fail-safe default**: Unknown consent = no disclosure beyond Tier 0.
- **Expired consent**: Automatically drops to Tier 0 and notifies the care recipient / admin.
- **Revoked consent**: Immediately effective — next alert generation respects the revocation.
- **Pending consent**: Treated as revoked (no disclosure) until explicitly granted.
- **Audit trail**: Every consent change is logged: who changed it, when, old value → new value.

### 6.3 Privacy Design Decision: Omission vs. Placeholder

When a caregiver lacks consent for a category:
- **Decision: Omit entirely** from that caregiver's alert feed.
- **Rationale**: Showing "[hidden]" placeholders would leak information about *what categories exist* for this recipient. Omitting unconsented categories prevents inference attacks.
- **Exception**: The caregiver's own "Access & Consent" view shows which categories exist and are restricted (so they understand the system), without showing values.

---

## 7. Functional Requirements

### FR-1: Consent Management
- FR-1.1: Admin/care-recipient can create, update, revoke consent per caregiver × category × tier.
- FR-1.2: Consent changes take effect immediately on the next alert rendering.
- FR-1.3: Expired consent auto-drops to Tier 0 with notification.
- FR-1.4: All consent changes are logged to an immutable audit trail.

### FR-2: Alert Generation (Rules Engine)
- FR-2.1: Missed check-in rule with configurable window.
- FR-2.2: Deviation-from-baseline rule using statistical thresholds.
- FR-2.3: Location/safety rule for unexpected departures.
- FR-2.4: Social isolation rule based on contact frequency.
- FR-2.5: Data-gap rule for sensor/device dropout (system alert, NOT health event).
- FR-2.6: Every alert is a structured object with category, severity, rule reference, evidence, and required tier.

### FR-3: Consent-Based Alert Filtering
- FR-3.1: `filter_alert_for_caregiver()` — pure function gating disclosure.
- FR-3.2: Alerts rendered only at or below the caregiver's consented tier.
- FR-3.3: Every filtering decision logged for audit.

### FR-4: Content Safety (Operational vs. Medical)
- FR-4.1: All alert text passes through a content linter before rendering.
- FR-4.2: Banned medical/diagnostic phrases are blocked at build time and runtime.
- FR-4.3: Violations trigger fallback to pre-approved generic operational phrasing.

### FR-5: Caregiver Dashboard
- FR-5.1: Role-based views (at least 3 distinct role views).
- FR-5.2: Card-based alert feed, newest first.
- FR-5.3: Each card shows: category, severity, tier label, freshness indicator.
- FR-5.4: "Your access level" banner per care recipient.
- FR-5.5: Positive empty state: "No alerts — everything looks on track."

### FR-6: Alert Drill-down
- FR-6.1: Tier-filtered evidence view (sparklines, trends, rule explanation).
- FR-6.2: Persistent disclaimer: "This is an operational pattern alert, not a medical diagnosis."

### FR-7: Freshness & Data Status
- FR-7.1: Four distinct UI states: Fresh, Stale, Missing, Consent-restricted.
- FR-7.2: "Missing" ≠ "all clear" — explicit guidance shown.
- FR-7.3: "Consent-restricted" visually distinct from "Missing."

### FR-8: Admin/Audit View
- FR-8.1: Full consent change audit trail.
- FR-8.2: Alert generation log.
- FR-8.3: "Who can see what" matrix.

---

## 8. Non-Functional Requirements

| ID | Requirement | Target |
|----|------------|--------|
| NFR-1 | Alert latency (synthetic) | < 2 seconds from signal ingestion to alert availability |
| NFR-2 | Unnecessary disclosure rate | **0%** (hard requirement) |
| NFR-3 | Content linter violations reaching UI | **0** |
| NFR-4 | Freshness badge correctness | **100%** against synthetic ground truth |
| NFR-5 | Alert precision | ≥ 0.80 |
| NFR-6 | Alert recall | ≥ 0.85 |

---

## 9. Explicit Non-Goals (Out of Scope)

1. **This is not a medical device**, not FDA-validated, not clinically certified, and generates no diagnostic output.
2. **No real PHI** (Protected Health Information) is stored, processed, or transmitted. All data is synthetic.
3. **No real device integrations** (Apple HealthKit, Google Fit, medical alert pendants, smart plugs, medication dispensers). The API stub simulates these feeds.
4. **No production-grade authentication or security hardening.** Mock auth (role selector) is used. This is a prototype.
5. **Tier 3 clinical summaries remain qualitative only.** Raw vitals, medication names/doses, and numeric clinical data pass-through is explicitly out of scope and flagged as future work requiring regulatory/compliance review (HIPAA/GDPR, Business Associate Agreements, clinical sign-off).
6. **No real-time push notifications.** Alerts are available via polling/refresh in this prototype.
7. **No mobile-native app.** The web UI is responsive but not a native iOS/Android application.

---

## 10. Assumptions

1. Synthetic data adequately represents the range of real-world patterns for prototype evaluation.
2. 4 caregiver roles are sufficient to demonstrate the tiering concept; production would likely add more.
3. Mock authentication is acceptable for a capstone demonstration.
4. JSON file storage is sufficient for prototype data persistence.
