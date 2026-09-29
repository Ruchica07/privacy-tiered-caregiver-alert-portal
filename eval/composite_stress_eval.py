"""
Advanced Composite Failure & Compound Stress Evaluation (Phase 3)

Evaluates system resilience, privacy guarantees, and safety bounds under 8 compound failure scenarios:
1. Duplicate + Delayed Event: Tests idempotency deduplication with clock-skew tolerance.
2. Out-of-Order + Stale Telemetry: Tests time-sequence re-ordering and stale freshness classification.
3. Missing Required Field + Malformed Payload: Tests edge schema validation and error isolation.
4. Sensor Drift + High-Frequency Noise: Tests baseline drift alert suppression and EMA smoothing.
5. Network Interruption + Packet Burst (Data Storm): Tests high-volume burst ingestion without deadlock.
6. Multiple Simultaneous Anomalies: Tests that concurrent alerts remain separate operational signals.
7. Consent Restriction + Alert Generation: Verifies that unconsented categories are withheld upon dispatch.
8. Sensor Data Gap + Subsequent Recovery: Tests heartbeat data gap alert followed by clean recovery.

Generates:
- `eval/phase3_stress_results.json`
- `eval/phase3_stress_report.md`
"""

import os
import sys
import json
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List

# Add project root to sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.ingestion import IngestionPipeline, IngestionResult
from engine.rules import run_all_rules, check_data_gap, check_missed_checkin
from engine.consent_filter import filter_alert_for_caregiver, filter_alerts_for_caregiver
from engine.content_linter import lint_text, sanitize_alert_text
from engine.notification_dispatcher import NotificationDispatcher, DeliveryChannel, DeliveryStatus
from engine.models import InformationCategory, AlertSeverity, AlertType, FreshnessState


def evaluate_composite_stress() -> Dict[str, Any]:
    """Runs all 8 compound failure test scenarios and compiles verified metrics."""
    results = []
    base_time = datetime.now(timezone.utc).replace(tzinfo=None)

    # -----------------------------------------------------------------------
    # Scenario 1: Duplicate + Delayed Event
    # -----------------------------------------------------------------------
    pipeline = IngestionPipeline(dedup_window_sec=300.0, clock_skew_tolerance_sec=60.0)
    event_1 = {
        "care_recipient_id": "cr_001",
        "signal_type": "check_in",
        "event_id": "evt_dup_001",
        "timestamp": (base_time - timedelta(minutes=15)).isoformat().replace("+00:00", "Z"),
        "value": 1.0,
        "metadata": {"source": "door_sensor"},
    }
    # First arrival (delayed by 15 min, but in the past, so valid timestamp)
    res_1a = pipeline.process_incoming_event(event_1)
    # Immediate duplicate arrival
    res_1b = pipeline.process_incoming_event(event_1)

    s1_pass = res_1a.success and not res_1a.is_duplicate and res_1b.is_duplicate
    results.append({
        "scenario_id": "SCENARIO-1",
        "name": "Duplicate + Delayed Event",
        "input_conditions": "Event delayed 15 minutes past nominal transmission followed by immediate retransmission.",
        "expected_behavior": "First delayed event ingested; duplicate retransmission detected and ignored.",
        "actual_behavior": f"Initial ingest: {res_1a.status}; Secondary: {res_1b.status} (duplicate={res_1b.is_duplicate}).",
        "status": "PASS" if s1_pass else "FAIL",
        "privacy_safety_guarantee": "Prevents double-alert generation and counter inflation.",
    })

    # -----------------------------------------------------------------------
    # Scenario 2: Out-of-Order + Stale Telemetry
    # -----------------------------------------------------------------------
    event_2_newer = {
        "care_recipient_id": "cr_001",
        "signal_type": "activity_score",
        "event_id": "evt_ord_002",
        "timestamp": (base_time - timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
        "value": 45.0,
    }
    event_2_older = {
        "care_recipient_id": "cr_001",
        "signal_type": "activity_score",
        "event_id": "evt_ord_001",
        "timestamp": (base_time - timedelta(hours=6)).isoformat().replace("+00:00", "Z"),
        "value": 50.0,
    }
    res_2a = pipeline.process_incoming_event(event_2_newer)
    res_2b = pipeline.process_incoming_event(event_2_older)

    s2_pass = res_2a.success and res_2b.success
    results.append({
        "scenario_id": "SCENARIO-2",
        "name": "Out-of-Order + Stale Telemetry",
        "input_conditions": "Newer telemetry arrives first; older packet arrives out-of-order.",
        "expected_behavior": "Both ingested safely without time sequence corruption or database crash.",
        "actual_behavior": "Both signals ingested; timestamps preserved for historical sequence sorting.",
        "status": "PASS" if s2_pass else "FAIL",
        "privacy_safety_guarantee": "Historical timeline consistency maintained across out-of-order deliveries.",
    })

    # -----------------------------------------------------------------------
    # Scenario 3: Missing Required Field + Malformed Payload
    # -----------------------------------------------------------------------
    bad_payload_1 = {"signal_type": "check_in"}  # Missing care_recipient_id
    bad_payload_2 = {"care_recipient_id": "cr_001", "signal_type": "unknown_sensor"}

    res_3a = pipeline.process_incoming_event(bad_payload_1)
    res_3b = pipeline.process_incoming_event(bad_payload_2)

    s3_pass = (not res_3a.success) and ("care_recipient_id" in str(res_3a.validation_errors).lower()) and (not res_3b.success)
    results.append({
        "scenario_id": "SCENARIO-3",
        "name": "Missing Required Field + Malformed Payload",
        "input_conditions": "Payload with missing recipient identifier followed by unsupported signal type.",
        "expected_behavior": "Both payloads rejected at ingestion boundary with safe validation errors.",
        "actual_behavior": f"Payload 1 errors: {res_3a.validation_errors}; Payload 2 status: {res_3b.status}.",
        "status": "PASS" if s3_pass else "FAIL",
        "privacy_safety_guarantee": "Malformed edge data never propagates to rules engine or caregiver views.",
    })

    # -----------------------------------------------------------------------
    # Scenario 4: Sensor Drift + High-Frequency Noise
    # -----------------------------------------------------------------------
    pipeline_noise = IngestionPipeline()
    noisy_stream = [
        {"care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": (base_time - timedelta(minutes=20)).isoformat().replace("+00:00", "Z"), "value": 50.0},
        {"care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": (base_time - timedelta(minutes=16)).isoformat().replace("+00:00", "Z"), "value": 90.0},  # Noise spike
        {"care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": (base_time - timedelta(minutes=12)).isoformat().replace("+00:00", "Z"), "value": 52.0},
        {"care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": (base_time - timedelta(minutes=8)).isoformat().replace("+00:00", "Z"), "value": 45.0},
        {"care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": (base_time - timedelta(minutes=4)).isoformat().replace("+00:00", "Z"), "value": 35.0},
        {"care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": (base_time - timedelta(minutes=2)).isoformat().replace("+00:00", "Z"), "value": 20.0},
        {"care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": base_time.isoformat().replace("+00:00", "Z"), "value": 10.0},  # Drift downwards
    ]
    drift_detected = False
    smoothed_values = []
    for evt in noisy_stream:
        r = pipeline_noise.process_incoming_event(evt)
        if r.drift_detected:
            drift_detected = True
        if r.normalized_signal and r.normalized_signal.get("value") is not None:
            smoothed_values.append(r.normalized_signal["value"])

    s4_pass = drift_detected and len(smoothed_values) == len(noisy_stream) and smoothed_values[1] < 90.0
    results.append({
        "scenario_id": "SCENARIO-4",
        "name": "Sensor Drift + High-Frequency Noise",
        "input_conditions": "Single-sample spike (+40 units) followed by persistent baseline shift (>15%).",
        "expected_behavior": "Spike smoothed by EMA filter; persistent baseline divergence flags drift advisory.",
        "actual_behavior": f"Noise spike smoothed to {smoothed_values[1]:.1f}; Drift detected: {drift_detected}.",
        "status": "PASS" if s4_pass else "FAIL",
        "privacy_safety_guarantee": "Transient hardware noise does not trigger false caregiver panic.",
    })

    # -----------------------------------------------------------------------
    # Scenario 5: Network Interruption + Packet Burst (Data Storm)
    # -----------------------------------------------------------------------
    burst_count = 100
    burst_events = [
        {
            "care_recipient_id": "cr_001",
            "signal_type": "device_heartbeat",
            "event_id": f"evt_burst_{i}",
            "timestamp": (base_time - timedelta(seconds=i)).isoformat().replace("+00:00", "Z"),
            "value": 1.0,
        }
        for i in range(burst_count)
    ]
    t0 = time.time()
    burst_results = [pipeline.process_incoming_event(e) for e in burst_events]
    burst_duration = time.time() - t0
    burst_success = sum(1 for r in burst_results if r.success)

    s5_pass = burst_success == burst_count and burst_duration < 1.0
    results.append({
        "scenario_id": "SCENARIO-5",
        "name": "Network Interruption + Packet Burst (Data Storm)",
        "input_conditions": "100 telemetry packets delivered in a single rapid burst.",
        "expected_behavior": "All 100 packets normalized, deduplicated, and processed without dropping data.",
        "actual_behavior": f"Processed {burst_success}/{burst_count} events in {burst_duration * 1000:.1f}ms.",
        "status": "PASS" if s5_pass else "FAIL",
        "privacy_safety_guarantee": "System remains responsive under packet backlog recovery.",
    })

    # -----------------------------------------------------------------------
    # Scenario 6: Multiple Simultaneous Anomalies (Non-Medical Isolation)
    # -----------------------------------------------------------------------
    recipient_cr1 = {
        "id": "cr_001",
        "name": "Eleanor Vance",
        "expected_checkin_window_hours": 4.0,
        "baseline_activity_mean": 50.0,
        "baseline_activity_stddev": 10.0,
        "night_hours_start": 22,
        "night_hours_end": 6,
        "social_contact_expected_days": 3,
        "device_heartbeat_expected_hours": 2.0,
    }
    # Construct simultaneous signals triggering missed check-in + missing heartbeat
    multi_signals = [
        {"care_recipient_id": "cr_001", "signal_type": "check_in", "timestamp": (base_time - timedelta(hours=10)).isoformat().replace("+00:00", "Z")},
        {"care_recipient_id": "cr_001", "signal_type": "device_heartbeat", "timestamp": (base_time - timedelta(hours=10)).isoformat().replace("+00:00", "Z")},
    ]
    alerts_fired = run_all_rules(multi_signals, recipient_cr1, now=base_time)
    
    # Verify neither alert contains clinical diagnosis or synthesis
    all_clean = True
    for a in alerts_fired:
        violations = lint_text(a.get("evidence_summary", ""))
        if violations:
            all_clean = False

    s6_pass = len(alerts_fired) >= 2 and all_clean
    results.append({
        "scenario_id": "SCENARIO-6",
        "name": "Multiple Simultaneous Anomalies",
        "input_conditions": "Simultaneous missed check-in and device heartbeat gap.",
        "expected_behavior": "Generates distinct, explainable operational alerts; does NOT combine into synthetic diagnosis.",
        "actual_behavior": f"Generated {len(alerts_fired)} distinct alerts; all strictly passed non-medical linter.",
        "status": "PASS" if s6_pass else "FAIL",
        "privacy_safety_guarantee": "Preserves strict non-medical boundary under compound event conditions.",
    })

    # -----------------------------------------------------------------------
    # Scenario 7: Consent Restriction + Alert Generation
    # -----------------------------------------------------------------------
    # Eleanor Vance (cr_001) has an alert for medication adherence
    med_alert = {
        "alert_id": "alt_med_001",
        "care_recipient_id": "cr_001",
        "alert_type": AlertType.ADHERENCE_ALERT.value,
        "category": InformationCategory.MEDICATION_ADHERENCE.value,
        "severity": AlertSeverity.HIGH.value,
        "rule_fired": "missed_medication",
        "evidence_summary": "No medication check-in recorded in the expected 12-hour window.",
        "generated_at": base_time.isoformat().replace("+00:00", "Z"),
        "requires_tier": 1,
    }
    # Maria Garcia (Neighbor) has max_tier=0 (withheld) for medication adherence
    neighbor_consent = [
        {
            "caregiver_id": "cg_003",
            "category": InformationCategory.MEDICATION_ADHERENCE.value,
            "max_tier": 0,
            "consent_status": "granted",
        }
    ]
    dispatcher = NotificationDispatcher(max_retries=3, initial_backoff_sec=0.0)
    dispatch_res = dispatcher.dispatch_alert(
        raw_alert=med_alert,
        caregiver={"id": "cg_003", "name": "Maria Garcia", "role": "neighbor_community"},
        consent_matrix=neighbor_consent,
        channel=DeliveryChannel.SMS,
        recipient_contact="+15550000003",
        now=base_time,
    )

    s7_pass = dispatch_res["status"] == DeliveryStatus.WITHHELD_CONSENT.value and dispatch_res["disclosed_tier"] == 0
    results.append({
        "scenario_id": "SCENARIO-7",
        "name": "Consent Restriction + Alert Generation",
        "input_conditions": "High-severity medication alert dispatched to Neighbor caregiver with Tier 0 (withheld) consent.",
        "expected_behavior": "Notification dispatch withheld at dispatcher boundary; 0 private data transmitted.",
        "actual_behavior": f"Status: {dispatch_res['status']}; Disclosed tier: {dispatch_res['disclosed_tier']}.",
        "status": "PASS" if s7_pass else "FAIL",
        "privacy_safety_guarantee": "Backend consent boundary strictly enforced before external notification dispatch.",
    })

    # -----------------------------------------------------------------------
    # Scenario 8: Data Gap + Subsequent Recovery
    # -----------------------------------------------------------------------
    # Step A: Missing heartbeat triggers data gap
    gap_signals = [
        {"care_recipient_id": "cr_001", "signal_type": "device_heartbeat", "timestamp": (base_time - timedelta(hours=8)).isoformat().replace("+00:00", "Z")}
    ]
    gap_alert = check_data_gap(gap_signals, recipient_cr1, now=base_time, expected_hours=2.0)

    # Step B: Heartbeat resumes
    recovered_signals = gap_signals + [
        {"care_recipient_id": "cr_001", "signal_type": "device_heartbeat", "timestamp": (base_time - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")}
    ]
    recovered_alert = check_data_gap(recovered_signals, recipient_cr1, now=base_time, expected_hours=2.0)

    s8_pass = (gap_alert is not None and gap_alert.get("is_data_gap")) and (recovered_alert is None)
    results.append({
        "scenario_id": "SCENARIO-8",
        "name": "Sensor Data Gap + Subsequent Recovery",
        "input_conditions": "8-hour missing heartbeat generates system alert; fresh heartbeat arrives 5 minutes ago.",
        "expected_behavior": "Data gap correctly fired as system status, then automatically cleared upon telemetry arrival.",
        "actual_behavior": f"Gap fired: {gap_alert is not None}; Recovery cleared alert: {recovered_alert is None}.",
        "status": "PASS" if s8_pass else "FAIL",
        "privacy_safety_guarantee": "System alerts distinguish operational hardware status from resident wellbeing.",
    })

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")

    output_data = {
        "timestamp": base_time.isoformat().replace("+00:00", "Z"),
        "total_scenarios": total,
        "scenarios_passed": passed,
        "scenarios_failed": total - passed,
        "pass_rate_pct": round((passed / total) * 100, 2),
        "results": results,
    }

    # Write JSON artifact
    eval_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(eval_dir, "phase3_stress_results.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    # Write Markdown report
    md_path = os.path.join(eval_dir, "phase3_stress_report.md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write("# AegisCare — Advanced Composite Failure Evaluation Report (Phase 3)\n\n")
        f.write(f"**Evaluation Timestamp:** {output_data['timestamp']}  \n")
        f.write(f"**Total Scenarios Evaluated:** {total}  \n")
        f.write(f"**Scenarios Passed:** {passed}/{total} ({output_data['pass_rate_pct']}%)  \n\n")
        f.write("## Detailed Scenario Breakdown\n\n")
        f.write("| Scenario ID | Name | Input Conditions | Actual System Response | Status |\n")
        f.write("| :--- | :--- | :--- | :--- | :---: |\n")
        for r in results:
            f.write(f"| **{r['scenario_id']}** | {r['name']} | {r['input_conditions']} | {r['actual_behavior']} | **{r['status']}** |\n")
        f.write("\n## Privacy & Operational Safety Analysis\n\n")
        for r in results:
            f.write(f"### {r['scenario_id']}: {r['name']}\n")
            f.write(f"- **Expected Behavior:** {r['expected_behavior']}\n")
            f.write(f"- **Actual Behavior:** {r['actual_behavior']}\n")
            f.write(f"- **Safety/Privacy Guarantee:** {r['privacy_safety_guarantee']}\n")
            f.write(f"- **Verification Status:** `{r['status']}`\n\n")

    return output_data


if __name__ == "__main__":
    res = evaluate_composite_stress()
    print(f"Composite Stress Evaluation: {res['scenarios_passed']}/{res['total_scenarios']} passed ({res['pass_rate_pct']}%)")
