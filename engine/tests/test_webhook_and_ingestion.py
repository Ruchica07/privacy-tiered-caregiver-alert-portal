"""
Test Suite: WebHook Ingestion, HMAC Verification, Deduplication, and Edge Telemetry

Verifies:
1. HMAC-SHA256 signature verification & rejection of bad signatures
2. Payload schema normalization (vendor formats -> AegisCare signals)
3. Rejection of future timestamps exceeding 60.0s clock skew
4. Idempotent deduplication cache (sliding window)
5. Exponential Moving Average (EMA) sensor noise smoothing
6. Sensor baseline drift advisory detection
"""

import pytest
import hmac
import hashlib
import json
from datetime import datetime, timedelta, timezone

from engine.ingestion import IngestionPipeline, WEBHOOK_SECRET_DEFAULT


class TestWebhookAndIngestionPipeline:

    @pytest.fixture
    def pipeline(self):
        return IngestionPipeline(webhook_secret=WEBHOOK_SECRET_DEFAULT, clock_skew_tolerance_sec=60.0)

    def test_hmac_signature_verification_success(self, pipeline):
        payload = json.dumps({"care_recipient_id": "cr_001", "signal_type": "check_in"}).encode("utf-8")
        expected_sig = hmac.new(WEBHOOK_SECRET_DEFAULT.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        assert pipeline.verify_signature(payload, f"sha256={expected_sig}") is True
        assert pipeline.verify_signature(payload, expected_sig) is True

    def test_hmac_signature_verification_failure_tampered_payload(self, pipeline):
        payload = json.dumps({"care_recipient_id": "cr_001", "signal_type": "check_in"}).encode("utf-8")
        tampered_payload = json.dumps({"care_recipient_id": "cr_002", "signal_type": "check_in"}).encode("utf-8")
        expected_sig = hmac.new(WEBHOOK_SECRET_DEFAULT.encode("utf-8"), payload, hashlib.sha256).hexdigest()

        assert pipeline.verify_signature(tampered_payload, expected_sig) is False

    def test_hmac_signature_verification_failure_wrong_secret(self):
        pipeline_wrong = IngestionPipeline(webhook_secret="wrong_secret_123")
        payload = json.dumps({"test": "data"}).encode("utf-8")
        sig = hmac.new(b"correct_secret_456", payload, hashlib.sha256).hexdigest()

        assert pipeline_wrong.verify_signature(payload, sig) is False

    def test_missing_required_fields_rejected(self, pipeline):
        raw = {"value": 45.0}  # Missing care_recipient_id and signal_type
        res = pipeline.process_incoming_event(raw)

        assert res.success is False
        assert res.status == "rejected_invalid_payload"
        assert len(res.validation_errors) >= 2

    def test_future_timestamp_rejected_beyond_clock_skew(self, pipeline):
        now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 10 minutes in the future (> 60s skew tolerance)
        future_ts = (now + timedelta(minutes=10)).isoformat().replace("+00:00", "Z")

        raw = {
            "care_recipient_id": "cr_001",
            "signal_type": "check_in",
            "timestamp": future_ts,
        }
        res = pipeline.process_incoming_event(raw, now=now)

        assert res.success is False
        assert res.status == "rejected_future_timestamp"
        assert "Future timestamp rejected" in res.validation_errors[0]

    def test_timestamp_within_clock_skew_accepted(self, pipeline):
        now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        # 30 seconds in the future (<= 60s skew tolerance)
        skew_ts = (now + timedelta(seconds=30)).isoformat().replace("+00:00", "Z")

        raw = {
            "care_recipient_id": "cr_001",
            "signal_type": "check_in",
            "timestamp": skew_ts,
        }
        res = pipeline.process_incoming_event(raw, now=now)

        assert res.success is True
        assert res.status == "ingested"

    def test_duplicate_event_id_deduplication(self, pipeline):
        now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        raw = {
            "event_id": "evt_unique_1001",
            "care_recipient_id": "cr_001",
            "signal_type": "check_in",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
        }

        # 1st ingestion: success
        res1 = pipeline.process_incoming_event(raw, now=now)
        assert res1.success is True
        assert res1.is_duplicate is False

        # 2nd ingestion (same event_id): duplicate ignored
        res2 = pipeline.process_incoming_event(raw, now=now + timedelta(seconds=5))
        assert res2.success is True
        assert res2.is_duplicate is True
        assert res2.status == "duplicate_ignored"

    def test_vendor_schema_normalization_homeassistant(self, pipeline):
        now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        ha_payload = {
            "patient_id": "cr_002",
            "event": "front_door_opened",
            "time": now.isoformat().replace("+00:00", "Z"),
            "left_home": True,
            "returned_home": False,
        }
        res = pipeline.process_incoming_event(ha_payload, now=now)

        assert res.success is True
        assert res.normalized_signal["care_recipient_id"] == "cr_002"
        assert res.normalized_signal["signal_type"] == "location_event"
        assert res.normalized_signal["metadata"]["left_home"] is True

    def test_sensor_noise_smoothing_on_accelerometer_spike(self, pipeline):
        now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Sequence of normal baseline readings (~50.0)
        for i in range(5):
            t = now - timedelta(hours=5 - i)
            pipeline.process_incoming_event({
                "care_recipient_id": "cr_001",
                "signal_type": "activity_score",
                "timestamp": t.isoformat().replace("+00:00", "Z"),
                "value": 50.0,
            }, now=t)

        # Isolated extreme glitch reading (0.1)
        glitch_payload = {
            "care_recipient_id": "cr_001",
            "signal_type": "activity_score",
            "timestamp": now.isoformat().replace("+00:00", "Z"),
            "value": 0.1,
        }
        res = pipeline.process_incoming_event(glitch_payload, now=now)

        assert res.success is True
        assert res.noise_smoothed is True
        # Smoothed value should be pulled towards baseline, not dropping straight to 0.1
        assert res.normalized_signal["value"] > 20.0
        assert res.normalized_signal["metadata"]["original_raw_value"] == 0.1

    def test_sensor_drift_detection(self, pipeline):
        now = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        # Steadily dropping sequence
        drift_values = [60.0, 50.0, 40.0, 30.0, 20.0, 10.0]
        last_res = None
        for i, val in enumerate(drift_values):
            t = now + timedelta(hours=i)
            last_res = pipeline.process_incoming_event({
                "care_recipient_id": "cr_drift_test",
                "signal_type": "activity_score",
                "timestamp": t.isoformat().replace("+00:00", "Z"),
                "value": val,
            }, now=t)

        assert last_res.drift_detected is True
        assert last_res.normalized_signal["metadata"].get("sensor_drift_advisory") is True
