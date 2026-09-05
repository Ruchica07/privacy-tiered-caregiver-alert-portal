# System Limitations & Threat Model

This document outlines the explicitly acknowledged limitations, assumptions, threat model, and regulatory posture of the Privacy-Tiered Caregiver Alert Portal prototype.

---

## 1. Explicit Non-Goals & Scope Boundaries

1. **Not a Medical Device**: The system does NOT diagnose, treat, prevent, or monitor clinical conditions (e.g., cardiac arrythmia, cognitive decline stage, glucose levels).
2. **No High-Frequency Emergency Dispatch**: The portal is not a replacement for 911 / EMS emergency response pendants or monitored fall dispatch services.
3. **No Direct Senior UI Burden**: Older adults are not required to operate complex touchscreens, navigate menus, or respond to multi-step prompts. Their interaction is limited to passive sensing and simple physical check-in buttons.

---

## 2. Regulatory & Compliance Posture

### HIPAA (Health Insurance Portability and Accountability Act)
- **Status**: The prototype incorporates HIPAA-aligned access control principles (Minimum Necessary Rule) via `consent_filter.py` and immutable audit logs. However, as a standalone open prototype running on synthetic data, it is not currently certified under BAA (Business Associate Agreement) infrastructure.

### GDPR (General Data Protection Regulation)
- **Article 6 (Consent)**: Explicit, revocable consent matrices empower care recipients (or legal proxies) to manage category-level sharing.
- **Article 15 (Right of Access)**: The Admin Audit Log exposes all historical disclosure decisions.
- **Article 17 (Right to Erasure)**: Data stores support complete purging of recipient signal histories.

---

## 3. Known Technical Gaps & Limitations

| Dimension | Current Limitation | Mitigation / Production Path |
|-----------|-------------------|------------------------------|
| **Authentication** | Mock role selector dropdown | OAuth2 / OIDC with WebAuthn & MFA |
| **Data Store** | File-based JSON (`sample_dataset.json`) | PostgreSQL with Row-Level Security (RLS) |
| **Sensor Ingestion** | Synthetic batch generator | MQTT / WebSockets for real-time telemetry |
| **Proxy Authorization** | Simulated legal proxy role | Integration with electronic Power of Attorney registries |
| **Offline Resilience** | Client-side cache only | Service Workers + IndexedDB offline queuing |

---

## 4. Threat Model & Failure Modes

### Attack Vectors & Protections

1. **Caregiver Privilege Escalation**:
   - *Risk*: A secondary caregiver attempts to call API endpoints reserved for primary caregivers or professional coordinators.
   - *Defense*: Server-side `consent_filter.py` enforces tier checking on every API request independently of client UI parameters.

2. **Diagnostic Jargon Leakage**:
   - *Risk*: Third-party sensor integration emits clinical notes containing medical terminology.
   - *Defense*: Dual-layer regex `content_linter.py` scans text at generation and render time, downgrading any violation to generic operational phrasing.

3. **Silent Sensor Failure ("False Peace of Mind")**:
   - *Risk*: A dead battery or disconnected Wi-Fi router causes zero signals to arrive, which an unrefined system might interpret as "no problems detected".
   - *Defense*: Active data gap detection flags stale or missing streams with explicit red "Missing Data" freshness badges after 24 hours.

4. **Coercive Consent Setup**:
   - *Risk*: Family members pressure an older adult into granting Tier 3 full access.
   - *Defense*: The consent model defaults to Tier 0 / Tier 1 upon initial onboarding, requiring affirmative step-up confirmation and audit logging.
