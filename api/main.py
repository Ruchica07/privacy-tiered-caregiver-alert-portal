"""
FastAPI Main Application — Privacy-Tiered Caregiver Alert Portal API (Phase 2)

Features:
- Robust Edge Ingestion Router with HMAC-SHA256 WebHook verification (`POST /api/v1/ingest/webhook`)
- MQTT IoT Sensor Telemetry Router (`POST /api/v1/ingest/mqtt`)
- Cryptographic SHA-256 Tamper-Evident Audit Chain Verification (`GET /api/audit/verify`)
- Production JWT Bearer Token Authentication & Server-Side RBAC (`/api/auth/login`, `/api/auth/me`)
- Multi-Resident Care Coordinator Fleet Overview (`GET /api/fleet-overview`)
- Quantitative Evaluation Benchmarks (Review 1 Baseline, Advanced Stress, Stakeholder SUS)
- Deterministic Alert Rules & Server-Side Privacy Tier Redaction (Tier 0 to Tier 3)
"""

import sys
import os
import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, HTTPException, Header, Request, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from api.data_store import get_store
from engine.rules import run_all_rules
from engine.consent_filter import (
    filter_alerts_for_caregiver, filter_alert_for_caregiver, get_caregiver_access_summary,
)
from engine.content_linter import lint_text, sanitize_alert_text
from engine.models import generate_id, FreshnessState, SignalType, InformationCategory
from engine.ingestion import get_ingestion_pipeline, IngestionResult
from engine.notification_dispatcher import get_notification_dispatcher, DeliveryChannel, DeliveryStatus
from api.mqtt_adapter import get_mqtt_adapter, MQTTMessage
from api.auth import (
    LoginRequest, TokenResponse, get_current_user, require_auth,
    verify_password, create_access_token, SEED_USERS, ACCESS_TOKEN_EXPIRE_MINUTES,
    verify_caregiver_access
)
from api.oidc_auth import validate_oidc_token, OIDCValidationResult
from api.middleware import CorrelationIdMiddleware, register_exception_handlers

app = FastAPI(
    title="AegisCare: Privacy-Tiered Caregiver Alert Portal API",
    description=(
        "Production-grade operational & wellbeing support API for older adults living alone. "
        "Implements cryptographic audit verification, edge deduplication, HMAC webhooks, JWT/OIDC RBAC, "
        "and privacy-tiered notification dispatching."
    ),
    version="0.3.0",
)

# Structured Observability & Correlation ID Middleware (Phase 3)
app.add_middleware(CorrelationIdMiddleware)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Standardized Error Envelopes
register_exception_handlers(app)


# ---------------------------------------------------------------------------
# Pydantic Request / Response Models
# ---------------------------------------------------------------------------

class SignalInput(BaseModel):
    care_recipient_id: str
    signal_type: str
    value: Optional[float] = None
    metadata: dict = {}


class WebhookIngestPayload(BaseModel):
    care_recipient_id: Optional[str] = None
    recipient_id: Optional[str] = None
    signal_type: Optional[str] = None
    event: Optional[str] = None
    timestamp: Optional[str] = None
    value: Optional[float] = None
    event_id: Optional[str] = None
    metadata: dict = {}


class MQTTIngestRequest(BaseModel):
    topic: str
    payload: Any
    qos: int = 1


class ConsentUpdate(BaseModel):
    caregiver_id: str
    category: str
    max_tier: int
    consent_status: str
    expires_at: Optional[str] = None
    override_reason: Optional[str] = None


class ConsentUpdateRequest(BaseModel):
    updates: List[ConsentUpdate]
    actor_id: str = "admin"


class RunRulesRequest(BaseModel):
    evaluation_time: Optional[str] = None


class OIDCValidateRequest(BaseModel):
    token: str


class NotificationDispatchRequest(BaseModel):
    alert_id: str
    caregiver_id: str
    channel: str = "web_push"
    recipient_contact: Optional[str] = None


# ---------------------------------------------------------------------------
# Authentication Endpoints
# ---------------------------------------------------------------------------

@app.post("/api/auth/login", response_model=TokenResponse)
def login(request: LoginRequest):
    """
    Authenticate caregiver and issue a signed JWT access token.
    Pre-seeded accounts: jane.smith, bob.smith, maria.garcia, dr.sarah.chen, admin
    Default password: AegisCare2026!
    """
    user = SEED_USERS.get(request.username)
    if not user or not verify_password(request.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Issue JWT token
    token_payload = {
        "sub": user["username"],
        "caregiver_id": user["caregiver_id"],
        "role": user["role"],
        "care_recipient_ids": user["care_recipient_ids"],
    }
    access_token = create_access_token(token_payload)

    # Record login audit event
    store = get_store()
    store.add_audit_entry({
        "audit_id": generate_id(),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": "user_login",
        "actor_id": user["caregiver_id"],
        "care_recipient_id": user["care_recipient_ids"][0] if user["care_recipient_ids"] else "system",
        "details": {"username": user["username"], "role": user["role"]},
    })

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in_seconds=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user={
            "caregiver_id": user["caregiver_id"],
            "username": user["username"],
            "name": user["name"],
            "role": user["role"],
            "care_recipient_ids": user["care_recipient_ids"],
        }
    )


@app.get("/api/auth/me")
def get_current_user_profile(current_user: dict = Depends(require_auth)):
    """Retrieve profile and RBAC permissions of the authenticated user."""
    return {"user": current_user}


@app.post("/api/auth/oidc/validate")
def validate_oidc(request: OIDCValidateRequest):
    """
    Enterprise-ready OIDC Bearer token validation endpoint.
    Validates token signature, issuer, audience, expiration, and claims mapping.
    """
    result = validate_oidc_token(request.token)
    if not result.is_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=result.error_message or "OIDC token validation failed.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "is_valid": True,
        "status": result.status,
        "caregiver_profile": result.caregiver_profile,
        "claims": result.claims.dict() if result.claims else None,
    }


# ---------------------------------------------------------------------------
# External Ingestion Interfaces: WebHook & MQTT
# ---------------------------------------------------------------------------

@app.post("/api/v1/ingest/webhook")
async def ingest_webhook(
    request: Request,
    x_signature_256: Optional[str] = Header(None),
):
    """
    Authenticated WebHook endpoint for external vendor devices/gateways.
    - Verifies HMAC-SHA256 signature when header is present
    - Normalizes multi-vendor payload schemas
    - Rejects future timestamps (>60s clock skew)
    - Enforces idempotency via sliding-window deduplication
    - Applies sensor noise smoothing & drift detection
    - Records tamper-evident audit entry
    """
    raw_body = await request.body()
    pipeline = get_ingestion_pipeline()

    # If signature header is provided, verify HMAC-SHA256
    if x_signature_256 is not None:
        if not pipeline.verify_signature(raw_body, x_signature_256):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid HMAC-SHA256 signature. Webhook rejected.",
            )

    try:
        payload_data = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON body.",
        )

    # Process through pipeline
    result = pipeline.process_incoming_event(payload_data)

    if not result.success:
        status_code = status.HTTP_422_UNPROCESSABLE_ENTITY if "rejected_future_timestamp" in result.status else status.HTTP_400_BAD_REQUEST
        return {
            "success": False,
            "status": result.status,
            "validation_errors": result.validation_errors,
        }

    # If duplicate, ignore cleanly
    if result.is_duplicate:
        return {
            "success": True,
            "status": "duplicate_ignored",
            "is_duplicate": True,
            "signal_id": result.signal_id,
            "event_id": result.event_id,
        }

    # Store valid signal
    store = get_store()
    store.add_signal(result.normalized_signal)

    # Record tamper-evident audit entry
    audit_entry = store.add_audit_entry({
        "audit_id": generate_id(),
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "event_type": "webhook_ingest",
        "actor_id": "webhook_gateway",
        "care_recipient_id": result.normalized_signal["care_recipient_id"],
        "details": {
            "signal_id": result.signal_id,
            "signal_type": result.normalized_signal["signal_type"],
            "event_id": result.event_id,
            "noise_smoothed": result.noise_smoothed,
            "drift_detected": result.drift_detected,
        },
    })

    return {
        "success": True,
        "status": "ingested",
        "signal_id": result.signal_id,
        "event_id": result.event_id,
        "normalized_signal": result.normalized_signal,
        "noise_smoothed": result.noise_smoothed,
        "drift_detected": result.drift_detected,
        "audit_entry_hash": audit_entry.get("entry_hash"),
    }


@app.post("/api/v1/ingest/mqtt")
def ingest_mqtt(request: MQTTIngestRequest):
    """
    Ingest an IoT MQTT message from a local broker or simulator.
    """
    adapter = get_mqtt_adapter()
    msg = MQTTMessage(topic=request.topic, payload=request.payload, qos=request.qos)
    result = adapter.handle_message(msg)

    return {
        "success": result.success,
        "status": result.status,
        "signal_id": result.signal_id,
        "is_duplicate": result.is_duplicate,
        "validation_errors": result.validation_errors,
        "noise_smoothed": result.noise_smoothed,
    }


# ---------------------------------------------------------------------------
# User & Caregiver Listing Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/care-recipients")
def list_care_recipients():
    """List all care recipients."""
    store = get_store()
    return {"care_recipients": store.get_care_recipients()}


@app.get("/api/caregivers")
def list_caregivers():
    """List all caregivers."""
    store = get_store()
    return {"caregivers": store.get_caregivers()}


@app.get("/api/caregivers/{recipient_id}")
def list_caregivers_for_recipient(recipient_id: str):
    """List caregivers assigned to a specific care recipient."""
    store = get_store()
    return {"caregivers": store.get_caregivers_for_recipient(recipient_id)}


# ---------------------------------------------------------------------------
# Multi-Resident Care Coordinator Fleet Overview (Phase 2)
# ---------------------------------------------------------------------------

@app.get("/api/fleet-overview")
def get_fleet_overview(caregiver_id: Optional[str] = Query(None), current_user: Optional[dict] = Depends(get_current_user)):
    """
    Multi-resident fleet summary for care coordinators managing multiple older adults.
    Returns per-resident aggregated wellbeing status, active alerts by severity,
    data source freshness, and consented tier levels.
    """
    store = get_store()
    active_caregiver_id = current_user.get("caregiver_id") if current_user else (caregiver_id or "cg_004")
    
    recipients = store.get_care_recipients()
    fleet = []

    # Use dataset metadata base_time for reproducible freshness evaluation
    metadata = store.get_metadata()
    base_time_str = metadata.get("base_time", None)
    now = datetime.fromisoformat(base_time_str.replace("Z", "")) if base_time_str else datetime.utcnow()

    for r in recipients:
        rid = r["id"]
        alerts = store.get_alerts(rid)
        consent_matrix = store.get_consent_matrix(rid)

        # Filter alerts according to caregiver permissions
        rendered_alerts, _ = filter_alerts_for_caregiver(alerts, active_caregiver_id, consent_matrix, now=now)

        # Counts by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for a in rendered_alerts:
            sev = a.get("severity", "low").lower()
            if sev in severity_counts:
                severity_counts[sev] += 1

        # Check heartbeat freshness
        heartbeat_signals = store.get_signals(rid, "device_heartbeat")
        freshness = "fresh"
        if not heartbeat_signals:
            freshness = "missing"
        else:
            latest = max(heartbeat_signals, key=lambda s: s.get("timestamp", ""))
            latest_ts = datetime.fromisoformat(latest["timestamp"].replace("Z", ""))
            hours_since = (now - latest_ts).total_seconds() / 3600
            if hours_since > r.get("device_heartbeat_expected_hours", 2.0) * 3:
                freshness = "missing"
            elif hours_since > r.get("device_heartbeat_expected_hours", 2.0):
                freshness = "stale"

        # Overall status label
        if severity_counts["critical"] > 0 or severity_counts["high"] > 0:
            status_badge = "Attention Needed"
            status_type = "warning"
        elif freshness == "missing":
            status_badge = "Device Offline"
            status_type = "missing"
        else:
            status_badge = "Operational Normal"
            status_type = "normal"

        access_summary = get_caregiver_access_summary(active_caregiver_id, rid, consent_matrix, now=now)

        fleet.append({
            "care_recipient_id": rid,
            "name": r["name"],
            "status_badge": status_badge,
            "status_type": status_type,
            "freshness": freshness,
            "total_active_alerts": len(rendered_alerts),
            "severity_counts": severity_counts,
            "overall_tier_label": access_summary.get("overall_tier_label", "Tier 1"),
            "baseline_activity_mean": r.get("baseline_activity_mean", 50.0),
            "accessible_categories_count": len(access_summary.get("accessible_categories", [])),
        })

    return {"fleet": fleet, "total_recipients": len(fleet), "coordinator_id": active_caregiver_id}


# ---------------------------------------------------------------------------
# Signal Ingestion (Legacy Synthetic POST endpoint)
# ---------------------------------------------------------------------------

@app.post("/api/synthetic/signals")
def ingest_signal(signal: SignalInput):
    """
    Ingest a synthetic sensor/check-in event (backward-compatible).
    """
    store = get_store()
    signal_dict = {
        "signal_id": generate_id(),
        "care_recipient_id": signal.care_recipient_id,
        "signal_type": signal.signal_type,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "value": signal.value,
        "metadata": signal.metadata,
    }
    store.add_signal(signal_dict)
    return {"status": "ok", "signal_id": signal_dict["signal_id"]}


# ---------------------------------------------------------------------------
# Rules Engine Execution
# ---------------------------------------------------------------------------

@app.post("/api/run-rules/{care_recipient_id}")
def run_rules(care_recipient_id: str, body: Optional[RunRulesRequest] = None):
    """Run the rules engine for a single care recipient."""
    store = get_store()
    recipient = store.get_care_recipient(care_recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Care recipient not found")

    signals = store.get_signals(care_recipient_id)

    eval_time = None
    if body and body.evaluation_time:
        try:
            eval_time = datetime.fromisoformat(body.evaluation_time.replace("Z", ""))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid evaluation_time format")

    alerts = run_all_rules(signals, recipient, eval_time)

    # Store alerts
    store.clear_alerts(care_recipient_id)
    for alert in alerts:
        store.add_alert(alert)

    # Record tamper-evident audit entry
    store.add_audit_entry({
        "audit_id": generate_id(),
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "event_type": "rules_executed",
        "actor_id": "system",
        "care_recipient_id": care_recipient_id,
        "details": {"alerts_generated": len(alerts)},
    })

    return {"alerts_generated": len(alerts), "alerts": alerts}


@app.post("/api/run-rules-all")
def run_rules_all():
    """Run rules for all care recipients across the dataset."""
    store = get_store()
    total = 0
    for recipient in store.get_care_recipients():
        signals = store.get_signals(recipient["id"])
        metadata = store.get_metadata()
        base_time_str = metadata.get("base_time", None)
        eval_time = None
        if base_time_str:
            try:
                eval_time = datetime.fromisoformat(base_time_str.replace("Z", ""))
            except ValueError:
                pass

        alerts = run_all_rules(signals, recipient, eval_time)
        store.clear_alerts(recipient["id"])
        for alert in alerts:
            store.add_alert(alert)
        total += len(alerts)

    return {"total_alerts_generated": total}


# ---------------------------------------------------------------------------
# Alert Endpoints (Consent-Filtered + Server-Side RBAC Guard)
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
def get_alerts(caregiver_id: str = Query(...), current_user: Optional[dict] = Depends(get_current_user)):
    """
    Get the tier-filtered, consent-checked alert feed for a caregiver.
    Enforces RBAC anti-impersonation if JWT Bearer token is provided.
    """
    # Enforce authorization if token provided
    verify_caregiver_access(caregiver_id, current_user=current_user)

    store = get_store()
    caregiver = store.get_caregiver(caregiver_id)
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    all_alerts = []
    for recipient_id in caregiver.get("care_recipient_ids", []):
        alerts = store.get_alerts(recipient_id)
        consent_matrix = store.get_consent_matrix(recipient_id)

        rendered, audit = filter_alerts_for_caregiver(alerts, caregiver_id, consent_matrix)
        all_alerts.extend(rendered)

        # Log disclosure audit entries
        for entry in audit:
            store.add_audit_entry({
                "audit_id": generate_id(),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "alert_filtered",
                "actor_id": caregiver_id,
                "care_recipient_id": recipient_id,
                "details": entry,
            })

    all_alerts.sort(key=lambda a: a.get("generated_at", ""), reverse=True)
    return {"alerts": all_alerts, "total": len(all_alerts)}


@app.get("/api/alerts/{alert_id}/evidence")
def get_alert_evidence(alert_id: str, caregiver_id: str = Query(...), current_user: Optional[dict] = Depends(get_current_user)):
    """Get drill-down evidence for a specific alert, tier-filtered."""
    verify_caregiver_access(caregiver_id, current_user=current_user)

    store = get_store()
    caregiver = store.get_caregiver(caregiver_id)
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    for recipient_id in caregiver.get("care_recipient_ids", []):
        alerts = store.get_alerts(recipient_id)
        for alert in alerts:
            if alert.get("alert_id") == alert_id:
                consent_matrix = store.get_consent_matrix(recipient_id)
                rendered, _ = filter_alert_for_caregiver(alert, caregiver_id, consent_matrix)
                if rendered:
                    return {"evidence": rendered}
                else:
                    raise HTTPException(status_code=403, detail="Not authorized to view this alert")

    raise HTTPException(status_code=404, detail="Alert not found")


@app.get("/api/access-summary")
def get_access_summary(caregiver_id: str = Query(...), care_recipient_id: str = Query(...)):
    """Get the access summary for a caregiver-recipient pair."""
    store = get_store()
    consent_matrix = store.get_consent_matrix(care_recipient_id)
    summary = get_caregiver_access_summary(caregiver_id, care_recipient_id, consent_matrix)
    return summary


# ---------------------------------------------------------------------------
# Consent Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/consent/{care_recipient_id}")
def get_consent(care_recipient_id: str):
    """Get the full consent matrix for a care recipient."""
    store = get_store()
    matrix = store.get_consent_matrix(care_recipient_id)
    caregivers = store.get_caregivers_for_recipient(care_recipient_id)
    return {"consent_matrix": matrix, "caregivers": caregivers}


@app.put("/api/consent/{care_recipient_id}")
def update_consent(care_recipient_id: str, request: ConsentUpdateRequest):
    """Update consent records for a care recipient with tamper-evident audit logging."""
    store = get_store()
    updates = [u.dict() for u in request.updates]
    audit_entries = store.update_consent(care_recipient_id, updates, request.actor_id)
    return {"status": "updated", "audit_entries": audit_entries}


# ---------------------------------------------------------------------------
# Data Status / Freshness Endpoints
# ---------------------------------------------------------------------------

@app.get("/api/data-status/{care_recipient_id}")
def get_data_status(care_recipient_id: str):
    """Get freshness/missing-data status per source for UI badges."""
    store = get_store()
    recipient = store.get_care_recipient(care_recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Care recipient not found")

    metadata = store.get_metadata()
    base_time_str = metadata.get("base_time", None)
    now = datetime.fromisoformat(base_time_str.replace("Z", "")) if base_time_str else datetime.utcnow()

    sources = {
        "check_in": recipient.get("expected_checkin_window_hours", 4.0),
        "activity_score": 8.0,
        "medication_event": recipient.get("expected_medication_window_hours", 12.0),
        "device_heartbeat": recipient.get("device_heartbeat_expected_hours", 2.0),
        "social_contact": recipient.get("social_contact_expected_days", 3) * 24,
        "vitals_reading": 12.0,
        "location_event": 24.0,
    }

    statuses = []
    for source_type, expected_hours in sources.items():
        signals = store.get_signals(care_recipient_id, source_type)

        if not signals:
            statuses.append({
                "source_type": source_type,
                "state": FreshnessState.MISSING.value,
                "last_received": None,
                "expected_interval_hours": expected_hours,
                "message": f"No data has ever been received from {source_type.replace('_', ' ')}.",
            })
            continue

        latest = max(signals, key=lambda s: s.get("timestamp", ""))
        latest_ts = datetime.fromisoformat(latest["timestamp"].replace("Z", ""))
        hours_since = (now - latest_ts).total_seconds() / 3600

        if hours_since <= expected_hours:
            state = FreshnessState.FRESH
            message = f"Data is current (last received {hours_since:.1f}h ago)."
        elif hours_since <= expected_hours * 3:
            state = FreshnessState.STALE
            message = f"Last updated {hours_since:.1f}h ago — expected every {expected_hours:.0f}h."
        else:
            state = FreshnessState.MISSING
            message = f"No data received for {hours_since:.1f}h. Check if device is connected."

        statuses.append({
            "source_type": source_type,
            "state": state.value,
            "last_received": latest["timestamp"],
            "expected_interval_hours": expected_hours,
            "message": message,
        })

    return {"care_recipient_id": care_recipient_id, "sources": statuses}


# ---------------------------------------------------------------------------
# Tamper-Evident Audit & Verification Endpoints (Phase 2)
# ---------------------------------------------------------------------------

@app.get("/api/audit/verify")
@app.get("/api/audit-verify")
def verify_audit_trail(care_recipient_id: Optional[str] = Query(None)):
    """
    Cryptographically verify the SHA-256 hash chain of the audit trail.
    Ensures no past records were modified, injected, or deleted.
    """
    store = get_store()
    result = store.verify_audit_chain(care_recipient_id)
    return result


@app.get("/api/audit/{care_recipient_id}")
def get_audit_log(care_recipient_id: str):
    """Get the audit trail for a care recipient."""
    store = get_store()
    log = store.get_audit_log(care_recipient_id)
    return {"audit_log": log, "total": len(log)}


@app.get("/api/audit/{care_recipient_id}/verify")
def verify_recipient_audit_trail(care_recipient_id: str):
    """Verify the hash chain for a specific care recipient."""
    store = get_store()
    result = store.verify_audit_chain(care_recipient_id)
    return result


# ---------------------------------------------------------------------------
# Quantitative Evaluation Benchmarks & Metrics
# ---------------------------------------------------------------------------

@app.get("/api/ground-truth")
def get_ground_truth():
    """Get ground truth anomalies for evaluation."""
    store = get_store()
    return {"ground_truth": store.get_ground_truth()}


@app.get("/api/all-alerts-raw")
def get_all_alerts_raw():
    """Get all raw (unfiltered) alerts — for metrics evaluation only."""
    store = get_store()
    return {"alerts": store.get_alerts()}


@app.get("/api/evaluation-metrics")
def get_evaluation_metrics():
    """Compute quantitative evaluation metrics across the 30-day synthetic benchmark dataset."""
    from eval.metrics import evaluate_system
    results = evaluate_system()
    return {"metrics": results}


@app.get("/api/stakeholder-metrics")
def get_stakeholder_metrics():
    """Retrieve structured usability evaluation results (System Usability Scale protocol)."""
    from eval.stakeholder_evaluation import run_stakeholder_evaluation
    results = run_stakeholder_evaluation()
    return {"stakeholder_evaluation": results}


@app.get("/api/advanced-evaluation-metrics")
def get_advanced_evaluation_metrics():
    """Compute advanced stress metrics (packet loss, noise, drift, duplicate rejection)."""
    from eval.advanced_metrics import evaluate_advanced_stress
    results = evaluate_advanced_stress()
    return {"advanced_metrics": results}


# ---------------------------------------------------------------------------
# Content Linter Check (Demo Endpoint)
# ---------------------------------------------------------------------------

@app.post("/api/lint-check")
def lint_check(text: str = Query(...)):
    """Check text against the content linter for banned medical terms."""
    violations = lint_text(text)
    sanitized, _ = sanitize_alert_text(text)
    return {
        "original": text,
        "is_compliant": len(violations) == 0,
        "violations": [v.to_dict() for v in violations],
        "sanitized": sanitized,
    }


# ---------------------------------------------------------------------------
# Notification Dispatcher Endpoints (Phase 3)
# ---------------------------------------------------------------------------

@app.post("/api/notifications/dispatch")
def dispatch_notification(
    request: NotificationDispatchRequest,
    current_user: Optional[dict] = Depends(get_current_user),
):
    """
    Dispatches a privacy-filtered alert notification to a caregiver.
    Applies role-based consent filtering, content linting, idempotency deduplication,
    and records a tamper-evident audit log.
    """
    # Enforce RBAC
    verify_caregiver_access(request.caregiver_id, current_user=current_user)

    store = get_store()
    caregiver = store.get_caregiver(request.caregiver_id)
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    # Locate the target alert
    target_alert = None
    target_recipient_id = None
    for r_id in caregiver.get("care_recipient_ids", []):
        alerts = store.get_alerts(r_id)
        for a in alerts:
            if a.get("alert_id") == request.alert_id:
                target_alert = a
                target_recipient_id = r_id
                break
        if target_alert:
            break

    if not target_alert:
        raise HTTPException(status_code=404, detail="Alert not found for this caregiver's assigned care recipients")

    consent_matrix = store.get_consent_matrix(target_recipient_id)
    dispatcher = get_notification_dispatcher()

    recipient_contact = request.recipient_contact or f"{request.caregiver_id}@notifications.local"
    try:
        channel_enum = DeliveryChannel(request.channel)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid delivery channel '{request.channel}'. Supported: 'web_push', 'sms'."
        )

    result = dispatcher.dispatch_alert(
        raw_alert=target_alert,
        caregiver=caregiver,
        consent_matrix=consent_matrix,
        channel=channel_enum,
        recipient_contact=recipient_contact,
        audit_sink=store,
    )

    return result


@app.get("/api/notifications/history")
def get_notification_history(
    care_recipient_id: Optional[str] = Query(None),
    current_user: Optional[dict] = Depends(get_current_user),
):
    """Retrieve recorded notification dispatches and sandbox delivery states."""
    dispatcher = get_notification_dispatcher()
    history = dispatcher.get_dispatch_history(care_recipient_id=care_recipient_id)
    return {"notifications": history, "total": len(history)}
