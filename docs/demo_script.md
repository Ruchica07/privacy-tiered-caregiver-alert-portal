# Demo Script — Privacy-Tiered Caregiver Alert Portal

A 5–8 minute scripted walkthrough designed for a capstone presentation or live video demonstration of the working prototype.

---

## Storyline Context

**Care Recipient**: Dorothy Thompson (82 years old, lives alone, low digital confidence).  
**Caregivers**:
1. **Jane Smith** (Daughter, Primary Caregiver) — Tier 2 (Detailed Trends)
2. **Bob Smith** (Son, Secondary Caregiver) — Tier 1 (Category Detail)
3. **Maria Garcia** (Neighbor) — Tier 0 (Wellness Ping)
4. **Dr. Sarah Chen** (Care Coordinator) — Tier 3 (Full Clinical Context)

---

## Act 1: The Privacy Challenge & Role Selection (1 min)

1. Open the Caregiver Portal application at `http://localhost:5173`.
2. Point out the top header:
   - **Role Switcher**: Highlight how switching roles immediately alters the visible information without page reloads.
   - **Disclaimer Strip**: Point out the persistent disclaimer: *"Operational & Wellbeing Support Portal — Not a Diagnostic Medical Device"*.
3. Select **Jane Smith (Primary Caregiver - Tier 2)**.
   - Show the **"Your Access Level" Banner**: Displays granted consent categories and tier access explicitly in the UI.

---

## Act 2: Caregiver Dashboard & Alert Feed (2 min)

1. Review the alert feed for Dorothy Thompson:
   - Point out **Card 1: Nocturnal Activity Pattern** (Severity: High, Category: Location & Safety, Tier: 2).
   - Point out the **Freshness Badge**: `Fresh (<2h ago)`.
2. Click **"View Evidence & Trend"** to expand the drill-down view:
   - Show the **Sparkline Graph**: Displays nighttime motion count over the past 7 days without raw physiological metrics.
   - Read the **Evidence Summary**: *"Nocturnal movement detected between 02:15 and 03:45 AM (3 occurrences this week, baseline = 0)."*
   - Read the **Actionable Step**: *"Check front door smart lock status or call Dorothy during morning check-in."*
3. Switch Role to **Maria Garcia (Neighbor - Tier 0)**:
   - Observe how the exact same alert card updates instantly!
   - Card Title: *"Check-in Reminder / Activity Ping"*.
   - Description: *"Dorothy may appreciate a routine check-in today."*
   - Evidence & trend details are completely hidden. No location, sensor, or night movement text is disclosed.

---

## Act 3: Edge Cases Live Demonstration (3 min)

### Edge Case 1: Consent Revocation Mid-Stream
1. Navigate to **"Consent & Access Settings"** (`/onboarding` or Consent tab).
2. As the Care Recipient representative, **Revoke Consent** for *Location & Safety* for Jane Smith.
3. Return to the Caregiver Dashboard as Jane Smith.
4. Observe: Location alerts drop immediately to **Tier 0 (Restricted)** state with a lock icon.

### Edge Case 2: Total Data Outage (Sensor Disconnection)
1. In the backend or UI simulator, simulate a 24+ hour gap in device heartbeat.
2. Dashboard displays a **Data Gap Alert**:
   - Badge: `Missing (>24h)` in red.
   - Text: *"Sensor Connection Offline — Device heartbeat missed for 26 hours."*
   - Actionable Step: *"Verify gateway power plug and home Wi-Fi router."*
   - Emphasize to the audience: *The system displays "No Data Available", NEVER "All Clear" during an outage.*

### Edge Case 3: Content Linter Enforcement
1. Show the backend log or trigger a raw medical phrase test (`/api/linter/test`).
2. Show how diagnostic strings like `"Symptoms consistent with dementia wandering"` are caught by `content_linter.py` and safely replaced with pre-approved operational phrasing before reaching any UI component.

---

## Act 4: Admin Audit Log & Metrics Dashboard (2 min)

1. Navigate to **"Audit Trail & Compliance"** tab:
   - View the immutable audit log table: timestamp, actor, event type (`consent_revoked`, `alert_filtered`, `access_granted`).
   - Demonstrates HIPAA/GDPR readiness by providing complete transparency into who accessed what tier and when.
2. Navigate to **"Quantitative Evaluation & Metrics"** tab:
   - Highlight measured benchmark performance:
     - **Alert Precision**: 100.0%
     - **Unnecessary Disclosure Rate**: 0.0%
     - **Content Linter Violations**: 0
     - **Freshness Badge Correctness**: 100.0%

---

## Closing Summary

*"By placing consent, caregiver role, and data freshness directly into the user interface, our Privacy-Tiered Caregiver Alert Portal empowers families to support aging loved ones safely, maintaining dignity and privacy without compromising on peace of mind."*
