"""
Notification Dispatcher Module — Privacy-Tiered Alert Dispatcher & Sandbox Adapters (Phase 3)

Architecture:
Alert Generated
  ↓
Privacy / Consent Filter (Tier 0 to Tier 3)
  ↓
Content Safety Linter (Non-medical boundary enforcement on summary AND actionable step)
  ↓
Notification Dispatcher (Idempotency, channel routing, bounded retry policy)
  ↓
Channel Adapters (Web Push Sandbox, SMS Sandbox)
  ↓
Tamper-Evident Audit Logging

Security & Privacy Guarantees:
1. Strict Consent Gating: Never dispatches alerts for unconsented or expired categories (withheld).
2. Tier Redaction: Dispatches strictly the sanitized content matching the recipient caregiver's permitted tier.
3. Non-Medical Boundary: BOTH `evidence_summary` AND `actionable_step` are strictly passed through
   the content safety linter to strip any prohibited clinical/prescriptive phrases before external dispatch.
4. Deterministic Idempotency: Dispatches with identical (alert_id, caregiver_id, channel) are deduplicated.
   Note: The default `_dispatch_history` registry is an in-memory process cache designed for prototyping
   and demonstration; production deployment requires persistent transactional store backing (e.g. Redis/PostgreSQL).
5. Bounded Retries & Exponential Backoff: Transient delivery failures are retried deterministically up to max_retries.
6. Honest Sandbox Labeling: All simulated deliveries are explicitly tagged with `is_sandbox: True` and
   environment: `SANDBOX / SIMULATION`. Real external provider credentials are not simulated as live deliveries.
"""

import time
import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, List, Optional, Tuple

from engine.models import generate_id
from engine.consent_filter import filter_alert_for_caregiver
from engine.content_linter import sanitize_alert_text


class DeliveryChannel(str, Enum):
    WEB_PUSH = "web_push"
    SMS = "sms"


class DeliveryStatus(str, Enum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED_SANDBOX = "delivered_sandbox"
    FAILED = "failed"
    WITHHELD_CONSENT = "withheld_consent"
    DUPLICATE_IGNORED = "duplicate_ignored"


class BaseChannelAdapter:
    """Base interface for notification channel adapters with deterministic failure testing support."""
    
    def __init__(self, channel_name: str, deterministic_fail_attempts: int = 0):
        self.channel_name = channel_name
        self.is_sandbox = True
        self.deterministic_fail_attempts = deterministic_fail_attempts
        self.current_attempt_count = 0

    def send(self, recipient_address: str, payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        """
        Send a notification to a recipient address.
        Returns: (success: bool, status_message: str, provider_metadata: dict)
        """
        raise NotImplementedError


class WebPushSandboxAdapter(BaseChannelAdapter):
    """
    Simulated Web Push Notification Adapter.
    Clearly labeled as SANDBOX / SIMULATION — does not connect to external push services.
    Supports deterministic failure counts for unit test verification.
    """
    
    def __init__(self, deterministic_fail_attempts: int = 0):
        super().__init__(DeliveryChannel.WEB_PUSH.value, deterministic_fail_attempts=deterministic_fail_attempts)

    def send(self, recipient_address: str, payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        self.current_attempt_count += 1
        
        # Deterministic simulation trigger: fail first N attempts if configured or if recipient specifies failure
        if self.current_attempt_count <= self.deterministic_fail_attempts or recipient_address == "sim_fail@push.local":
            return False, f"Simulated Web Push network failure (attempt {self.current_attempt_count}).", {
                "adapter": "WebPushSandboxAdapter",
                "environment": "SANDBOX / SIMULATION",
                "attempt": self.current_attempt_count,
                "is_sandbox": True
            }

        return True, "Delivered via Web Push Sandbox simulator.", {
            "adapter": "WebPushSandboxAdapter",
            "environment": "SANDBOX / SIMULATION",
            "simulated_push_endpoint": f"https://sandbox.push.local/v1/notify/{recipient_address}",
            "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "attempt": self.current_attempt_count,
            "is_sandbox": True
        }


class SMSSandboxAdapter(BaseChannelAdapter):
    """
    Simulated SMS Notification Adapter.
    Clearly labeled as SANDBOX / SIMULATION — does not connect to external SMS gateways.
    Supports deterministic failure counts for unit test verification.
    """
    
    def __init__(self, deterministic_fail_attempts: int = 0):
        super().__init__(DeliveryChannel.SMS.value, deterministic_fail_attempts=deterministic_fail_attempts)

    def send(self, recipient_address: str, payload: Dict[str, Any]) -> Tuple[bool, str, Dict[str, Any]]:
        self.current_attempt_count += 1

        # Deterministic simulation trigger
        if self.current_attempt_count <= self.deterministic_fail_attempts or recipient_address == "+10000000000_fail":
            return False, f"Simulated SMS carrier delivery failure (attempt {self.current_attempt_count}).", {
                "adapter": "SMSSandboxAdapter",
                "environment": "SANDBOX / SIMULATION",
                "attempt": self.current_attempt_count,
                "is_sandbox": True
            }

        if not recipient_address or len(recipient_address.strip()) < 5:
            return False, "Invalid recipient phone number format.", {
                "adapter": "SMSSandboxAdapter",
                "environment": "SANDBOX / SIMULATION",
                "is_sandbox": True
            }

        return True, "Delivered via SMS Sandbox simulator.", {
            "adapter": "SMSSandboxAdapter",
            "environment": "SANDBOX / SIMULATION",
            "masked_phone": recipient_address[:3] + "***" + recipient_address[-2:] if len(recipient_address) >= 5 else recipient_address,
            "delivered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "attempt": self.current_attempt_count,
            "is_sandbox": True
        }


class NotificationDispatcher:
    """
    Central dispatcher coordinating privacy filtering, tier-based redaction,
    linter enforcement on evidence & actions, idempotency, bounded retry logic,
    and tamper-evident audit logging.
    """

    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_sec: float = 0.0,
        custom_adapters: Optional[Dict[str, BaseChannelAdapter]] = None,
    ):
        self.max_retries = max_retries
        self.initial_backoff_sec = initial_backoff_sec
        self.adapters: Dict[str, BaseChannelAdapter] = custom_adapters or {
            DeliveryChannel.WEB_PUSH.value: WebPushSandboxAdapter(),
            DeliveryChannel.SMS.value: SMSSandboxAdapter(),
        }
        # In-memory idempotency tracking: idempotency_key -> dispatch record
        # Note: In-memory for prototype demonstration; does not survive process restarts.
        self._dispatch_history: Dict[str, Dict[str, Any]] = {}

    def compute_idempotency_key(self, alert_id: str, caregiver_id: str, channel: str) -> str:
        """Generate deterministic idempotency key from alert, caregiver, and channel identifiers."""
        raw = f"{alert_id}:{caregiver_id}:{channel}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def dispatch_alert(
        self,
        raw_alert: Dict[str, Any],
        caregiver: Dict[str, Any],
        consent_matrix: List[Dict[str, Any]],
        channel: DeliveryChannel,
        recipient_contact: str,
        audit_sink: Optional[Any] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """
        Dispatches a privacy-filtered alert notification to a caregiver.
        
        Steps:
        1. Evaluate privacy consent matrix and caregiver role.
        2. If withheld, record audit and return WITHHELD_CONSENT status.
        3. Extract tier-redacted evidence summary and actionable step.
        4. Pass BOTH summary AND actionable step through content safety linter.
        5. Verify idempotency cache.
        6. Execute delivery with bounded exponential backoff retries.
        7. Record tamper-evident audit entry.
        """
        now = now or datetime.now(timezone.utc)
        caregiver_id = caregiver.get("id", "")
        alert_id = raw_alert.get("alert_id", "")
        channel_str = channel.value if isinstance(channel, DeliveryChannel) else str(channel)

        idempotency_key = self.compute_idempotency_key(alert_id, caregiver_id, channel_str)

        # 1. Check In-Memory Idempotency Cache
        if idempotency_key in self._dispatch_history:
            prev_record = self._dispatch_history[idempotency_key]
            return {
                "dispatch_id": prev_record["dispatch_id"],
                "idempotency_key": idempotency_key,
                "status": DeliveryStatus.DUPLICATE_IGNORED.value,
                "is_duplicate": True,
                "message": "Duplicate notification request ignored by idempotency key.",
                "original_dispatched_at": prev_record["dispatched_at"],
                "channel": channel_str,
            }

        # 2. Server-side Consent & Privacy Tier Filter
        filtered_alert, audit_info = filter_alert_for_caregiver(
            raw_alert, caregiver_id, consent_matrix, now=now
        )

        effective_tier = filtered_alert.get("rendered_tier", 0) if filtered_alert else 0

        if not filtered_alert or effective_tier == 0:
            # Notification is strictly withheld due to resident consent settings
            dispatch_id = generate_id()
            record = {
                "dispatch_id": dispatch_id,
                "idempotency_key": idempotency_key,
                "alert_id": alert_id,
                "caregiver_id": caregiver_id,
                "care_recipient_id": raw_alert.get("care_recipient_id"),
                "channel": channel_str,
                "status": DeliveryStatus.WITHHELD_CONSENT.value,
                "dispatched_at": now.isoformat().replace("+00:00", "Z"),
                "disclosed_tier": 0,
                "payload": None,
                "attempts": 0,
                "audit_info": audit_info,
            }
            self._dispatch_history[idempotency_key] = record

            if audit_sink and hasattr(audit_sink, "add_audit_entry"):
                audit_sink.add_audit_entry({
                    "audit_id": generate_id(),
                    "timestamp": now.isoformat().replace("+00:00", "Z"),
                    "event_type": "notification_withheld_consent",
                    "actor_id": "notification_dispatcher",
                    "care_recipient_id": raw_alert.get("care_recipient_id", "unknown"),
                    "details": {
                        "dispatch_id": dispatch_id,
                        "alert_id": alert_id,
                        "caregiver_id": caregiver_id,
                        "channel": channel_str,
                        "reason": audit_info.get("withhold_reason", audit_info.get("reason", "Unconsented, zero-tier, or expired category")),
                    },
                })

            return {
                "dispatch_id": dispatch_id,
                "idempotency_key": idempotency_key,
                "status": DeliveryStatus.WITHHELD_CONSENT.value,
                "is_duplicate": False,
                "message": "Notification withheld: resident consent does not permit disclosure to this caregiver.",
                "disclosed_tier": 0,
            }

        # 3. Content Safety Linter Pass: Sanitize BOTH evidence_summary AND actionable_step
        raw_summary = filtered_alert.get("evidence_summary", "")
        sanitized_summary, _ = sanitize_alert_text(raw_summary, filtered_alert.get("alert_type", "generic"))

        raw_action = filtered_alert.get("actionable_step") or ""
        sanitized_action, _ = sanitize_alert_text(raw_action, filtered_alert.get("alert_type", "generic")) if raw_action else (None, [])

        notification_payload = {
            "alert_id": alert_id,
            "care_recipient_id": filtered_alert.get("care_recipient_id"),
            "severity": filtered_alert.get("severity"),
            "category": filtered_alert.get("category"),
            "disclosed_tier": effective_tier,
            "tier_label": filtered_alert.get("tier_label", "Standard Alert"),
            "evidence_summary": sanitized_summary,
            "actionable_step": sanitized_action,
            "is_data_gap": filtered_alert.get("is_data_gap", False),
            "generated_at": filtered_alert.get("generated_at"),
        }

        # 4. Route to Adapter with Bounded Retries & Exponential Backoff
        adapter = self.adapters.get(channel_str)
        if not adapter:
            return {
                "dispatch_id": generate_id(),
                "idempotency_key": idempotency_key,
                "status": DeliveryStatus.FAILED.value,
                "is_duplicate": False,
                "message": f"Unsupported delivery channel: {channel_str}",
            }

        dispatch_id = generate_id()
        attempt = 0
        success = False
        last_msg = ""
        provider_meta = {}

        while attempt < self.max_retries and not success:
            attempt += 1
            success, last_msg, provider_meta = adapter.send(recipient_contact, notification_payload)
            if not success and attempt < self.max_retries:
                # Bounded exponential backoff delay (non-blocking if initial_backoff_sec is 0.0)
                if self.initial_backoff_sec > 0:
                    time.sleep(self.initial_backoff_sec * (2 ** (attempt - 1)))

        final_status = DeliveryStatus.DELIVERED_SANDBOX.value if success else DeliveryStatus.FAILED.value

        dispatch_record = {
            "dispatch_id": dispatch_id,
            "idempotency_key": idempotency_key,
            "alert_id": alert_id,
            "caregiver_id": caregiver_id,
            "care_recipient_id": filtered_alert.get("care_recipient_id"),
            "channel": channel_str,
            "recipient_contact": recipient_contact,
            "status": final_status,
            "dispatched_at": now.isoformat().replace("+00:00", "Z"),
            "disclosed_tier": filtered_alert.get("disclosed_tier", 1),
            "attempts": attempt,
            "provider_meta": provider_meta,
            "payload": notification_payload,
        }
        self._dispatch_history[idempotency_key] = dispatch_record

        # 5. Tamper-Evident Audit Entry
        if audit_sink and hasattr(audit_sink, "add_audit_entry"):
            audit_sink.add_audit_entry({
                "audit_id": generate_id(),
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "event_type": "notification_dispatched" if success else "notification_failed",
                "actor_id": "notification_dispatcher",
                "care_recipient_id": filtered_alert.get("care_recipient_id", "unknown"),
                "details": {
                    "dispatch_id": dispatch_id,
                    "alert_id": alert_id,
                    "caregiver_id": caregiver_id,
                    "channel": channel_str,
                    "disclosed_tier": filtered_alert.get("disclosed_tier", 1),
                    "status": final_status,
                    "attempts": attempt,
                    "is_sandbox": provider_meta.get("is_sandbox", True),
                },
            })

        return {
            "dispatch_id": dispatch_id,
            "idempotency_key": idempotency_key,
            "status": final_status,
            "is_duplicate": False,
            "message": last_msg,
            "disclosed_tier": filtered_alert.get("disclosed_tier", 1),
            "attempts": attempt,
            "channel": channel_str,
            "provider_meta": provider_meta,
            "payload": notification_payload,
        }

    def get_dispatch_history(self, care_recipient_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve all recorded notification dispatches, optionally filtered by care recipient."""
        records = list(self._dispatch_history.values())
        if care_recipient_id:
            records = [r for r in records if r.get("care_recipient_id") == care_recipient_id]
        return sorted(records, key=lambda r: r.get("dispatched_at", ""), reverse=True)


# Singleton instance
_dispatcher_instance: Optional[NotificationDispatcher] = None

def get_notification_dispatcher() -> NotificationDispatcher:
    global _dispatcher_instance
    if _dispatcher_instance is None:
        _dispatcher_instance = NotificationDispatcher()
    return _dispatcher_instance
