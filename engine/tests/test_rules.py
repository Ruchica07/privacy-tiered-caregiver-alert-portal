"""
Test suite for the Rules Engine.

Tests that:
1. Each rule fires correctly on synthetic anomalies
2. Rules produce properly structured alert objects
3. Rules do NOT fire on normal data
4. Edge cases: data storms, total outage
5. All alert text passes the content linter
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime, timedelta
from engine.rules import (
    check_missed_checkin, check_missed_medication,
    check_activity_deviation, check_location_safety,
    check_social_isolation, check_data_gap,
    check_vitals_summary, run_all_rules,
)
from engine.content_linter import is_compliant


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_recipient(**overrides):
    base = {
        "id": "cr_001",
        "name": "Test Recipient",
        "baseline_activity_mean": 50.0,
        "baseline_activity_stddev": 10.0,
        "expected_checkin_window_hours": 4.0,
        "expected_medication_window_hours": 12.0,
        "night_hours_start": 22,
        "night_hours_end": 6,
        "social_contact_expected_days": 3,
        "device_heartbeat_expected_hours": 2.0,
    }
    base.update(overrides)
    return base


NOW = datetime(2025, 6, 15, 12, 0, 0)


# ---------------------------------------------------------------------------
# Test Missed Check-in Rule
# ---------------------------------------------------------------------------

class TestMissedCheckin:

    def test_fires_when_overdue(self):
        """Should fire when no check-in in the expected window."""
        signals = [{
            "signal_id": "s1",
            "care_recipient_id": "cr_001",
            "signal_type": "check_in",
            "timestamp": (NOW - timedelta(hours=8)).isoformat() + "Z",
        }]
        recipient = make_recipient()
        alert = check_missed_checkin(signals, recipient, NOW)

        assert alert is not None
        assert alert["alert_type"] == "adherence_alert"
        assert alert["category"] == "activity_engagement"
        assert alert["requires_tier"] == 1
        assert is_compliant(alert["evidence_summary"])

    def test_does_not_fire_when_recent(self):
        """Should NOT fire when check-in is recent."""
        signals = [{
            "signal_id": "s1",
            "care_recipient_id": "cr_001",
            "signal_type": "check_in",
            "timestamp": (NOW - timedelta(hours=1)).isoformat() + "Z",
        }]
        recipient = make_recipient()
        alert = check_missed_checkin(signals, recipient, NOW)
        assert alert is None

    def test_severity_escalation(self):
        """Severity should increase with overdue duration."""
        # 2x overdue → medium
        signals_medium = [{
            "signal_id": "s1",
            "care_recipient_id": "cr_001",
            "signal_type": "check_in",
            "timestamp": (NOW - timedelta(hours=7)).isoformat() + "Z",
        }]
        alert_medium = check_missed_checkin(signals_medium, make_recipient(), NOW)
        assert alert_medium["severity"] in ["low", "medium"]

        # 5x overdue → critical
        signals_critical = [{
            "signal_id": "s1",
            "care_recipient_id": "cr_001",
            "signal_type": "check_in",
            "timestamp": (NOW - timedelta(hours=20)).isoformat() + "Z",
        }]
        alert_critical = check_missed_checkin(signals_critical, make_recipient(), NOW)
        assert alert_critical["severity"] in ["high", "critical"]

    def test_no_signals_at_all(self):
        """No signals at all should fire with high severity."""
        alert = check_missed_checkin([], make_recipient(), NOW)
        assert alert is not None
        assert alert["severity"] == "critical"


# ---------------------------------------------------------------------------
# Test Activity Deviation Rule
# ---------------------------------------------------------------------------

class TestActivityDeviation:

    def test_fires_on_low_scores(self):
        """Should fire when activity is below baseline for consecutive days."""
        signals = []
        for day_offset in range(7):
            ts = NOW - timedelta(days=day_offset)
            score = 15.0 if day_offset < 3 else 50.0  # Last 3 days very low
            signals.append({
                "signal_id": f"s_{day_offset}",
                "care_recipient_id": "cr_001",
                "signal_type": "activity_score",
                "timestamp": ts.isoformat() + "Z",
                "value": score,
            })

        recipient = make_recipient()
        alert = check_activity_deviation(signals, recipient, NOW)
        assert alert is not None
        assert alert["alert_type"] == "pattern_alert"
        assert alert["requires_tier"] == 2
        assert is_compliant(alert["evidence_summary"])

    def test_does_not_fire_normal_scores(self):
        """Should NOT fire when activity is within normal range."""
        signals = []
        for day_offset in range(7):
            ts = NOW - timedelta(days=day_offset)
            signals.append({
                "signal_id": f"s_{day_offset}",
                "care_recipient_id": "cr_001",
                "signal_type": "activity_score",
                "timestamp": ts.isoformat() + "Z",
                "value": 50.0,  # Normal
            })

        recipient = make_recipient()
        alert = check_activity_deviation(signals, recipient, NOW)
        assert alert is None


# ---------------------------------------------------------------------------
# Test Location Safety Rule
# ---------------------------------------------------------------------------

class TestLocationSafety:

    def test_fires_on_night_wandering(self):
        """Should fire when left home at night with no return."""
        wander_time = NOW.replace(hour=23, minute=15)
        # Set NOW to 2 hours after departure
        check_time = wander_time + timedelta(hours=2)

        signals = [{
            "signal_id": "loc_1",
            "care_recipient_id": "cr_001",
            "signal_type": "location_event",
            "timestamp": wander_time.isoformat() + "Z",
            "value": None,
            "metadata": {"left_home": True, "returned_home": False},
        }]

        recipient = make_recipient()
        alert = check_location_safety(signals, recipient, check_time)
        assert alert is not None
        assert alert["alert_type"] == "safety_alert"
        assert alert["severity"] == "high"
        assert is_compliant(alert["evidence_summary"])

    def test_does_not_fire_daytime_with_return(self):
        """Should NOT fire when a daytime departure is followed by a confirmed return."""
        signals = [{
            "signal_id": "loc_1",
            "care_recipient_id": "cr_001",
            "signal_type": "location_event",
            "timestamp": NOW.replace(hour=14).isoformat() + "Z",
            "value": None,
            # returned_home=True: device confirms the person came back — not an alert
            "metadata": {"left_home": True, "returned_home": True},
        }]

        alert = check_location_safety(signals, make_recipient(), NOW.replace(hour=16))
        assert alert is None

    def test_fires_for_device_flagged_unresolved_departure(self):
        """Should fire when a device explicitly flags an unresolved departure (returned_home=False),
        even during daytime UTC hours — this covers UTC-stored local nighttime timestamps
        and smart-home devices that directly assert departure status."""
        signals = [{
            "signal_id": "loc_2",
            "care_recipient_id": "cr_001",
            "signal_type": "location_event",
            "timestamp": NOW.replace(hour=11).isoformat() + "Z",
            "value": None,
            # returned_home=False: device directly asserts unresolved departure
            "metadata": {"left_home": True, "returned_home": False},
        }]

        alert = check_location_safety(signals, make_recipient(), NOW.replace(hour=16))
        assert alert is not None
        assert alert["alert_type"] == "safety_alert"
        assert alert["evidence_data"]["detection_path"] == "device_flagged"
        assert is_compliant(alert["evidence_summary"])


# ---------------------------------------------------------------------------
# Test Social Isolation Rule
# ---------------------------------------------------------------------------

class TestSocialIsolation:

    def test_fires_when_no_contacts(self):
        """Should fire when no social contact exceeds threshold."""
        signals = [{
            "signal_id": "sc_1",
            "care_recipient_id": "cr_001",
            "signal_type": "social_contact",
            "timestamp": (NOW - timedelta(days=5)).isoformat() + "Z",
        }]

        recipient = make_recipient(social_contact_expected_days=3)
        alert = check_social_isolation(signals, recipient, NOW)
        assert alert is not None
        assert alert["alert_type"] == "isolation_alert"
        assert is_compliant(alert["evidence_summary"])

    def test_does_not_fire_recent_contact(self):
        """Should NOT fire when recent contact exists."""
        signals = [{
            "signal_id": "sc_1",
            "care_recipient_id": "cr_001",
            "signal_type": "social_contact",
            "timestamp": (NOW - timedelta(days=1)).isoformat() + "Z",
        }]

        alert = check_social_isolation(signals, make_recipient(), NOW)
        assert alert is None


# ---------------------------------------------------------------------------
# Test Data Gap Rule
# ---------------------------------------------------------------------------

class TestDataGap:

    def test_fires_when_no_heartbeat(self):
        """Should fire when device heartbeat is missing."""
        signals = [{
            "signal_id": "hb_1",
            "care_recipient_id": "cr_001",
            "signal_type": "device_heartbeat",
            "timestamp": (NOW - timedelta(hours=5)).isoformat() + "Z",
        }]

        recipient = make_recipient(device_heartbeat_expected_hours=2.0)
        alert = check_data_gap(signals, recipient, NOW)
        assert alert is not None
        assert alert["is_data_gap"] is True
        assert alert["requires_tier"] == 0  # System status, always visible
        assert "device" in alert["evidence_summary"].lower() or "connectivity" in alert["evidence_summary"].lower()
        assert is_compliant(alert["evidence_summary"])

    def test_data_gap_not_phrased_as_health_event(self):
        """Data gap alert must NOT be phrased as a health event."""
        alert = check_data_gap([], make_recipient(), NOW)
        assert alert is not None
        text = alert["evidence_summary"]
        assert "device" in text.lower() or "connectivity" in text.lower() or "monitoring source" in text.lower()
        # Should NOT contain health-event language
        assert "health" not in text.lower() or "wellbeing" in text.lower()


# ---------------------------------------------------------------------------
# Test run_all_rules
# ---------------------------------------------------------------------------

class TestRunAllRules:

    def test_all_alerts_have_required_fields(self):
        """All generated alerts must have the required structured fields."""
        required_fields = [
            "alert_id", "care_recipient_id", "alert_type", "category",
            "severity", "rule_fired", "evidence_summary", "generated_at",
            "requires_tier", "is_data_gap",
        ]
        alerts = run_all_rules([], make_recipient(), NOW)

        for alert in alerts:
            for field in required_fields:
                assert field in alert, f"Missing field '{field}' in alert: {alert}"

    def test_all_alert_text_passes_linter(self):
        """CRITICAL: Every alert's text must pass the content linter."""
        # Generate alerts with various conditions
        signals = [
            {"signal_id": "s1", "care_recipient_id": "cr_001",
             "signal_type": "check_in",
             "timestamp": (NOW - timedelta(hours=8)).isoformat() + "Z"},
        ]
        alerts = run_all_rules(signals, make_recipient(), NOW)

        for alert in alerts:
            assert is_compliant(alert["evidence_summary"]), (
                f"Alert evidence fails linter: {alert['evidence_summary']}"
            )
            if alert.get("actionable_step"):
                assert is_compliant(alert["actionable_step"]), (
                    f"Alert action fails linter: {alert['actionable_step']}"
                )


# ---------------------------------------------------------------------------
# Edge Case 2: Conflicting/stacked signals (data storm)
# ---------------------------------------------------------------------------

class TestDataStorm:

    def test_multiple_anomalies_not_combined_into_diagnosis(self):
        """
        When multiple anomalies fire, they must remain separate operational
        signals, not be combined into a scarier diagnosis-like composite.
        """
        signals = [
            # Missed check-in
            {"signal_id": "s1", "care_recipient_id": "cr_001",
             "signal_type": "check_in",
             "timestamp": (NOW - timedelta(hours=10)).isoformat() + "Z"},
            # Device offline
            {"signal_id": "s2", "care_recipient_id": "cr_001",
             "signal_type": "device_heartbeat",
             "timestamp": (NOW - timedelta(hours=5)).isoformat() + "Z"},
        ]

        alerts = run_all_rules(signals, make_recipient(), NOW)
        # Should have separate alerts, not one combined alert
        alert_types = [a["alert_type"] for a in alerts]

        # Each alert should stand alone — no combined/composite alerts
        for alert in alerts:
            text = alert["evidence_summary"]
            assert is_compliant(text)
            # Should not contain compound diagnostic language
            assert "and therefore" not in text.lower()
            assert "combined with" not in text.lower()


# ---------------------------------------------------------------------------
# Edge Case 3: Total data outage
# ---------------------------------------------------------------------------

class TestTotalOutage:

    def test_no_signals_generates_data_gaps(self):
        """Total data outage must generate data-gap alerts, not silence."""
        alerts = run_all_rules([], make_recipient(), NOW)

        data_gap_alerts = [a for a in alerts if a["is_data_gap"]]
        assert len(data_gap_alerts) > 0, "Total outage must produce data-gap alerts"

        # Verify none are phrased as health events
        for alert in data_gap_alerts:
            assert "device" in alert["evidence_summary"].lower() or \
                   "monitoring" in alert["evidence_summary"].lower() or \
                   "connectivity" in alert["evidence_summary"].lower()
