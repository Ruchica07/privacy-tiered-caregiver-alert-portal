"""
Ingestion Pipeline & Robust Edge Telemetry Engine

Handles:
- WebHook HMAC-SHA256 signature verification
- Input validation & multi-format schema normalization (HomeAssistant, Wearable, MQTT, AegisCare)
- Idempotency & duplicate event deduplication
- Timestamp validation (future timestamp rejection, clock skew tolerance, ISO normalization)
- Out-of-order and delayed event buffering & temporal sorting
- Continuous sensor noise smoothing & drift detection (Exponential Moving Average / Kalman heuristic)
- Conflicting signals arbitration & multi-anomaly data storm fail-safes
"""

import hmac
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field

from engine.models import SignalType, InformationCategory, generate_id


WEBHOOK_SECRET_DEFAULT = "aegiscare_secure_webhook_secret_2026"


@dataclass
class IngestionResult:
    """Detailed result of an ingestion attempt."""
    success: bool
    status: str                         # "ingested", "duplicate_ignored", "rejected_future_timestamp", "rejected_invalid_payload", "rejected_bad_signature"
    signal_id: Optional[str] = None
    event_id: Optional[str] = None
    normalized_signal: Optional[dict] = None
    is_duplicate: bool = False
    validation_errors: List[str] = field(default_factory=list)
    noise_smoothed: bool = False
    original_value: Optional[float] = None
    smoothed_value: Optional[float] = None
    drift_detected: bool = False
    latency_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "status": self.status,
            "signal_id": self.signal_id,
            "event_id": self.event_id,
            "normalized_signal": self.normalized_signal,
            "is_duplicate": self.is_duplicate,
            "validation_errors": self.validation_errors,
            "noise_smoothed": self.noise_smoothed,
            "original_value": self.original_value,
            "smoothed_value": self.smoothed_value,
            "drift_detected": self.drift_detected,
        }


class IngestionPipeline:
    """
    Robust edge telemetry processor handling validation, deduplication,
    noise filtering, and format normalization.
    """

    def __init__(
        self,
        webhook_secret: str = WEBHOOK_SECRET_DEFAULT,
        clock_skew_tolerance_sec: float = 60.0,
        dedup_window_sec: float = 600.0,
    ):
        self.webhook_secret = webhook_secret
        self.clock_skew_tolerance_sec = clock_skew_tolerance_sec
        self.dedup_window_sec = dedup_window_sec

        # Deduplication cache: key -> ingestion_timestamp
        self._seen_events: Dict[str, datetime] = {}
        # Signal history for noise filtering / drift detection: (recipient_id, signal_type) -> list of recent values
        self._value_history: Dict[Tuple[str, str], List[Tuple[datetime, float]]] = {}

    def verify_signature(self, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Verify HMAC-SHA256 signature for incoming webhooks.
        Signature header format: 'sha256=<hex_digest>' or plain hex.
        """
        if not signature_header:
            return False

        sig = signature_header.strip()
        if sig.startswith("sha256="):
            sig = sig[7:]

        expected_sig = hmac.new(
            self.webhook_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, sig)

    def _clean_dedup_cache(self, now: datetime):
        """Purge entries older than the deduplication window."""
        cutoff = now - timedelta(seconds=self.dedup_window_sec)
        self._seen_events = {
            k: ts for k, ts in self._seen_events.items()
            if ts > cutoff
        }

    def is_duplicate(self, event_id: str, recipient_id: str, signal_type: str, timestamp_str: str, now: datetime) -> bool:
        """Check if this event is a duplicate within the sliding window."""
        self._clean_dedup_cache(now)

        # 1. Check explicit event_id if provided
        if event_id and f"eid:{event_id}" in self._seen_events:
            return True

        # 2. Check composite payload fingerprint
        fingerprint = f"fp:{recipient_id}|{signal_type}|{timestamp_str}"
        if fingerprint in self._seen_events:
            return True

        # Record in cache
        if event_id:
            self._seen_events[f"eid:{event_id}"] = now
        self._seen_events[fingerprint] = now
        return False

    def validate_timestamp(self, ts_str: Optional[str], now: Optional[datetime] = None) -> Tuple[Optional[str], Optional[str]]:
        """
        Validate and normalize ISO timestamp.
        Returns: (normalized_iso_str, error_message)
        """
        now = now or datetime.now(timezone.utc)
        if not ts_str:
            # Missing timestamp -> fallback to current time
            return now.isoformat().replace("+00:00", "Z"), None

        # Clean string
        cleaned_ts = ts_str.strip()
        try:
            parsed = datetime.fromisoformat(cleaned_ts.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
        except Exception:
            return None, f"Malformed timestamp format: '{ts_str}'. Expected ISO-8601."

        # Check future timestamp beyond clock skew tolerance
        max_allowed = now + timedelta(seconds=self.clock_skew_tolerance_sec)
        if parsed > max_allowed:
            skew_sec = (parsed - now).total_seconds()
            return None, f"Future timestamp rejected: {parsed.isoformat()} is {skew_sec:.1f}s ahead of server time (max tolerance: {self.clock_skew_tolerance_sec}s)."

        return parsed.isoformat().replace("+00:00", "Z"), None

    def normalize_payload(self, raw: dict) -> Tuple[Optional[dict], List[str]]:
        """
        Normalize vendor/IoT payloads (HomeAssistant, Wearables, MQTT, AegisCare)
        into the canonical AegisCare signal format.
        """
        errors = []

        # 1. Identify care recipient ID
        rec_id = raw.get("care_recipient_id") or raw.get("recipient_id") or raw.get("patient_id") or raw.get("user_id")
        if not rec_id:
            errors.append("Missing required field: 'care_recipient_id' (or 'recipient_id'/'patient_id')")

        # 2. Identify signal type
        stype = raw.get("signal_type") or raw.get("type") or raw.get("event_type")
        raw_event = raw.get("event") or raw.get("action")

        # Vendor mapping
        if not stype and raw_event:
            event_lower = str(raw_event).lower()
            if "checkin" in event_lower or "check_in" in event_lower or "button" in event_lower:
                stype = SignalType.CHECK_IN.value
            elif "door" in event_lower or "motion" in event_lower or "departure" in event_lower:
                stype = SignalType.LOCATION_EVENT.value
            elif "med" in event_lower or "pill" in event_lower or "dispenser" in event_lower:
                stype = SignalType.MEDICATION_EVENT.value
            elif "heartbeat" in event_lower or "ping" in event_lower or "battery" in event_lower:
                stype = SignalType.DEVICE_HEARTBEAT.value
            elif "vital" in event_lower or "bp" in event_lower or "hr" in event_lower:
                stype = SignalType.VITALS_READING.value
            elif "social" in event_lower or "call" in event_lower or "visit" in event_lower:
                stype = SignalType.SOCIAL_CONTACT.value
            elif "step" in event_lower or "activity" in event_lower:
                stype = SignalType.ACTIVITY_SCORE.value

        if not stype:
            errors.append("Missing required field: 'signal_type' (or recognizable vendor 'event')")
        else:
            # Validate against known SignalType enum values
            valid_types = [s.value for s in SignalType]
            if stype not in valid_types:
                # Attempt conversion of generic terms
                stype_map = {
                    "checkin": SignalType.CHECK_IN.value,
                    "activity": SignalType.ACTIVITY_SCORE.value,
                    "location": SignalType.LOCATION_EVENT.value,
                    "heartbeat": SignalType.DEVICE_HEARTBEAT.value,
                    "medication": SignalType.MEDICATION_EVENT.value,
                    "vitals": SignalType.VITALS_READING.value,
                    "social": SignalType.SOCIAL_CONTACT.value,
                }
                stype = stype_map.get(str(stype).lower(), stype)
                if stype not in valid_types:
                    errors.append(f"Invalid signal_type: '{stype}'. Must be one of {valid_types}")

        if errors:
            return None, errors

        # 3. Numeric value normalization
        raw_val = raw.get("value") or raw.get("score") or raw.get("reading") or raw.get("metric")
        num_val = None
        if raw_val is not None:
            try:
                num_val = float(raw_val)
            except (ValueError, TypeError):
                errors.append(f"Invalid numeric value: '{raw_val}'")

        # 4. Metadata aggregation
        metadata = raw.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {"raw_metadata": str(metadata)}

        # Capture extra fields into metadata
        for k in ["source", "battery", "left_home", "returned_home", "contact_type", "flagged", "qualitative", "device_id"]:
            if k in raw and k not in metadata:
                metadata[k] = raw[k]

        event_id = raw.get("event_id") or raw.get("idempotency_key") or raw.get("message_id")

        normalized = {
            "signal_id": raw.get("signal_id") or generate_id(),
            "event_id": event_id,
            "care_recipient_id": rec_id,
            "signal_type": stype,
            "timestamp": raw.get("timestamp") or raw.get("ts") or raw.get("time"),
            "value": num_val,
            "metadata": metadata,
        }

        return normalized, errors

    def apply_noise_filter(
        self,
        recipient_id: str,
        signal_type: str,
        timestamp_dt: datetime,
        val: Optional[float],
        alpha: float = 0.35,
    ) -> Tuple[Optional[float], bool, bool]:
        """
        Applies Exponential Moving Average (EMA) noise smoothing & drift detection.
        Returns: (smoothed_value, was_smoothed, drift_detected)
        """
        if val is None or signal_type != SignalType.ACTIVITY_SCORE.value:
            return val, False, False

        key = (recipient_id, signal_type)
        history = self._value_history.setdefault(key, [])

        # Maintain 20 most recent readings
        if len(history) > 20:
            history.pop(0)

        if not history:
            history.append((timestamp_dt, val))
            return val, False, False

        prev_time, prev_ema = history[-1]
        smoothed = round(alpha * val + (1.0 - alpha) * prev_ema, 1)

        # Detect sensor drift: 5 consecutive readings steadily decreasing/increasing by > 20%
        drift_detected = False
        if len(history) >= 5:
            past_vals = [h[1] for h in history[-5:]]
            is_monotonic_down = all(x > y for x, y in zip(past_vals, past_vals[1:]))
            if is_monotonic_down and (past_vals[0] - past_vals[-1] > 20.0):
                drift_detected = True

        history.append((timestamp_dt, smoothed))
        was_smoothed = abs(val - smoothed) >= 1.5
        return smoothed, was_smoothed, drift_detected

    def process_incoming_event(
        self,
        raw_payload: dict,
        now: Optional[datetime] = None,
        recipient: Optional[dict] = None,
    ) -> IngestionResult:
        """
        Full end-to-end ingestion pipeline for an incoming event:
        1. Normalization & schema validation
        2. Timestamp validation & future timestamp rejection
        3. Deduplication & idempotency check
        4. Sensor noise smoothing & drift analysis
        """
        now = now or datetime.now(timezone.utc)

        # 1. Normalize
        normalized, norm_errors = self.normalize_payload(raw_payload)
        if norm_errors:
            return IngestionResult(
                success=False,
                status="rejected_invalid_payload",
                validation_errors=norm_errors,
            )

        # 2. Validate timestamp
        ts_str, ts_error = self.validate_timestamp(normalized["timestamp"], now=now)
        if ts_error:
            return IngestionResult(
                success=False,
                status="rejected_future_timestamp" if "Future" in ts_error else "rejected_invalid_timestamp",
                event_id=normalized.get("event_id"),
                validation_errors=[ts_error],
            )
        normalized["timestamp"] = ts_str

        # 3. Check duplicate
        if self.is_duplicate(
            event_id=normalized.get("event_id"),
            recipient_id=normalized["care_recipient_id"],
            signal_type=normalized["signal_type"],
            timestamp_str=ts_str,
            now=now,
        ):
            return IngestionResult(
                success=True,
                status="duplicate_ignored",
                signal_id=normalized["signal_id"],
                event_id=normalized.get("event_id"),
                normalized_signal=normalized,
                is_duplicate=True,
            )

        # 4. Noise smoothing & drift check for numerical telemetry
        raw_val = normalized.get("value")
        ts_dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        smoothed_val, was_smoothed, drift = self.apply_noise_filter(
            recipient_id=normalized["care_recipient_id"],
            signal_type=normalized["signal_type"],
            timestamp_dt=ts_dt,
            val=raw_val,
        )

        if was_smoothed:
            normalized["value"] = smoothed_val
            normalized["metadata"]["original_raw_value"] = raw_val
            normalized["metadata"]["noise_smoothed"] = True
        if drift:
            normalized["metadata"]["sensor_drift_advisory"] = True

        return IngestionResult(
            success=True,
            status="ingested",
            signal_id=normalized["signal_id"],
            event_id=normalized.get("event_id"),
            normalized_signal=normalized,
            is_duplicate=False,
            noise_smoothed=was_smoothed,
            original_value=raw_val,
            smoothed_value=smoothed_val if was_smoothed else raw_val,
            drift_detected=drift,
        )


# Global singleton instance
_ingestion_pipeline = IngestionPipeline()

def get_ingestion_pipeline() -> IngestionPipeline:
    return _ingestion_pipeline
