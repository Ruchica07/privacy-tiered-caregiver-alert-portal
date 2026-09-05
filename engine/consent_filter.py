"""
Consent Filter — Privacy-Critical Disclosure Gating Layer

Pure function that determines what a specific caregiver is allowed to see,
based on the consent matrix. Every filtering decision is logged for audit.

Fail-safe: unknown consent = no disclosure beyond Tier 0.
Expired consent = automatically drop to Tier 0.
"""

from datetime import datetime
from typing import List, Optional, Dict, Tuple
from engine.models import (
    Alert, RenderableAlert, ConsentRecord, ConsentStatus,
    InformationCategory, AuditEntry, FreshnessState,
    generate_id,
)
from engine.content_linter import sanitize_alert_text


# ---------------------------------------------------------------------------
# Category display names (for Tier 1+ rendering)
# ---------------------------------------------------------------------------

CATEGORY_DISPLAY_NAMES = {
    InformationCategory.ACTIVITY_ENGAGEMENT: "Activity & Engagement",
    InformationCategory.MEDICATION_ADHERENCE: "Medication Adherence",
    InformationCategory.VITALS_SUMMARY: "Vitals Summary",
    InformationCategory.LOCATION_SAFETY: "Location & Safety",
    InformationCategory.SOCIAL_ISOLATION_SIGNAL: "Social & Isolation",
    InformationCategory.DIAGNOSIS_CONDITIONS: "Diagnosis & Conditions",
}

# Tier 0 summary templates (binary wellness ping)
TIER0_SUMMARIES = {
    "low": "Everything looks on track.",
    "medium": "Something may need attention.",
    "high": "Attention may be needed soon.",
    "critical": "Urgent attention may be needed.",
}


# ---------------------------------------------------------------------------
# Core consent lookup
# ---------------------------------------------------------------------------

def lookup_consent(
    caregiver_id: str,
    category: InformationCategory,
    consent_matrix: List[dict],
    now: Optional[datetime] = None,
) -> Tuple[Optional[dict], int]:
    """
    Look up the active consent for a caregiver × category.
    
    Returns:
        Tuple of (consent_record_dict or None, effective_max_tier).
        If no consent found or consent is not active, effective tier = -1
        (meaning: no access, not even Tier 0 for this specific category lookup;
        the caller handles the Tier-0 wellness ping fallback).
    """
    now = now or datetime.utcnow()

    for consent in consent_matrix:
        if (consent.get("caregiver_id") == caregiver_id and
                consent.get("category") == category.value):

            status = consent.get("consent_status", "pending")

            # Pending or revoked = no access
            if status != "granted":
                return consent, -1

            # Check expiry
            expires_at = consent.get("expires_at")
            if expires_at:
                try:
                    expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
                    if now.tzinfo is None:
                        expiry = expiry.replace(tzinfo=None)
                    if now >= expiry:
                        return consent, -1  # Expired
                except (ValueError, TypeError):
                    return consent, -1  # Parse error = fail safe

            return consent, consent.get("max_tier", 0)

    # No consent record found at all = fail safe, no access
    return None, -1


# ---------------------------------------------------------------------------
# Core filtering function
# ---------------------------------------------------------------------------

def filter_alert_for_caregiver(
    alert: dict,
    caregiver_id: str,
    consent_matrix: List[dict],
    now: Optional[datetime] = None,
) -> Tuple[Optional[dict], dict]:
    """
    The privacy-critical filter: determines what a caregiver can see.
    
    Args:
        alert: Alert dict (from rules engine)
        caregiver_id: The caregiver requesting to see this alert
        consent_matrix: List of consent record dicts
        now: Current time (for expiry checks)
    
    Returns:
        Tuple of (RenderableAlert dict or None, audit_details dict).
        - If the caregiver has sufficient consent: returns a tier-filtered alert.
        - If not: returns None (alert is not shown to this caregiver).
        - In both cases, returns audit details for logging.
    """
    now = now or datetime.utcnow()
    category_str = alert.get("category", "")

    try:
        category = InformationCategory(category_str)
    except ValueError:
        # Unknown category = fail safe, don't show
        return None, {
            "decision": "withheld",
            "reason": f"Unknown category: {category_str}",
            "caregiver_id": caregiver_id,
            "alert_id": alert.get("alert_id", "unknown"),
        }

    # Look up consent
    consent_record, max_tier = lookup_consent(
        caregiver_id, category, consent_matrix, now
    )

    alert_requires_tier = alert.get("requires_tier", 1)

    # --- Decision logic ---

    # Case 1: No consent or negative tier → check if we can still show Tier 0
    if max_tier < 0:
        # No consent at all for this category
        # Data-gap alerts are always shown as Tier 0 (system status, not health info)
        if alert.get("is_data_gap", False):
            rendered = _render_at_tier(alert, 0, caregiver_id)
            audit = {
                "decision": "shown_as_tier0_data_gap",
                "reason": "No consent for category, but data-gap alerts are system status",
                "caregiver_id": caregiver_id,
                "alert_id": alert.get("alert_id"),
                "rendered_tier": 0,
            }
            return rendered, audit

        return None, {
            "decision": "withheld",
            "reason": "No active consent for this category",
            "caregiver_id": caregiver_id,
            "alert_id": alert.get("alert_id"),
            "category": category_str,
            "consent_status": consent_record.get("consent_status") if consent_record else "none",
        }

    # Case 2: Consent exists but tier is below alert's requirement
    if max_tier < alert_requires_tier:
        # Render at the caregiver's max tier (downgraded)
        rendered = _render_at_tier(alert, max_tier, caregiver_id)
        audit = {
            "decision": "shown_downgraded",
            "reason": f"Consent tier ({max_tier}) < required tier ({alert_requires_tier}), downgraded",
            "caregiver_id": caregiver_id,
            "alert_id": alert.get("alert_id"),
            "rendered_tier": max_tier,
            "required_tier": alert_requires_tier,
        }
        return rendered, audit

    # Case 3: Sufficient consent — render at the alert's required tier
    # (never render above the caregiver's consented tier)
    render_tier = min(max_tier, alert_requires_tier)
    rendered = _render_at_tier(alert, render_tier, caregiver_id)
    audit = {
        "decision": "shown",
        "reason": "Consent sufficient",
        "caregiver_id": caregiver_id,
        "alert_id": alert.get("alert_id"),
        "rendered_tier": render_tier,
        "max_consented_tier": max_tier,
    }
    return rendered, audit


def _render_at_tier(alert: dict, tier: int, caregiver_id: str) -> dict:
    """
    Render an alert at a specific disclosure tier, redacting fields above that tier.
    All text is run through the content linter before rendering.
    """
    severity = alert.get("severity", "medium")
    alert_type = alert.get("alert_type", "generic")
    category = alert.get("category", "")

    # Base renderable alert (always included)
    rendered = {
        "alert_id": alert.get("alert_id"),
        "care_recipient_id": alert.get("care_recipient_id"),
        "alert_type": alert_type,
        "category": category if tier >= 1 else "general",
        "severity": severity,
        "rule_fired": alert.get("rule_fired", ""),
        "rendered_tier": tier,
        "generated_at": alert.get("generated_at"),
        "is_data_gap": alert.get("is_data_gap", False),
    }

    # Tier 0: Binary wellness ping only
    if tier == 0:
        rendered["summary"] = TIER0_SUMMARIES.get(severity, "Status update available.")
        rendered["category"] = "general"  # Don't reveal category at Tier 0
        rendered["rule_fired"] = ""       # Don't reveal rule at Tier 0
        return rendered

    # Tier 1+: Operational alert with category
    evidence = alert.get("evidence_summary", "")
    sanitized_evidence, violations = sanitize_alert_text(evidence, alert_type)
    rendered["summary"] = sanitized_evidence
    rendered["evidence_summary"] = sanitized_evidence

    # Category detail
    try:
        cat_enum = InformationCategory(category)
        rendered["category_detail"] = CATEGORY_DISPLAY_NAMES.get(cat_enum, category)
    except ValueError:
        rendered["category_detail"] = category

    # Actionable step (Tier 1+)
    action = alert.get("actionable_step", "")
    if action:
        sanitized_action, _ = sanitize_alert_text(action, alert_type)
        rendered["actionable_step"] = sanitized_action

    # Tier 2+: Trend info + evidence data
    if tier >= 2:
        trend = alert.get("trend_info", "")
        if trend:
            sanitized_trend, _ = sanitize_alert_text(trend, alert_type)
            rendered["trend_info"] = sanitized_trend
        rendered["evidence_data"] = alert.get("evidence_data", {})

    # Tier 3: Clinical note (qualitative only, still linted)
    if tier >= 3:
        clinical = alert.get("clinical_note", "")
        if clinical:
            sanitized_clinical, _ = sanitize_alert_text(clinical, alert_type)
            rendered["clinical_note"] = sanitized_clinical

    return rendered


# ---------------------------------------------------------------------------
# Batch filtering
# ---------------------------------------------------------------------------

def filter_alerts_for_caregiver(
    alerts: List[dict],
    caregiver_id: str,
    consent_matrix: List[dict],
    now: Optional[datetime] = None,
) -> Tuple[List[dict], List[dict]]:
    """
    Filter a list of alerts for a specific caregiver.
    
    Returns:
        Tuple of (list of renderable alerts, list of audit entries).
    """
    renderable = []
    audit_log = []

    for alert in alerts:
        rendered, audit = filter_alert_for_caregiver(
            alert, caregiver_id, consent_matrix, now
        )
        if rendered is not None:
            renderable.append(rendered)
        audit_log.append(audit)

    return renderable, audit_log


# ---------------------------------------------------------------------------
# Consent summary for UI ("Your access level" banner)
# ---------------------------------------------------------------------------

def get_caregiver_access_summary(
    caregiver_id: str,
    care_recipient_id: str,
    consent_matrix: List[dict],
    now: Optional[datetime] = None,
) -> dict:
    """
    Generate a summary of what a caregiver can see for a care recipient.
    Used for the "Your access level" banner and "Access & Consent" view.
    
    Returns dict with:
      - accessible_categories: list of {category, tier, tier_label}
      - restricted_categories: list of {category, reason}
      - overall_tier: the maximum tier across all categories
    """
    now = now or datetime.utcnow()
    accessible = []
    restricted = []
    overall_tier = -1

    tier_labels = {
        0: "Wellness Ping",
        1: "Operational Alert",
        2: "Operational + Trend",
        3: "Clinical Summary",
    }

    for category in InformationCategory:
        consent, max_tier = lookup_consent(
            caregiver_id, category, consent_matrix, now
        )

        if max_tier >= 0:
            accessible.append({
                "category": category.value,
                "category_name": CATEGORY_DISPLAY_NAMES.get(category, category.value),
                "tier": max_tier,
                "tier_label": tier_labels.get(max_tier, f"Tier {max_tier}"),
            })
            overall_tier = max(overall_tier, max_tier)
        else:
            reason = "No consent granted"
            if consent:
                status = consent.get("consent_status", "pending")
                if status == "revoked":
                    reason = "Consent revoked"
                elif status == "pending":
                    reason = "Consent pending"
                # Check expiry
                expires_at = consent.get("expires_at")
                if expires_at and status == "granted":
                    reason = "Consent expired"
            restricted.append({
                "category": category.value,
                "category_name": CATEGORY_DISPLAY_NAMES.get(category, category.value),
                "reason": reason,
            })

    return {
        "caregiver_id": caregiver_id,
        "care_recipient_id": care_recipient_id,
        "accessible_categories": accessible,
        "restricted_categories": restricted,
        "overall_tier": max(overall_tier, 0),
        "overall_tier_label": tier_labels.get(max(overall_tier, 0), "No Access"),
    }
