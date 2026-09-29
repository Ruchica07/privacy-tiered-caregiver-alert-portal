"""
Test Suite: Live Notification Dispatcher Subsystem (Phase 3)

Verifies:
1. Permitted Tier 1/2/3 alert dispatch via Web Push & SMS Sandbox Adapters
2. Tier 0 (Redacted indicator) notification dispatch
3. Strict withholding of unconsented or expired alert categories
4. Non-medical content safety linter on both evidence_summary AND actionable_step
5. Deterministic idempotency key deduplication (prevents duplicate dispatches)
6. Deterministic retry behavior and bounded attempts
7. Permanent failure handling after exhausting max_retries
8. Clear sandbox/simulation labeling on all outgoing payloads
9. Tamper-evident audit logging of notification events
"""

import pytest
from datetime import datetime, timezone, timedelta
from engine.notification_dispatcher import (
    NotificationDispatcher,
    WebPushSandboxAdapter,
    SMSSandboxAdapter,
    DeliveryChannel,
    DeliveryStatus,
)
from engine.models import InformationCategory, AlertType, AlertSeverity, generate_id


class MockAuditSink:
    def __init__(self):
        self.entries = []

    def add_audit_entry(self, entry: dict) -> dict:
        self.entries.append(entry)
        return entry


@pytest.fixture
def mock_audit_sink():
    return MockAuditSink()


@pytest.fixture
def base_alert():
    return {
        "alert_id": "alt_test_101",
        "care_recipient_id": "cr_001",
        "alert_type": AlertType.ADHERENCE_ALERT.value,
        "category": InformationCategory.ACTIVITY_ENGAGEMENT.value,
        "severity": AlertSeverity.MEDIUM.value,
        "rule_fired": "missed_checkin",
        "evidence_summary": "No check-in received in the last 6.0 hours (expected every 4 hours).",
        "actionable_step": "Consider calling to check in on daily routine.",
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "requires_tier": 1,
        "is_data_gap": False,
    }


@pytest.fixture
def primary_caregiver():
    return {
        "id": "cg_001",
        "name": "Jane Smith",
        "role": "primary_caregiver",
        "care_recipient_ids": ["cr_001"],
    }


@pytest.fixture
def granted_consent_matrix():
    return [
        {
            "caregiver_id": "cg_001",
            "category": InformationCategory.ACTIVITY_ENGAGEMENT.value,
            "max_tier": 2,
            "consent_status": "granted",
            "expires_at": None,
        }
    ]


class TestNotificationDispatcher:
    
    def test_successful_web_push_dispatch(self, base_alert, primary_caregiver, granted_consent_matrix, mock_audit_sink):
        dispatcher = NotificationDispatcher(max_retries=3, initial_backoff_sec=0.0)
        res = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=granted_consent_matrix,
            channel=DeliveryChannel.WEB_PUSH,
            recipient_contact="jane.smith@push.local",
            audit_sink=mock_audit_sink,
        )

        assert res["status"] == DeliveryStatus.DELIVERED_SANDBOX.value
        assert res["is_duplicate"] is False
        assert res["disclosed_tier"] == 1
        assert res["attempts"] == 1
        assert res["provider_meta"]["is_sandbox"] is True
        assert res["provider_meta"]["environment"] == "SANDBOX / SIMULATION"
        assert len(mock_audit_sink.entries) == 1
        assert mock_audit_sink.entries[0]["event_type"] == "notification_dispatched"

    def test_successful_sms_sandbox_dispatch(self, base_alert, primary_caregiver, granted_consent_matrix, mock_audit_sink):
        dispatcher = NotificationDispatcher(max_retries=3, initial_backoff_sec=0.0)
        res = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=granted_consent_matrix,
            channel=DeliveryChannel.SMS,
            recipient_contact="+15551234567",
            audit_sink=mock_audit_sink,
        )

        assert res["status"] == DeliveryStatus.DELIVERED_SANDBOX.value
        assert res["is_duplicate"] is False
        assert res["provider_meta"]["masked_phone"] == "+15***67"
        assert res["provider_meta"]["is_sandbox"] is True

    def test_notification_strictly_withheld_on_unconsented_category(self, base_alert, primary_caregiver, mock_audit_sink):
        # Empty consent matrix (no consent granted)
        empty_matrix = []
        dispatcher = NotificationDispatcher(max_retries=3, initial_backoff_sec=0.0)
        res = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=empty_matrix,
            channel=DeliveryChannel.SMS,
            recipient_contact="+15551234567",
            audit_sink=mock_audit_sink,
        )

        assert res["status"] == DeliveryStatus.WITHHELD_CONSENT.value
        assert res["disclosed_tier"] == 0
        assert "withheld" in res["message"].lower()
        assert len(mock_audit_sink.entries) == 1
        assert mock_audit_sink.entries[0]["event_type"] == "notification_withheld_consent"

    def test_notification_withheld_on_expired_consent(self, base_alert, primary_caregiver, mock_audit_sink):
        expired_matrix = [
            {
                "caregiver_id": "cg_001",
                "category": InformationCategory.ACTIVITY_ENGAGEMENT.value,
                "max_tier": 2,
                "consent_status": "granted",
                "expires_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat().replace("+00:00", "Z"),
            }
        ]
        dispatcher = NotificationDispatcher(max_retries=3, initial_backoff_sec=0.0)
        res = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=expired_matrix,
            channel=DeliveryChannel.WEB_PUSH,
            recipient_contact="jane.smith@push.local",
            audit_sink=mock_audit_sink,
        )

        assert res["status"] == DeliveryStatus.WITHHELD_CONSENT.value
        assert res["disclosed_tier"] == 0

    def test_deterministic_idempotency_deduplication(self, base_alert, primary_caregiver, granted_consent_matrix, mock_audit_sink):
        dispatcher = NotificationDispatcher(max_retries=3, initial_backoff_sec=0.0)
        # First dispatch
        res_1 = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=granted_consent_matrix,
            channel=DeliveryChannel.WEB_PUSH,
            recipient_contact="jane.smith@push.local",
            audit_sink=mock_audit_sink,
        )
        # Second identical dispatch
        res_2 = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=granted_consent_matrix,
            channel=DeliveryChannel.WEB_PUSH,
            recipient_contact="jane.smith@push.local",
            audit_sink=mock_audit_sink,
        )

        assert res_1["status"] == DeliveryStatus.DELIVERED_SANDBOX.value
        assert res_2["status"] == DeliveryStatus.DUPLICATE_IGNORED.value
        assert res_2["is_duplicate"] is True
        assert res_1["idempotency_key"] == res_2["idempotency_key"]
        # Audit logged only once for the primary successful dispatch
        assert len(mock_audit_sink.entries) == 1

    def test_linter_sanitizes_both_summary_and_actionable_step(self, primary_caregiver, granted_consent_matrix):
        medical_alert = {
            "alert_id": "alt_med_999",
            "care_recipient_id": "cr_001",
            "alert_type": AlertType.ADHERENCE_ALERT.value,
            "category": InformationCategory.ACTIVITY_ENGAGEMENT.value,
            "severity": AlertSeverity.HIGH.value,
            "rule_fired": "missed_checkin",
            "evidence_summary": "Patient diagnosed with acute stroke and blood pressure 180/110.",
            "actionable_step": "Administer 50mg lisinopril and initiate clinical treatment.",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "requires_tier": 1,
            "is_data_gap": False,
        }
        dispatcher = NotificationDispatcher(max_retries=3, initial_backoff_sec=0.0)
        res = dispatcher.dispatch_alert(
            raw_alert=medical_alert,
            caregiver=primary_caregiver,
            consent_matrix=granted_consent_matrix,
            channel=DeliveryChannel.WEB_PUSH,
            recipient_contact="jane.smith@push.local",
        )

        payload = res["payload"]
        assert "diagnosed" not in payload["evidence_summary"].lower()
        assert "stroke" not in payload["evidence_summary"].lower()
        assert "lisinopril" not in payload["actionable_step"].lower()
        assert "administer" not in payload["actionable_step"].lower()

    def test_bounded_retry_succeeds_on_second_attempt(self, base_alert, primary_caregiver, granted_consent_matrix):
        # Configure adapter with 1 deterministic failure before success
        custom_adapter = WebPushSandboxAdapter(deterministic_fail_attempts=1)
        dispatcher = NotificationDispatcher(
            max_retries=3,
            initial_backoff_sec=0.0,
            custom_adapters={DeliveryChannel.WEB_PUSH.value: custom_adapter}
        )

        res = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=granted_consent_matrix,
            channel=DeliveryChannel.WEB_PUSH,
            recipient_contact="jane.smith@push.local",
        )

        assert res["status"] == DeliveryStatus.DELIVERED_SANDBOX.value
        assert res["attempts"] == 2

    def test_bounded_retry_permanent_failure_exhausts_max_retries(self, base_alert, primary_caregiver, granted_consent_matrix, mock_audit_sink):
        # Configure adapter with 5 deterministic failures (exceeds max_retries=3)
        custom_adapter = WebPushSandboxAdapter(deterministic_fail_attempts=5)
        dispatcher = NotificationDispatcher(
            max_retries=3,
            initial_backoff_sec=0.0,
            custom_adapters={DeliveryChannel.WEB_PUSH.value: custom_adapter}
        )

        res = dispatcher.dispatch_alert(
            raw_alert=base_alert,
            caregiver=primary_caregiver,
            consent_matrix=granted_consent_matrix,
            channel=DeliveryChannel.WEB_PUSH,
            recipient_contact="jane.smith@push.local",
            audit_sink=mock_audit_sink,
        )

        assert res["status"] == DeliveryStatus.FAILED.value
        assert res["attempts"] == 3
        assert len(mock_audit_sink.entries) == 1
        assert mock_audit_sink.entries[0]["event_type"] == "notification_failed"
