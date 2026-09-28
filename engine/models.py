"""
Shared data models for the Privacy-Tiered Caregiver Alert Portal.

All enums, dataclasses, and type definitions used across the rules engine,
consent filter, content linter, API, and synthetic data generator.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional
import uuid


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class CaregiverRole(str, Enum):
    """Caregiver roles with associated default disclosure tiers."""
    PRIMARY_CAREGIVER = "primary_caregiver"
    SECONDARY_CAREGIVER = "secondary_caregiver"
    NEIGHBOR_COMMUNITY = "neighbor_community"
    CARE_COORDINATOR_PROFESSIONAL = "care_coordinator_professional"


# Default tier per role (can be overridden per caregiver × category)
DEFAULT_TIERS = {
    CaregiverRole.PRIMARY_CAREGIVER: 2,
    CaregiverRole.SECONDARY_CAREGIVER: 1,
    CaregiverRole.NEIGHBOR_COMMUNITY: 0,
    CaregiverRole.CARE_COORDINATOR_PROFESSIONAL: 3,
}


class InformationCategory(str, Enum):
    """Categories of information that can be tiered."""
    ACTIVITY_ENGAGEMENT = "activity_engagement"
    MEDICATION_ADHERENCE = "medication_adherence"
    VITALS_SUMMARY = "vitals_summary"
    LOCATION_SAFETY = "location_safety"
    SOCIAL_ISOLATION_SIGNAL = "social_isolation_signal"
    DIAGNOSIS_CONDITIONS = "diagnosis_conditions"


class ConsentStatus(str, Enum):
    """Status of a consent grant."""
    GRANTED = "granted"
    REVOKED = "revoked"
    PENDING = "pending"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertType(str, Enum):
    """Types of alerts the rules engine can generate."""
    ADHERENCE_ALERT = "adherence_alert"
    PATTERN_ALERT = "pattern_alert"
    SAFETY_ALERT = "safety_alert"
    ISOLATION_ALERT = "isolation_alert"
    DATA_GAP = "data_gap"


class FreshnessState(str, Enum):
    """Data freshness states for UI display."""
    FRESH = "fresh"
    STALE = "stale"
    MISSING = "missing"
    CONSENT_RESTRICTED = "consent_restricted"


class SignalType(str, Enum):
    """Types of synthetic signals from devices/check-ins."""
    CHECK_IN = "check_in"
    ACTIVITY_SCORE = "activity_score"
    VITALS_READING = "vitals_reading"
    LOCATION_EVENT = "location_event"
    SOCIAL_CONTACT = "social_contact"
    DEVICE_HEARTBEAT = "device_heartbeat"
    MEDICATION_EVENT = "medication_event"


# ---------------------------------------------------------------------------
# Data Classes
# ---------------------------------------------------------------------------

@dataclass
class CareRecipient:
    """An older adult being monitored."""
    id: str
    name: str
    baseline_activity_mean: float = 50.0
    baseline_activity_stddev: float = 10.0
    expected_checkin_window_hours: float = 4.0
    expected_medication_window_hours: float = 12.0
    night_hours_start: int = 22  # 10 PM
    night_hours_end: int = 6    # 6 AM
    social_contact_expected_days: int = 3
    device_heartbeat_expected_hours: float = 2.0

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "baseline_activity_mean": self.baseline_activity_mean,
            "baseline_activity_stddev": self.baseline_activity_stddev,
            "expected_checkin_window_hours": self.expected_checkin_window_hours,
            "expected_medication_window_hours": self.expected_medication_window_hours,
            "night_hours_start": self.night_hours_start,
            "night_hours_end": self.night_hours_end,
            "social_contact_expected_days": self.social_contact_expected_days,
            "device_heartbeat_expected_hours": self.device_heartbeat_expected_hours,
        }


@dataclass
class Caregiver:
    """A caregiver linked to one or more care recipients."""
    id: str
    name: str
    role: CaregiverRole
    care_recipient_ids: list = field(default_factory=list)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role.value,
            "care_recipient_ids": self.care_recipient_ids,
        }


@dataclass
class ConsentRecord:
    """A single consent entry: caregiver × category × tier."""
    consent_id: str
    care_recipient_id: str
    caregiver_id: str
    category: InformationCategory
    max_tier: int  # 0-3
    consent_status: ConsentStatus
    granted_at: Optional[str] = None   # ISO datetime string
    expires_at: Optional[str] = None   # ISO datetime string, null = no expiry
    override_reason: Optional[str] = None

    def to_dict(self):
        return {
            "consent_id": self.consent_id,
            "care_recipient_id": self.care_recipient_id,
            "caregiver_id": self.caregiver_id,
            "category": self.category.value,
            "max_tier": self.max_tier,
            "consent_status": self.consent_status.value,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "override_reason": self.override_reason,
        }

    def is_active(self, now: Optional[datetime] = None) -> bool:
        """Check if this consent is currently active (granted + not expired)."""
        if self.consent_status != ConsentStatus.GRANTED:
            return False
        if self.expires_at:
            now = now or datetime.utcnow()
            try:
                expiry = datetime.fromisoformat(self.expires_at.replace("Z", "+00:00"))
                if now.tzinfo is None:
                    expiry = expiry.replace(tzinfo=None)
                return now < expiry
            except (ValueError, TypeError):
                return False
        return True


import hashlib
import json

GENESIS_HASH = "0" * 64

def compute_audit_hash(
    audit_id: str,
    timestamp: str,
    event_type: str,
    actor_id: str,
    care_recipient_id: str,
    details: dict,
    prev_hash: str = GENESIS_HASH,
) -> str:
    """Compute deterministic SHA-256 hash for an audit log entry."""
    canonical_details = json.dumps(details, sort_keys=True, default=str)
    payload = f"{audit_id}|{timestamp}|{event_type}|{actor_id}|{care_recipient_id}|{canonical_details}|{prev_hash}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class AuditEntry:
    """An immutable, tamper-evident hash-chained audit log entry."""
    audit_id: str
    timestamp: str          # ISO datetime
    event_type: str         # "consent_change", "alert_generated", "alert_filtered", "consent_expired", "webhook_ingest"
    actor_id: str           # Who initiated the change
    care_recipient_id: str
    details: dict = field(default_factory=dict)
    prev_hash: str = GENESIS_HASH
    entry_hash: Optional[str] = None

    def __post_init__(self):
        if not self.entry_hash:
            self.entry_hash = compute_audit_hash(
                self.audit_id,
                self.timestamp,
                self.event_type,
                self.actor_id,
                self.care_recipient_id,
                self.details,
                self.prev_hash,
            )

    def to_dict(self):
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "care_recipient_id": self.care_recipient_id,
            "details": self.details,
            "prev_hash": self.prev_hash,
            "entry_hash": self.entry_hash,
        }


@dataclass
class SyntheticSignal:
    """A synthetic signal from a device, check-in, or sensor."""
    signal_id: str
    care_recipient_id: str
    signal_type: SignalType
    timestamp: str          # ISO datetime
    value: Optional[float] = None       # e.g., activity score, vital reading
    metadata: dict = field(default_factory=dict)  # flexible extra data

    def to_dict(self):
        return {
            "signal_id": self.signal_id,
            "care_recipient_id": self.care_recipient_id,
            "signal_type": self.signal_type.value,
            "timestamp": self.timestamp,
            "value": self.value,
            "metadata": self.metadata,
        }


@dataclass
class Alert:
    """A generated alert from the rules engine."""
    alert_id: str
    care_recipient_id: str
    alert_type: AlertType
    category: InformationCategory
    severity: AlertSeverity
    rule_fired: str              # Name of the rule that generated this alert
    evidence_summary: str        # Plain-language evidence description
    generated_at: str            # ISO datetime
    requires_tier: int           # Minimum tier needed to see this alert
    is_data_gap: bool = False    # True if this is a system alert, not a health event
    trend_info: Optional[str] = None    # Trend context for Tier 2+
    clinical_note: Optional[str] = None # Qualitative clinical note for Tier 3
    evidence_data: dict = field(default_factory=dict)  # Structured evidence for drill-down
    actionable_step: Optional[str] = None  # Non-medical next step suggestion

    def to_dict(self):
        return {
            "alert_id": self.alert_id,
            "care_recipient_id": self.care_recipient_id,
            "alert_type": getattr(self.alert_type, "value", self.alert_type),
            "category": getattr(self.category, "value", self.category),
            "severity": getattr(self.severity, "value", self.severity),
            "rule_fired": self.rule_fired,
            "evidence_summary": self.evidence_summary,
            "generated_at": self.generated_at,
            "requires_tier": self.requires_tier,
            "is_data_gap": self.is_data_gap,
            "trend_info": self.trend_info,
            "clinical_note": self.clinical_note,
            "evidence_data": self.evidence_data,
            "actionable_step": self.actionable_step,
        }


@dataclass
class RenderableAlert:
    """An alert after consent/tier filtering — safe to show to a specific caregiver."""
    alert_id: str
    care_recipient_id: str
    alert_type: str
    category: str
    severity: str
    rule_fired: str
    rendered_tier: int          # The tier at which this alert is being rendered
    generated_at: str
    is_data_gap: bool = False

    # Content fields — populated based on rendered tier
    summary: str = ""           # Always shown (Tier 0+)
    category_detail: Optional[str] = None    # Tier 1+
    evidence_summary: Optional[str] = None   # Tier 1+
    trend_info: Optional[str] = None         # Tier 2+
    clinical_note: Optional[str] = None      # Tier 3 only
    evidence_data: Optional[dict] = None     # Tier 2+ (sparkline data etc.)
    actionable_step: Optional[str] = None    # Tier 1+

    def to_dict(self):
        result = {
            "alert_id": self.alert_id,
            "care_recipient_id": self.care_recipient_id,
            "alert_type": self.alert_type,
            "category": self.category,
            "severity": self.severity,
            "rule_fired": self.rule_fired,
            "rendered_tier": self.rendered_tier,
            "generated_at": self.generated_at,
            "is_data_gap": self.is_data_gap,
            "summary": self.summary,
        }
        # Only include fields appropriate to the rendered tier
        if self.category_detail is not None:
            result["category_detail"] = self.category_detail
        if self.evidence_summary is not None:
            result["evidence_summary"] = self.evidence_summary
        if self.trend_info is not None:
            result["trend_info"] = self.trend_info
        if self.clinical_note is not None:
            result["clinical_note"] = self.clinical_note
        if self.evidence_data is not None:
            result["evidence_data"] = self.evidence_data
        if self.actionable_step is not None:
            result["actionable_step"] = self.actionable_step
        return result


@dataclass
class DataSourceStatus:
    """Freshness/status of a data source for a care recipient."""
    source_type: str       # signal type
    care_recipient_id: str
    last_received: Optional[str] = None  # ISO datetime of last signal
    expected_interval_hours: float = 4.0
    state: FreshnessState = FreshnessState.MISSING
    message: str = ""

    def to_dict(self):
        return {
            "source_type": self.source_type,
            "care_recipient_id": self.care_recipient_id,
            "last_received": self.last_received,
            "expected_interval_hours": self.expected_interval_hours,
            "state": self.state.value,
            "message": self.message,
        }


def generate_id() -> str:
    """Generate a short unique ID."""
    return str(uuid.uuid4())[:8]
