"""
Test suite for the Consent Filter — highest priority test coverage.

Tests that:
1. Consent lookup works correctly for granted/revoked/pending/expired states
2. Tier-based rendering redacts fields above the caregiver's tier
3. Consent revocation mid-stream works immediately
4. Expired consent auto-drops to no access
5. Audit details are always produced
6. Data-gap alerts are shown even without category consent (system status)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from datetime import datetime, timedelta
from engine.consent_filter import (
    lookup_consent, filter_alert_for_caregiver,
    filter_alerts_for_caregiver, get_caregiver_access_summary,
    TIER0_SUMMARIES,
)
from engine.models import InformationCategory, ConsentStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_consent(caregiver_id, category, tier, status="granted", expires_at=None):
    return {
        "consent_id": "test",
        "care_recipient_id": "cr_001",
        "caregiver_id": caregiver_id,
        "category": category,
        "max_tier": tier,
        "consent_status": status,
        "granted_at": "2025-01-01T00:00:00Z",
        "expires_at": expires_at,
    }


def make_alert(category="activity_engagement", requires_tier=1, severity="medium",
               alert_type="adherence_alert", is_data_gap=False):
    return {
        "alert_id": "alert_001",
        "care_recipient_id": "cr_001",
        "alert_type": alert_type,
        "category": category,
        "severity": severity,
        "rule_fired": "test_rule",
        "evidence_summary": "No check-in received in the last 6 hours.",
        "generated_at": "2025-06-15T12:00:00Z",
        "requires_tier": requires_tier,
        "is_data_gap": is_data_gap,
        "trend_info": "This is the 3rd missed check-in this week.",
        "clinical_note": "Readings flagged outside expected range.",
        "actionable_step": "Consider reaching out to check in.",
        "evidence_data": {"hours_overdue": 6.0},
    }


# ---------------------------------------------------------------------------
# Test consent lookup
# ---------------------------------------------------------------------------

class TestConsentLookup:

    def test_granted_consent(self):
        matrix = [make_consent("cg_001", "activity_engagement", 2)]
        record, tier = lookup_consent("cg_001", InformationCategory.ACTIVITY_ENGAGEMENT, matrix)
        assert tier == 2
        assert record is not None

    def test_revoked_consent(self):
        matrix = [make_consent("cg_001", "activity_engagement", 2, status="revoked")]
        record, tier = lookup_consent("cg_001", InformationCategory.ACTIVITY_ENGAGEMENT, matrix)
        assert tier == -1

    def test_pending_consent(self):
        matrix = [make_consent("cg_001", "activity_engagement", 2, status="pending")]
        record, tier = lookup_consent("cg_001", InformationCategory.ACTIVITY_ENGAGEMENT, matrix)
        assert tier == -1

    def test_expired_consent(self):
        past = (datetime.utcnow() - timedelta(days=1)).isoformat() + "Z"
        matrix = [make_consent("cg_001", "activity_engagement", 2, expires_at=past)]
        record, tier = lookup_consent("cg_001", InformationCategory.ACTIVITY_ENGAGEMENT, matrix)
        assert tier == -1

    def test_not_yet_expired_consent(self):
        future = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
        matrix = [make_consent("cg_001", "activity_engagement", 2, expires_at=future)]
        record, tier = lookup_consent("cg_001", InformationCategory.ACTIVITY_ENGAGEMENT, matrix)
        assert tier == 2

    def test_no_consent_record(self):
        matrix = []
        record, tier = lookup_consent("cg_001", InformationCategory.ACTIVITY_ENGAGEMENT, matrix)
        assert record is None
        assert tier == -1

    def test_wrong_caregiver(self):
        matrix = [make_consent("cg_002", "activity_engagement", 2)]
        record, tier = lookup_consent("cg_001", InformationCategory.ACTIVITY_ENGAGEMENT, matrix)
        assert record is None
        assert tier == -1


# ---------------------------------------------------------------------------
# Test tier-based rendering
# ---------------------------------------------------------------------------

class TestTierRendering:

    def test_tier0_binary_only(self):
        """Tier 0 should show only binary wellness ping, no category detail."""
        matrix = [make_consent("cg_001", "activity_engagement", 0)]
        alert = make_alert(requires_tier=0)
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is not None
        assert rendered["rendered_tier"] == 0
        assert rendered["category"] == "general"  # Category hidden
        assert rendered["rule_fired"] == ""        # Rule hidden
        assert "evidence_summary" not in rendered
        assert "trend_info" not in rendered
        assert "clinical_note" not in rendered

    def test_tier1_shows_category_and_evidence(self):
        """Tier 1 should show category and evidence but no trend or clinical."""
        matrix = [make_consent("cg_001", "activity_engagement", 1)]
        alert = make_alert(requires_tier=1)
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is not None
        assert rendered["rendered_tier"] == 1
        assert rendered["category"] == "activity_engagement"
        assert "evidence_summary" in rendered
        assert "trend_info" not in rendered
        assert "clinical_note" not in rendered

    def test_tier2_shows_trend(self):
        """Tier 2 should include trend information."""
        matrix = [make_consent("cg_001", "activity_engagement", 2)]
        alert = make_alert(requires_tier=1)  # Alert requires only tier 1
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is not None
        # Should render at alert's required tier, not caregiver's max
        assert rendered["rendered_tier"] == 1

    def test_tier2_alert_shows_trend_data(self):
        """Tier 2 alert to tier 2 caregiver should show trend."""
        matrix = [make_consent("cg_001", "activity_engagement", 2)]
        alert = make_alert(requires_tier=2)
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is not None
        assert rendered["rendered_tier"] == 2
        assert "trend_info" in rendered
        assert "evidence_data" in rendered
        assert "clinical_note" not in rendered

    def test_tier3_shows_clinical_note(self):
        """Tier 3 should include clinical note."""
        matrix = [make_consent("cg_001", "activity_engagement", 3)]
        alert = make_alert(requires_tier=3)
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is not None
        assert rendered["rendered_tier"] == 3
        assert "clinical_note" in rendered


# ---------------------------------------------------------------------------
# Test privacy guarantees
# ---------------------------------------------------------------------------

class TestPrivacyGuarantees:

    def test_no_consent_withholds_alert(self):
        """Without consent, alert must be withheld entirely."""
        matrix = []
        alert = make_alert()
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is None
        assert audit["decision"] == "withheld"

    def test_revoked_consent_withholds_alert(self):
        """Revoked consent must immediately withhold alerts."""
        matrix = [make_consent("cg_001", "activity_engagement", 2, status="revoked")]
        alert = make_alert()
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is None
        assert audit["decision"] == "withheld"

    def test_consent_revoked_midstream(self):
        """
        Edge Case 1: Consent revoked mid-stream.
        First alert at Tier 2, then consent revoked, second alert must be withheld.
        """
        # First: consent granted at Tier 2
        matrix = [make_consent("cg_001", "activity_engagement", 2)]
        alert1 = make_alert()
        rendered1, _ = filter_alert_for_caregiver(alert1, "cg_001", matrix)
        assert rendered1 is not None  # First alert shown

        # Then: consent revoked
        matrix[0]["consent_status"] = "revoked"
        alert2 = make_alert()
        alert2["alert_id"] = "alert_002"
        rendered2, audit2 = filter_alert_for_caregiver(alert2, "cg_001", matrix)
        assert rendered2 is None  # Second alert must be withheld
        assert audit2["decision"] == "withheld"

    def test_expired_consent_withholds(self):
        """
        Edge Case 4: Expired consent must drop access.
        """
        past = (datetime.utcnow() - timedelta(hours=1)).isoformat() + "Z"
        matrix = [make_consent("cg_001", "activity_engagement", 2, expires_at=past)]
        alert = make_alert()
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is None
        assert audit["decision"] == "withheld"

    def test_downgraded_tier_never_exceeds_consent(self):
        """Rendered tier must NEVER exceed the consented tier."""
        matrix = [make_consent("cg_001", "activity_engagement", 1)]
        alert = make_alert(requires_tier=2)  # Alert wants Tier 2
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is not None
        assert rendered["rendered_tier"] <= 1
        assert "trend_info" not in rendered  # Tier 1 should NOT have trend

    def test_data_gap_shown_without_consent(self):
        """Data-gap alerts (system status) should be shown even without consent."""
        matrix = []  # No consent at all
        alert = make_alert(is_data_gap=True, requires_tier=0, alert_type="data_gap")
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is not None
        assert rendered["rendered_tier"] == 0
        assert audit["decision"] == "shown_as_tier0_data_gap"

    def test_unknown_category_fails_safe(self):
        """Unknown category must fail safe — withhold the alert."""
        matrix = [make_consent("cg_001", "unknown_category", 2)]
        alert = make_alert(category="totally_unknown_cat")
        rendered, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert rendered is None
        assert audit["decision"] == "withheld"


# ---------------------------------------------------------------------------
# Test audit trail
# ---------------------------------------------------------------------------

class TestAuditTrail:

    def test_audit_always_produced(self):
        """Every filter call must produce audit details."""
        matrix = [make_consent("cg_001", "activity_engagement", 2)]
        alert = make_alert()
        _, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert "decision" in audit
        assert "caregiver_id" in audit
        assert audit["caregiver_id"] == "cg_001"

    def test_audit_on_withheld(self):
        """Withheld alerts must have audit with reason."""
        matrix = []
        alert = make_alert()
        _, audit = filter_alert_for_caregiver(alert, "cg_001", matrix)

        assert audit["decision"] == "withheld"
        assert "reason" in audit


# ---------------------------------------------------------------------------
# Test batch filtering
# ---------------------------------------------------------------------------

class TestBatchFiltering:

    def test_batch_filters_correctly(self):
        """Batch filtering should produce correct results for mixed consent."""
        matrix = [
            make_consent("cg_001", "activity_engagement", 2),
            # No consent for medication_adherence
        ]
        alerts = [
            make_alert(category="activity_engagement"),
            make_alert(category="medication_adherence"),
        ]
        rendered, audit_log = filter_alerts_for_caregiver(alerts, "cg_001", matrix)

        assert len(rendered) == 1  # Only activity alert shown
        assert len(audit_log) == 2  # Both have audit entries
        assert rendered[0]["category"] == "activity_engagement"


# ---------------------------------------------------------------------------
# Test access summary
# ---------------------------------------------------------------------------

class TestAccessSummary:

    def test_summary_shows_accessible_and_restricted(self):
        """Access summary should correctly categorize accessible vs restricted."""
        matrix = [
            make_consent("cg_001", "activity_engagement", 2),
            make_consent("cg_001", "medication_adherence", 1),
            make_consent("cg_001", "vitals_summary", 0, status="revoked"),
        ]
        summary = get_caregiver_access_summary("cg_001", "cr_001", matrix)

        assert len(summary["accessible_categories"]) == 2
        assert len(summary["restricted_categories"]) >= 1
        assert summary["overall_tier"] == 2


# ---------------------------------------------------------------------------
# Disclosure rate test (core privacy metric)
# ---------------------------------------------------------------------------

def test_zero_unnecessary_disclosure():
    """
    CORE PRIVACY METRIC: No rendered alert should exceed the caregiver's consented tier.
    This is the 0% unnecessary disclosure requirement.
    """
    from engine.models import InformationCategory

    # Create a comprehensive matrix and alert set
    categories = [c.value for c in InformationCategory]
    tiers = [0, 1, 2, 3]

    for cat in categories:
        for max_tier in tiers:
            for requires_tier in tiers:
                matrix = [make_consent("cg_test", cat, max_tier)]
                alert = make_alert(category=cat, requires_tier=requires_tier)
                rendered, _ = filter_alert_for_caregiver(alert, "cg_test", matrix)

                if rendered is not None:
                    assert rendered["rendered_tier"] <= max_tier, (
                        f"DISCLOSURE VIOLATION: cat={cat}, max_tier={max_tier}, "
                        f"requires_tier={requires_tier}, rendered_tier={rendered['rendered_tier']}"
                    )
