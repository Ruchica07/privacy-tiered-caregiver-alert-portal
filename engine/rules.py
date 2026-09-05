"""
Rules Engine — Deterministic, Explainable Alert Generation

Implements 5 rule templates for generating operational alerts from
synthetic signals. Each rule is explainable and outputs a structured
alert object. NO black-box ML — trust and operational/medical boundary
require full transparency.

Rules:
1. Missed check-in (activity or medication)
2. Deviation from baseline (activity score)
3. Location/safety (night wandering)
4. Social isolation (no contacts)
5. Data gap (sensor/device dropout — system alert, NOT health event)
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict
from engine.models import (
    Alert, AlertType, AlertSeverity, InformationCategory,
    SignalType, CareRecipient, generate_id,
)
from engine.content_linter import sanitize_alert_text
import statistics


# ---------------------------------------------------------------------------
# Helper: time parsing
# ---------------------------------------------------------------------------

def _parse_ts(ts_str: str) -> datetime:
    """Parse ISO datetime string, handling Z suffix."""
    if not ts_str:
        return datetime.min
    return datetime.fromisoformat(ts_str.replace("Z", "+00:00")).replace(tzinfo=None)


def _now_str() -> str:
    return datetime.utcnow().isoformat() + "Z"


# ---------------------------------------------------------------------------
# Rule 1: Missed Check-In
# ---------------------------------------------------------------------------

def check_missed_checkin(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
    signal_type: str = "check_in",
    category: InformationCategory = InformationCategory.ACTIVITY_ENGAGEMENT,
) -> Optional[dict]:
    """
    If no check-in within the expected window, generate an ADHERENCE_ALERT.
    Severity escalates based on how far past the window.
    """
    now = now or datetime.utcnow()
    window_hours = recipient.get("expected_checkin_window_hours", 4.0)

    # Find the most recent check-in
    checkins = [
        s for s in signals
        if s.get("signal_type") == signal_type
        and s.get("care_recipient_id") == recipient.get("id")
    ]

    if not checkins:
        # No check-ins at all
        hours_overdue = 999
    else:
        latest = max(checkins, key=lambda s: s.get("timestamp", ""))
        latest_time = _parse_ts(latest.get("timestamp", ""))
        hours_overdue = (now - latest_time).total_seconds() / 3600

    if hours_overdue <= window_hours:
        return None  # Within expected window, no alert

    # Determine severity based on overdue duration
    overdue_ratio = hours_overdue / window_hours
    if overdue_ratio >= 4:
        severity = AlertSeverity.CRITICAL
    elif overdue_ratio >= 2.5:
        severity = AlertSeverity.HIGH
    elif overdue_ratio >= 1.5:
        severity = AlertSeverity.MEDIUM
    else:
        severity = AlertSeverity.LOW

    evidence = f"No check-in received in the last {hours_overdue:.1f} hours (expected every {window_hours:.0f} hours)."
    action = "Consider reaching out to check in, or verify the check-in device is working."

    alert = {
        "alert_id": generate_id(),
        "care_recipient_id": recipient.get("id"),
        "alert_type": AlertType.ADHERENCE_ALERT.value,
        "category": category.value,
        "severity": severity.value,
        "rule_fired": "missed_checkin",
        "evidence_summary": evidence,
        "generated_at": now.isoformat() + "Z",
        "requires_tier": 1,
        "is_data_gap": False,
        "actionable_step": action,
        "evidence_data": {
            "hours_overdue": round(hours_overdue, 1),
            "expected_window_hours": window_hours,
            "overdue_ratio": round(overdue_ratio, 2),
        },
    }

    return alert


def check_missed_medication(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """Missed medication check-in — same logic, different category."""
    return check_missed_checkin(
        signals, recipient, now,
        signal_type="medication_event",
        category=InformationCategory.MEDICATION_ADHERENCE,
    )


# ---------------------------------------------------------------------------
# Rule 2: Deviation from Baseline (Activity Score)
# ---------------------------------------------------------------------------

def check_activity_deviation(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
    k: float = 2.0,
    consecutive_days: int = 2,
) -> Optional[dict]:
    """
    If daily activity score < (baseline_mean - k * baseline_stddev)
    for N consecutive days, generate a PATTERN_ALERT.
    """
    now = now or datetime.utcnow()
    recipient_id = recipient.get("id")
    baseline_mean = recipient.get("baseline_activity_mean", 50.0)
    baseline_stddev = recipient.get("baseline_activity_stddev", 10.0)

    # Get activity scores for the last 7 days
    threshold = baseline_mean - k * baseline_stddev
    activity_signals = [
        s for s in signals
        if s.get("signal_type") == "activity_score"
        and s.get("care_recipient_id") == recipient_id
    ]

    if not activity_signals:
        return None

    # Group by day and get daily averages
    daily_scores = {}
    for s in activity_signals:
        ts = _parse_ts(s.get("timestamp", ""))
        day_key = ts.date().isoformat()
        if day_key not in daily_scores:
            daily_scores[day_key] = []
        if s.get("value") is not None:
            daily_scores[day_key].append(s["value"])

    # Check last N days for consecutive below-threshold
    dates_sorted = sorted(daily_scores.keys(), reverse=True)
    below_count = 0
    recent_scores = []

    for date_key in dates_sorted[:7]:  # Look at last 7 days
        day_avg = statistics.mean(daily_scores[date_key]) if daily_scores[date_key] else baseline_mean
        recent_scores.append({"date": date_key, "score": round(day_avg, 1)})
        if day_avg < threshold:
            below_count += 1
        else:
            break  # Not consecutive anymore

    if below_count < consecutive_days:
        return None

    severity = AlertSeverity.MEDIUM if below_count <= 3 else AlertSeverity.HIGH
    evidence = (
        f"Activity level has been below the expected baseline for "
        f"{below_count} consecutive day(s). Baseline: {baseline_mean:.0f}, "
        f"threshold: {threshold:.0f}."
    )
    trend = f"This is a {below_count}-day pattern of reduced activity compared to the usual baseline."
    action = "Consider reaching out or scheduling a visit to check on their routine."

    return {
        "alert_id": generate_id(),
        "care_recipient_id": recipient_id,
        "alert_type": AlertType.PATTERN_ALERT.value,
        "category": InformationCategory.ACTIVITY_ENGAGEMENT.value,
        "severity": severity.value,
        "rule_fired": "activity_deviation",
        "evidence_summary": evidence,
        "generated_at": now.isoformat() + "Z",
        "requires_tier": 2,
        "is_data_gap": False,
        "trend_info": trend,
        "actionable_step": action,
        "evidence_data": {
            "baseline_mean": baseline_mean,
            "baseline_stddev": baseline_stddev,
            "threshold": round(threshold, 1),
            "consecutive_below_days": below_count,
            "recent_scores": recent_scores[:14],
        },
    }


# ---------------------------------------------------------------------------
# Rule 3: Location / Safety (Night Wandering)
# ---------------------------------------------------------------------------

def check_location_safety(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
    return_window_hours: float = 1.0,
) -> Optional[dict]:
    """
    If left_home during night hours and no return within window,
    generate a SAFETY_ALERT with high severity.

    Detection paths:
    1. Primary: left_home event during configured night hours + no return event seen
       within return_window_hours and the window has elapsed.
    2. Secondary: left_home event where the device itself asserts returned_home=False
       (explicit sensor flag) + return_window_hours has elapsed with no return event.
       This covers UTC-stored timestamps that represent local nighttime departures, and
       smart-home devices that directly signal an unresolved departure.
    """
    now = now or datetime.utcnow()
    recipient_id = recipient.get("id")
    night_start = recipient.get("night_hours_start", 22)
    night_end = recipient.get("night_hours_end", 6)

    # Get recent location events
    location_signals = [
        s for s in signals
        if s.get("signal_type") == "location_event"
        and s.get("care_recipient_id") == recipient_id
    ]

    if not location_signals:
        return None

    # Check for left-home events during night hours or device-flagged unresolved departures
    for sig in sorted(location_signals, key=lambda s: s.get("timestamp", ""), reverse=True):
        meta = sig.get("metadata", {})
        if not meta.get("left_home", False):
            continue

        ts = _parse_ts(sig.get("timestamp", ""))
        hour = ts.hour

        # Primary path: departure falls within configured night hours
        is_night = (hour >= night_start or hour < night_end)

        # Secondary path: smart-home device explicitly flags this as an unresolved
        # departure (returned_home=False is a direct sensor assertion, not an absence).
        # This covers UTC-stored timestamps that represent local nighttime departures,
        # and smart-home devices that directly signal an unresolved departure.
        device_flagged_unreturned = meta.get("returned_home") is False

        if not is_night and not device_flagged_unreturned:
            continue

        # Check if there's a return event within the window
        return_deadline = ts + timedelta(hours=return_window_hours)
        has_return = any(
            _parse_ts(s.get("timestamp", "")) > ts
            and _parse_ts(s.get("timestamp", "")) <= return_deadline
            and s.get("metadata", {}).get("returned_home", False)
            for s in location_signals
        )

        if has_return:
            continue

        # Still not returned — check if we're past the window
        if now < return_deadline:
            continue  # Not yet past the window

        # Build evidence — note the detection path for explainability
        if is_night:
            timing_note = f"during nighttime hours ({ts.strftime('%I:%M %p')} UTC)"
        else:
            timing_note = (
                f"at {ts.strftime('%I:%M %p')} UTC "
                f"(monitoring device flagged departure as unresolved)"
            )

        evidence = (
            f"An unexpected departure from home was detected {timing_note}, "
            f"with no return detected within "
            f"{return_window_hours:.0f} hour(s)."
        )
        action = "Consider checking in by phone or visiting to verify safety."

        return {
            "alert_id": generate_id(),
            "care_recipient_id": recipient_id,
            "alert_type": AlertType.SAFETY_ALERT.value,
            "category": InformationCategory.LOCATION_SAFETY.value,
            "severity": AlertSeverity.HIGH.value,
            "rule_fired": "night_wandering",
            "evidence_summary": evidence,
            "generated_at": now.isoformat() + "Z",
            "requires_tier": 1,
            "is_data_gap": False,
            "actionable_step": action,
            "evidence_data": {
                "departure_time": ts.isoformat(),
                "return_window_hours": return_window_hours,
                "has_return": False,
                "detection_path": "night_hours" if is_night else "device_flagged",
            },
        }

    return None


# ---------------------------------------------------------------------------
# Rule 4: Social Isolation
# ---------------------------------------------------------------------------

def check_social_isolation(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """
    If no logged social contact in N days, generate ISOLATION_ALERT.
    """
    now = now or datetime.utcnow()
    recipient_id = recipient.get("id")
    expected_days = recipient.get("social_contact_expected_days", 3)

    social_signals = [
        s for s in signals
        if s.get("signal_type") == "social_contact"
        and s.get("care_recipient_id") == recipient_id
    ]

    if not social_signals:
        days_without = 999
    else:
        latest = max(social_signals, key=lambda s: s.get("timestamp", ""))
        latest_time = _parse_ts(latest.get("timestamp", ""))
        days_without = (now - latest_time).total_seconds() / 86400

    if days_without <= expected_days:
        return None

    severity = AlertSeverity.LOW if days_without < expected_days * 2 else AlertSeverity.MEDIUM
    evidence = (
        f"No social contact (calls, visits, messages) has been logged "
        f"in the last {days_without:.0f} days (expected at least every {expected_days} days)."
    )
    trend = f"This is an extended period of {days_without:.0f} days without recorded social interaction."
    action = "Consider calling, visiting, or arranging a social activity."

    return {
        "alert_id": generate_id(),
        "care_recipient_id": recipient_id,
        "alert_type": AlertType.ISOLATION_ALERT.value,
        "category": InformationCategory.SOCIAL_ISOLATION_SIGNAL.value,
        "severity": severity.value,
        "rule_fired": "social_isolation",
        "evidence_summary": evidence,
        "generated_at": now.isoformat() + "Z",
        "requires_tier": 1,
        "is_data_gap": False,
        "trend_info": trend,
        "actionable_step": action,
        "evidence_data": {
            "days_without_contact": round(days_without, 1),
            "expected_every_days": expected_days,
        },
    }


# ---------------------------------------------------------------------------
# Rule 5: Data Gap (System Alert — NOT a health event)
# ---------------------------------------------------------------------------

def check_data_gap(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
    source_type: str = "device_heartbeat",
    expected_hours: Optional[float] = None,
) -> Optional[dict]:
    """
    If expected data source has 0 reports in window, generate DATA_GAP state.
    This is a SYSTEM alert, not a health event. Must NOT be phrased as a health concern.
    """
    now = now or datetime.utcnow()
    recipient_id = recipient.get("id")
    if expected_hours is None:
        expected_hours = recipient.get("device_heartbeat_expected_hours", 2.0)

    source_signals = [
        s for s in signals
        if s.get("signal_type") == source_type
        and s.get("care_recipient_id") == recipient_id
    ]

    if source_signals:
        latest = max(source_signals, key=lambda s: s.get("timestamp", ""))
        latest_time = _parse_ts(latest.get("timestamp", ""))
        hours_since = (now - latest_time).total_seconds() / 3600
    else:
        hours_since = 999

    if hours_since <= expected_hours:
        return None

    severity = AlertSeverity.LOW if hours_since < expected_hours * 3 else AlertSeverity.MEDIUM

    # IMPORTANT: This is a system/device alert, NOT phrased as a health event
    evidence = (
        f"No data has been received from the monitoring source ('{source_type}') "
        f"for {hours_since:.1f} hours (expected every {expected_hours:.0f} hours). "
        f"This may indicate a device or connectivity issue — it does not "
        f"necessarily reflect a change in wellbeing."
    )
    action = "Check if the monitoring device is charged, connected, and functioning properly."

    return {
        "alert_id": generate_id(),
        "care_recipient_id": recipient_id,
        "alert_type": AlertType.DATA_GAP.value,
        "category": InformationCategory.ACTIVITY_ENGAGEMENT.value,
        "severity": severity.value,
        "rule_fired": "data_gap",
        "evidence_summary": evidence,
        "generated_at": now.isoformat() + "Z",
        "requires_tier": 0,  # Data gaps are always shown (system status)
        "is_data_gap": True,
        "actionable_step": action,
        "evidence_data": {
            "source_type": source_type,
            "hours_since_last": round(hours_since, 1),
            "expected_interval_hours": expected_hours,
        },
    }


# ---------------------------------------------------------------------------
# Vitals summary rule (Tier 3, qualitative only)
# ---------------------------------------------------------------------------

def check_vitals_summary(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
) -> Optional[dict]:
    """
    Check if vitals readings are flagged outside normal range.
    IMPORTANT: Only outputs qualitative summaries, NEVER raw numeric values.
    """
    now = now or datetime.utcnow()
    recipient_id = recipient.get("id")

    vitals = [
        s for s in signals
        if s.get("signal_type") == "vitals_reading"
        and s.get("care_recipient_id") == recipient_id
    ]

    if not vitals:
        return None

    # Check for any flagged readings
    recent_vitals = sorted(vitals, key=lambda s: s.get("timestamp", ""), reverse=True)[:10]
    flagged = [v for v in recent_vitals if v.get("metadata", {}).get("flagged", False)]

    if not flagged:
        return None

    flagged_count = len(flagged)
    total_recent = len(recent_vitals)

    # QUALITATIVE ONLY — no raw values
    evidence = (
        f"Recent wellness readings show {flagged_count} of {total_recent} "
        f"readings flagged outside the expected range. No specific values are shown "
        f"in this view."
    )
    clinical = (
        f"Qualitative summary: {flagged_count} reading(s) were flagged outside "
        f"the expected baseline range in the recent monitoring window."
    )
    action = "Consider consulting with the care recipient's healthcare provider about recent monitoring trends."

    return {
        "alert_id": generate_id(),
        "care_recipient_id": recipient_id,
        "alert_type": AlertType.PATTERN_ALERT.value,
        "category": InformationCategory.VITALS_SUMMARY.value,
        "severity": AlertSeverity.MEDIUM.value if flagged_count <= 2 else AlertSeverity.HIGH.value,
        "rule_fired": "vitals_flagged",
        "evidence_summary": evidence,
        "generated_at": now.isoformat() + "Z",
        "requires_tier": 3,  # Clinical summary, restricted
        "is_data_gap": False,
        "clinical_note": clinical,
        "actionable_step": action,
        "evidence_data": {
            "flagged_count": flagged_count,
            "total_recent": total_recent,
            "qualitative_status": "outside_expected_range",
        },
    }


# ---------------------------------------------------------------------------
# Master rule runner
# ---------------------------------------------------------------------------

def run_all_rules(
    signals: List[dict],
    recipient: dict,
    now: Optional[datetime] = None,
) -> List[dict]:
    """
    Run all alert rules against signals for a care recipient.
    Returns a list of alert dicts (may be empty if no rules fire).
    """
    now = now or datetime.utcnow()
    alerts = []

    # Rule 1a: Missed check-in
    alert = check_missed_checkin(signals, recipient, now)
    if alert:
        alerts.append(alert)

    # Rule 1b: Missed medication check-in
    alert = check_missed_medication(signals, recipient, now)
    if alert:
        alerts.append(alert)

    # Rule 2: Activity deviation
    alert = check_activity_deviation(signals, recipient, now)
    if alert:
        alerts.append(alert)

    # Rule 3: Location/safety
    alert = check_location_safety(signals, recipient, now)
    if alert:
        alerts.append(alert)

    # Rule 4: Social isolation
    alert = check_social_isolation(signals, recipient, now)
    if alert:
        alerts.append(alert)

    # Rule 5: Data gap (check multiple sources)
    for source in ["device_heartbeat", "check_in", "activity_score"]:
        alert = check_data_gap(signals, recipient, now, source_type=source)
        if alert:
            alerts.append(alert)

    # Vitals summary (Tier 3)
    alert = check_vitals_summary(signals, recipient, now)
    if alert:
        alerts.append(alert)

    # Run content linter on all alerts
    for alert in alerts:
        evidence = alert.get("evidence_summary", "")
        sanitized, violations = sanitize_alert_text(evidence, alert.get("alert_type", "generic"))
        if violations:
            alert["evidence_summary"] = sanitized
            alert["_linter_violations"] = [v.to_dict() for v in violations]

        if alert.get("actionable_step"):
            sanitized_action, v2 = sanitize_alert_text(alert["actionable_step"], alert.get("alert_type", "generic"))
            if v2:
                alert["actionable_step"] = sanitized_action

    return alerts
