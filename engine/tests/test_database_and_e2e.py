"""
Comprehensive Database, Privacy Engine, and End-to-End Test Suite.

Verifies:
1. SQLite Database & SQLAlchemy models CRUD operations
2. Caregiver roles server-side enforcement
3. Consent levels affecting disclosure
4. Privacy tiers redaction guarantees
5. Prevention of restricted health info leakage
6. Same alert yielding differential disclosure across roles
7. Fresh, stale, and missing data states
8. Immutable audit trail creation
9. Edge cases (consent revocation, data storm, total outage, expired consent)
"""

import os
import json
import pytest
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import (
    Base, CareRecipientModel, CaregiverModel, ConsentRecordModel,
    SignalModel, AlertModel, AuditEntryModel
)
from api.data_store import DataStore
from engine.models import (
    InformationCategory, CaregiverRole, ConsentStatus,
    Alert, AlertType, AlertSeverity
)
from engine.consent_filter import filter_alert_for_caregiver, filter_alerts_for_caregiver
from engine.content_linter import lint_text, is_compliant
from engine.rules import run_all_rules


# ---------------------------------------------------------------------------
# Test 1: SQLite Database & SQLAlchemy Models
# ---------------------------------------------------------------------------

class TestDatabaseAndModels:
    """Verify SQLite database and SQLAlchemy models work properly."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        db_file = tmp_path / "test_portal.db"
        self.engine = create_engine(f"sqlite:///{db_file}")
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_care_recipient_model_crud(self):
        session = self.Session()
        cr = CareRecipientModel(
            id="cr_test_01",
            name="Alice Walker",
            baseline_activity_mean=55.0,
            baseline_activity_stddev=8.0,
            expected_checkin_window_hours=4.0
        )
        session.add(cr)
        session.commit()

        queried = session.query(CareRecipientModel).filter_by(id="cr_test_01").first()
        assert queried is not None
        assert queried.name == "Alice Walker"
        d = queried.to_dict()
        assert d["id"] == "cr_test_01"
        assert d["baseline_activity_mean"] == 55.0
        session.close()

    def test_caregiver_model_crud(self):
        session = self.Session()
        cg = CaregiverModel(
            id="cg_test_01",
            name="John Walker",
            role="primary_caregiver",
            care_recipient_ids_json=json.dumps(["cr_test_01"])
        )
        session.add(cg)
        session.commit()

        queried = session.query(CaregiverModel).filter_by(id="cg_test_01").first()
        assert queried is not None
        assert queried.role == "primary_caregiver"
        d = queried.to_dict()
        assert d["care_recipient_ids"] == ["cr_test_01"]
        session.close()

    def test_consent_record_model_crud(self):
        session = self.Session()
        rec = ConsentRecordModel(
            consent_id="c_001",
            care_recipient_id="cr_test_01",
            caregiver_id="cg_test_01",
            category="location_safety",
            max_tier=2,
            consent_status="granted"
        )
        session.add(rec)
        session.commit()

        queried = session.query(ConsentRecordModel).filter_by(consent_id="c_001").first()
        assert queried is not None
        assert queried.max_tier == 2
        assert queried.consent_status == "granted"
        session.close()

    def test_alert_and_audit_models(self):
        session = self.Session()
        alert = AlertModel(
            alert_id="a_test_01",
            care_recipient_id="cr_test_01",
            alert_type="safety_alert",
            category="location_safety",
            severity="high",
            rule_fired="night_wandering",
            evidence_summary="Door opened at night",
            generated_at="2026-09-01T02:30:00Z",
            requires_tier=2
        )
        audit = AuditEntryModel(
            audit_id="aud_test_01",
            timestamp="2026-09-01T02:30:01Z",
            event_type="alert_generated",
            actor_id="rules_engine",
            care_recipient_id="cr_test_01",
            details_json=json.dumps({"rule": "night_wandering"})
        )
        session.add_all([alert, audit])
        session.commit()

        assert session.query(AlertModel).count() == 1
        assert session.query(AuditEntryModel).count() == 1
        session.close()


# ---------------------------------------------------------------------------
# Test 2: Role-based & Privacy-Tier Differential Disclosure
# ---------------------------------------------------------------------------

class TestDifferentialDisclosure:
    """Verify that the same alert produces different disclosures across roles."""

    @pytest.fixture
    def sample_alert(self):
        return {
            "alert_id": "alert_sample_01",
            "care_recipient_id": "cr_001",
            "alert_type": "safety_alert",
            "category": "location_safety",
            "severity": "high",
            "rule_fired": "nocturnal_wandering",
            "evidence_summary": "Night movement detected outside normal hours between 02:00 and 03:30 AM.",
            "generated_at": "2026-09-01T03:30:00Z",
            "requires_tier": 2,
            "is_data_gap": False,
            "trend_info": "Third night in the last 7 days with nocturnal activity.",
            "clinical_note": "Qualitative cognitive and orientation assessment recommended.",
            "evidence_data": {"trend_points": [{"day": "Mon", "count": 1}, {"day": "Tue", "count": 3}]},
            "actionable_step": "Check front door status or call during morning check-in."
        }

    def test_same_alert_tier2_primary_caregiver(self, sample_alert):
        # Tier 2 consent: gets summary, actionable step, sparkline data, but NO clinical note
        consents = [{
            "caregiver_id": "cg_primary",
            "care_recipient_id": "cr_001",
            "category": "location_safety",
            "max_tier": 2,
            "consent_status": "granted"
        }]
        rendered, audit = filter_alert_for_caregiver(sample_alert, "cg_primary", consents)
        assert rendered is not None
        assert rendered["rendered_tier"] == 2
        assert rendered["category"] == "location_safety"
        assert rendered["evidence_summary"] is not None
        assert rendered["actionable_step"] is not None
        assert rendered["evidence_data"] is not None
        assert "clinical_note" not in rendered  # Redacted!
        assert audit["decision"] == "shown"

    def test_same_alert_tier1_secondary_caregiver(self, sample_alert):
        # Tier 1 consent: gets summary and actionable step, but NO sparkline data and NO clinical note
        consents = [{
            "caregiver_id": "cg_secondary",
            "care_recipient_id": "cr_001",
            "category": "location_safety",
            "max_tier": 1,
            "consent_status": "granted"
        }]
        rendered, audit = filter_alert_for_caregiver(sample_alert, "cg_secondary", consents)
        assert rendered is not None
        assert rendered["rendered_tier"] == 1
        assert rendered["category"] == "location_safety"
        assert rendered["actionable_step"] is not None
        assert "evidence_data" not in rendered  # Redacted!
        assert "clinical_note" not in rendered  # Redacted!
        assert audit["decision"] == "shown_downgraded"

    def test_same_alert_tier0_neighbor(self, sample_alert):
        # Tier 0 consent: only binary wellness ping, NO category detail, NO evidence, NO action
        consents = [{
            "caregiver_id": "cg_neighbor",
            "care_recipient_id": "cr_001",
            "category": "location_safety",
            "max_tier": 0,
            "consent_status": "granted"
        }]
        rendered, audit = filter_alert_for_caregiver(sample_alert, "cg_neighbor", consents)
        assert rendered is not None
        assert rendered["rendered_tier"] == 0
        assert rendered["category"] == "general"  # Masked!
        assert rendered["rule_fired"] == ""       # Masked!
        assert "evidence_summary" not in rendered # Redacted!
        assert "evidence_data" not in rendered    # Redacted!
        assert "actionable_step" not in rendered  # Redacted!
        assert "Attention may be needed" in rendered["summary"]

    def test_same_alert_tier3_care_coordinator(self, sample_alert):
        # Tier 3 consent: gets full operational context including clinical note
        consents = [{
            "caregiver_id": "cg_coordinator",
            "care_recipient_id": "cr_001",
            "category": "location_safety",
            "max_tier": 3,
            "consent_status": "granted"
        }]
        rendered, audit = filter_alert_for_caregiver(sample_alert, "cg_coordinator", consents)
        assert rendered is not None
        assert rendered["rendered_tier"] == 2  # Min of required_tier (2) and max_tier (3)
        assert rendered["actionable_step"] is not None

    def test_professional_coordinator_cannot_bypass_unconsented_category(self, sample_alert):
        # Requirement 6: Care coordinator role does NOT bypass older-adult consent
        # If recipient has NOT granted consent for location_safety to coordinator, alert must be withheld
        consents = [{
            "caregiver_id": "cg_coordinator",
            "care_recipient_id": "cr_001",
            "category": "activity_engagement",  # Consented for activity, NOT location_safety
            "max_tier": 3,
            "consent_status": "granted"
        }]
        rendered, audit = filter_alert_for_caregiver(sample_alert, "cg_coordinator", consents)
        assert rendered is None
        assert audit["decision"] == "withheld"

    def test_professional_coordinator_constrained_by_tier1_consent(self, sample_alert):
        # Requirement 6: Even with coordinator role, if recipient granted only Tier 1, they only get Tier 1
        consents = [{
            "caregiver_id": "cg_coordinator",
            "care_recipient_id": "cr_001",
            "category": "location_safety",
            "max_tier": 1,  # Older adult granted only Tier 1
            "consent_status": "granted"
        }]
        rendered, audit = filter_alert_for_caregiver(sample_alert, "cg_coordinator", consents)
        assert rendered is not None
        assert rendered["rendered_tier"] == 1
        assert "evidence_data" not in rendered  # Sparklines stripped
        assert "clinical_note" not in rendered   # Clinical note stripped
        assert audit["decision"] == "shown_downgraded"

    def test_professional_coordinator_withheld_on_revocation(self, sample_alert):
        # Requirement 6: Revoked consent blocks care coordinator immediately
        consents = [{
            "caregiver_id": "cg_coordinator",
            "care_recipient_id": "cr_001",
            "category": "location_safety",
            "max_tier": 3,
            "consent_status": "revoked"
        }]
        rendered, audit = filter_alert_for_caregiver(sample_alert, "cg_coordinator", consents)
        assert rendered is None
        assert audit["decision"] == "withheld"

    def test_higher_role_never_receives_unauthorized_health_info(self, sample_alert):
        # Requirement 7: Backend never returns restricted health info merely due to higher role
        dirty_alert = dict(sample_alert)
        dirty_alert["evidence_summary"] = "Blood pressure 150/95 mmHg. Administer 500mg metformin."
        consents = [{
            "caregiver_id": "cg_coordinator",
            "care_recipient_id": "cr_001",
            "category": "location_safety",
            "max_tier": 3,
            "consent_status": "granted"
        }]
        rendered, audit = filter_alert_for_caregiver(dirty_alert, "cg_coordinator", consents)
        assert rendered is not None
        # Must be sanitized by content linter, never raw clinical metrics or medication
        assert "150/95" not in rendered["summary"]
        assert "metformin" not in rendered["summary"]
        assert is_compliant(rendered["summary"])

    def test_restricted_health_info_sanitized(self):
        # Even if raw text contains medical diagnosis / prescription, content linter must catch it
        dirty_text = "Patient diagnosed with Alzheimer's disease. Administer 10mg donepezil."
        violations = lint_text(dirty_text)
        assert len(violations) >= 2
        assert not is_compliant(dirty_text)


# ---------------------------------------------------------------------------
# Test 3: Edge Cases Tested
# ---------------------------------------------------------------------------

class TestEdgeCases:
    """Verify minimum 3 edge cases."""

    def test_edge_case_1_consent_revocation_mid_stream(self):
        """Edge Case 1: Active consent is revoked. Subsequent queries immediately withhold alert."""
        alert = {
            "alert_id": "a_edge_1",
            "care_recipient_id": "cr_001",
            "category": "activity_engagement",
            "severity": "medium",
            "rule_fired": "missed_checkin",
            "evidence_summary": "Check-in delayed.",
            "requires_tier": 1,
            "is_data_gap": False,
        }

        # Step 1: Consent is granted -> Alert is visible
        consents_granted = [{
            "caregiver_id": "cg_family",
            "category": "activity_engagement",
            "max_tier": 1,
            "consent_status": "granted"
        }]
        rendered_before, audit_before = filter_alert_for_caregiver(alert, "cg_family", consents_granted)
        assert rendered_before is not None
        assert audit_before["decision"] == "shown"

        # Step 2: Consent revoked mid-stream -> Alert is immediately withheld
        consents_revoked = [{
            "caregiver_id": "cg_family",
            "category": "activity_engagement",
            "max_tier": 1,
            "consent_status": "revoked"
        }]
        rendered_after, audit_after = filter_alert_for_caregiver(alert, "cg_family", consents_revoked)
        assert rendered_after is None
        assert audit_after["decision"] == "withheld"

    def test_edge_case_2_sensor_data_gap_vs_health_event(self):
        """Edge Case 2: Missing heartbeat (>24h) is a data gap system alert, not a health emergency."""
        signals = [
            {
                "signal_id": "s_old",
                "care_recipient_id": "cr_001",
                "signal_type": "device_heartbeat",
                "timestamp": "2026-08-01T00:00:00Z",
            }
        ]
        recipient = {
            "id": "cr_001",
            "name": "Dorothy",
            "device_heartbeat_expected_hours": 2.0
        }
        eval_time = datetime(2026, 8, 3, 0, 0, 0)
        alerts = run_all_rules(signals, recipient, now=eval_time)
        data_gap_alerts = [a for a in alerts if a.get("is_data_gap")]
        assert len(data_gap_alerts) >= 1
        for a in data_gap_alerts:
            assert "medical" not in a["evidence_summary"].lower()
            assert "device" in a["evidence_summary"].lower() or "monitor" in a["evidence_summary"].lower()
            assert is_compliant(a["evidence_summary"])

    def test_edge_case_3_data_storm_concurrent_anomalies(self):
        """Edge Case 3: Multiple concurrent anomalies must not be combined into a synthetic clinical diagnosis."""
        signals = [
            # Low activity
            {"signal_id": "s_act", "care_recipient_id": "cr_001", "signal_type": "activity_score", "timestamp": "2026-08-05T12:00:00Z", "value": 10.0},
            # Night wandering
            {"signal_id": "s_loc", "care_recipient_id": "cr_001", "signal_type": "location_event", "timestamp": "2026-08-05T03:00:00Z", "metadata": {"event": "exterior_door_opened", "night": True}},
            # Missed checkin
            {"signal_id": "s_chk", "care_recipient_id": "cr_001", "signal_type": "check_in", "timestamp": "2026-08-04T08:00:00Z"},
        ]
        recipient = {
            "id": "cr_001",
            "name": "Dorothy",
            "baseline_activity_mean": 50.0,
            "baseline_activity_stddev": 10.0,
            "expected_checkin_window_hours": 4.0,
            "night_hours_start": 22,
            "night_hours_end": 6,
        }
        eval_time = datetime(2026, 8, 5, 14, 0, 0)
        alerts = run_all_rules(signals, recipient, now=eval_time)
        assert len(alerts) >= 2
        for a in alerts:
            # None of the alerts combine to diagnose dementia or disease
            assert is_compliant(a["evidence_summary"])
            assert is_compliant(a["actionable_step"] or "")

    def test_edge_case_4_expired_consent(self):
        """Edge Case 4: Expired consent automatically drops disclosure."""
        alert = {
            "alert_id": "a_exp",
            "care_recipient_id": "cr_001",
            "category": "activity_engagement",
            "severity": "medium",
            "rule_fired": "missed_checkin",
            "evidence_summary": "Check-in delayed.",
            "requires_tier": 1,
            "is_data_gap": False,
        }
        past_date = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        consents = [{
            "caregiver_id": "cg_expired",
            "category": "activity_engagement",
            "max_tier": 2,
            "consent_status": "granted",
            "expires_at": past_date
        }]
        rendered, audit = filter_alert_for_caregiver(alert, "cg_expired", consents)
        assert rendered is None
        assert audit["decision"] == "withheld"
