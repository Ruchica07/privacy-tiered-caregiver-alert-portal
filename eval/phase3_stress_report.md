# AegisCare — Advanced Composite Failure Evaluation Report (Phase 3)

**Evaluation Timestamp:** 2026-09-29T11:27:35.206691  
**Total Scenarios Evaluated:** 8  
**Scenarios Passed:** 8/8 (100.0%)  

## Detailed Scenario Breakdown

| Scenario ID | Name | Input Conditions | Actual System Response | Status |
| :--- | :--- | :--- | :--- | :---: |
| **SCENARIO-1** | Duplicate + Delayed Event | Event delayed 15 minutes past nominal transmission followed by immediate retransmission. | Initial ingest: ingested; Secondary: duplicate_ignored (duplicate=True). | **PASS** |
| **SCENARIO-2** | Out-of-Order + Stale Telemetry | Newer telemetry arrives first; older packet arrives out-of-order. | Both signals ingested; timestamps preserved for historical sequence sorting. | **PASS** |
| **SCENARIO-3** | Missing Required Field + Malformed Payload | Payload with missing recipient identifier followed by unsupported signal type. | Payload 1 errors: ["Missing required field: 'care_recipient_id' (or 'recipient_id'/'patient_id')"]; Payload 2 status: rejected_invalid_payload. | **PASS** |
| **SCENARIO-4** | Sensor Drift + High-Frequency Noise | Single-sample spike (+40 units) followed by persistent baseline shift (>15%). | Noise spike smoothed to 64.0; Drift detected: True. | **PASS** |
| **SCENARIO-5** | Network Interruption + Packet Burst (Data Storm) | 100 telemetry packets delivered in a single rapid burst. | Processed 100/100 events in 5.6ms. | **PASS** |
| **SCENARIO-6** | Multiple Simultaneous Anomalies | Simultaneous missed check-in and device heartbeat gap. | Generated 6 distinct alerts; all strictly passed non-medical linter. | **PASS** |
| **SCENARIO-7** | Consent Restriction + Alert Generation | High-severity medication alert dispatched to Neighbor caregiver with Tier 0 (withheld) consent. | Status: withheld_consent; Disclosed tier: 0. | **PASS** |
| **SCENARIO-8** | Sensor Data Gap + Subsequent Recovery | 8-hour missing heartbeat generates system alert; fresh heartbeat arrives 5 minutes ago. | Gap fired: True; Recovery cleared alert: True. | **PASS** |

## Privacy & Operational Safety Analysis

### SCENARIO-1: Duplicate + Delayed Event
- **Expected Behavior:** First delayed event ingested; duplicate retransmission detected and ignored.
- **Actual Behavior:** Initial ingest: ingested; Secondary: duplicate_ignored (duplicate=True).
- **Safety/Privacy Guarantee:** Prevents double-alert generation and counter inflation.
- **Verification Status:** `PASS`

### SCENARIO-2: Out-of-Order + Stale Telemetry
- **Expected Behavior:** Both ingested safely without time sequence corruption or database crash.
- **Actual Behavior:** Both signals ingested; timestamps preserved for historical sequence sorting.
- **Safety/Privacy Guarantee:** Historical timeline consistency maintained across out-of-order deliveries.
- **Verification Status:** `PASS`

### SCENARIO-3: Missing Required Field + Malformed Payload
- **Expected Behavior:** Both payloads rejected at ingestion boundary with safe validation errors.
- **Actual Behavior:** Payload 1 errors: ["Missing required field: 'care_recipient_id' (or 'recipient_id'/'patient_id')"]; Payload 2 status: rejected_invalid_payload.
- **Safety/Privacy Guarantee:** Malformed edge data never propagates to rules engine or caregiver views.
- **Verification Status:** `PASS`

### SCENARIO-4: Sensor Drift + High-Frequency Noise
- **Expected Behavior:** Spike smoothed by EMA filter; persistent baseline divergence flags drift advisory.
- **Actual Behavior:** Noise spike smoothed to 64.0; Drift detected: True.
- **Safety/Privacy Guarantee:** Transient hardware noise does not trigger false caregiver panic.
- **Verification Status:** `PASS`

### SCENARIO-5: Network Interruption + Packet Burst (Data Storm)
- **Expected Behavior:** All 100 packets normalized, deduplicated, and processed without dropping data.
- **Actual Behavior:** Processed 100/100 events in 5.6ms.
- **Safety/Privacy Guarantee:** System remains responsive under packet backlog recovery.
- **Verification Status:** `PASS`

### SCENARIO-6: Multiple Simultaneous Anomalies
- **Expected Behavior:** Generates distinct, explainable operational alerts; does NOT combine into synthetic diagnosis.
- **Actual Behavior:** Generated 6 distinct alerts; all strictly passed non-medical linter.
- **Safety/Privacy Guarantee:** Preserves strict non-medical boundary under compound event conditions.
- **Verification Status:** `PASS`

### SCENARIO-7: Consent Restriction + Alert Generation
- **Expected Behavior:** Notification dispatch withheld at dispatcher boundary; 0 private data transmitted.
- **Actual Behavior:** Status: withheld_consent; Disclosed tier: 0.
- **Safety/Privacy Guarantee:** Backend consent boundary strictly enforced before external notification dispatch.
- **Verification Status:** `PASS`

### SCENARIO-8: Sensor Data Gap + Subsequent Recovery
- **Expected Behavior:** Data gap correctly fired as system status, then automatically cleared upon telemetry arrival.
- **Actual Behavior:** Gap fired: True; Recovery cleared alert: True.
- **Safety/Privacy Guarantee:** System alerts distinguish operational hardware status from resident wellbeing.
- **Verification Status:** `PASS`

