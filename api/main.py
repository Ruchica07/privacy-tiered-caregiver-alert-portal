"""
FastAPI Main Application — Privacy-Tiered Caregiver Alert Portal API

This is a stub API simulating what a real senior-monitoring platform
(wearable, smart-home sensors, medication dispenser, check-in app) would
feed in, plus endpoints the caregiver UI consumes.

LIMITATION: This uses mock auth (role selector), no real authentication.
All data is synthetic. No real PHI.
"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

from api.data_store import get_store
from engine.rules import run_all_rules
from engine.consent_filter import (
    filter_alerts_for_caregiver, get_caregiver_access_summary,
)
from engine.content_linter import lint_text, sanitize_alert_text
from engine.models import generate_id, FreshnessState, SignalType

app = FastAPI(
    title="Privacy-Tiered Caregiver Alert Portal API",
    description=(
        "API stub for the caregiver alert portal prototype. "
        "All data is synthetic. This is NOT a medical device."
    ),
    version="0.1.0",
)

# CORS for frontend dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Pydantic models for request bodies
# ---------------------------------------------------------------------------

class SignalInput(BaseModel):
    care_recipient_id: str
    signal_type: str
    value: Optional[float] = None
    metadata: dict = {}


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


# ---------------------------------------------------------------------------
# User / Auth endpoints (mock auth)
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
    """List caregivers for a specific care recipient."""
    store = get_store()
    return {"caregivers": store.get_caregivers_for_recipient(recipient_id)}


# ---------------------------------------------------------------------------
# Signal ingestion (simulates device/sensor feed)
# ---------------------------------------------------------------------------

@app.post("/api/synthetic/signals")
def ingest_signal(signal: SignalInput):
    """
    Ingest a synthetic sensor/check-in event.
    This simulates what a real wearable/smart-home/medication-dispenser feed would provide.
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
# Rules engine trigger
# ---------------------------------------------------------------------------

@app.post("/api/run-rules/{care_recipient_id}")
def run_rules(care_recipient_id: str, body: Optional[RunRulesRequest] = None):
    """
    Run the rules engine for a care recipient against their signals.
    Generates alerts and stores them.
    """
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

    # Store alerts (replace previous for this recipient)
    store.clear_alerts(care_recipient_id)
    for alert in alerts:
        store.add_alert(alert)

    # Audit
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
    """Run rules for all care recipients."""
    store = get_store()
    total = 0
    for recipient in store.get_care_recipients():
        signals = store.get_signals(recipient["id"])
        # Use the base_time from the dataset metadata for consistent evaluation
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
# Alert endpoints (consent-filtered)
# ---------------------------------------------------------------------------

@app.get("/api/alerts")
def get_alerts(caregiver_id: str = Query(...)):
    """
    Get the tier-filtered, consent-checked alert feed for a caregiver.
    This is the primary endpoint the dashboard consumes.
    """
    store = get_store()
    caregiver = store.get_caregiver(caregiver_id)
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    all_alerts = []
    all_audit = []

    for recipient_id in caregiver.get("care_recipient_ids", []):
        alerts = store.get_alerts(recipient_id)
        consent_matrix = store.get_consent_matrix(recipient_id)

        rendered, audit = filter_alerts_for_caregiver(
            alerts, caregiver_id, consent_matrix
        )
        all_alerts.extend(rendered)

        # Log audit entries
        for entry in audit:
            store.add_audit_entry({
                "audit_id": generate_id(),
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "event_type": "alert_filtered",
                "actor_id": "system",
                "care_recipient_id": recipient_id,
                "details": entry,
            })

    # Sort by generated_at descending
    all_alerts.sort(key=lambda a: a.get("generated_at", ""), reverse=True)

    return {"alerts": all_alerts, "total": len(all_alerts)}


@app.get("/api/alerts/{alert_id}/evidence")
def get_alert_evidence(alert_id: str, caregiver_id: str = Query(...)):
    """
    Get drill-down evidence for a specific alert, tier-filtered.
    """
    store = get_store()
    caregiver = store.get_caregiver(caregiver_id)
    if not caregiver:
        raise HTTPException(status_code=404, detail="Caregiver not found")

    # Find the raw alert
    for recipient_id in caregiver.get("care_recipient_ids", []):
        alerts = store.get_alerts(recipient_id)
        for alert in alerts:
            if alert.get("alert_id") == alert_id:
                consent_matrix = store.get_consent_matrix(recipient_id)
                from engine.consent_filter import filter_alert_for_caregiver
                rendered, audit = filter_alert_for_caregiver(
                    alert, caregiver_id, consent_matrix
                )
                if rendered:
                    return {"evidence": rendered}
                else:
                    raise HTTPException(status_code=403, detail="Not authorized to view this alert")

    raise HTTPException(status_code=404, detail="Alert not found")


# ---------------------------------------------------------------------------
# Access summary endpoint
# ---------------------------------------------------------------------------

@app.get("/api/access-summary")
def get_access_summary(caregiver_id: str = Query(...), care_recipient_id: str = Query(...)):
    """Get the access summary for a caregiver-recipient pair."""
    store = get_store()
    consent_matrix = store.get_consent_matrix(care_recipient_id)
    summary = get_caregiver_access_summary(
        caregiver_id, care_recipient_id, consent_matrix
    )
    return summary


# ---------------------------------------------------------------------------
# Consent endpoints
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
    """Update consent records for a care recipient."""
    store = get_store()
    updates = [u.dict() for u in request.updates]
    audit_entries = store.update_consent(
        care_recipient_id, updates, request.actor_id
    )
    return {"status": "updated", "audit_entries": audit_entries}


# ---------------------------------------------------------------------------
# Data status / freshness endpoints
# ---------------------------------------------------------------------------

@app.get("/api/data-status/{care_recipient_id}")
def get_data_status(care_recipient_id: str):
    """
    Get freshness/missing-data status per source for UI badges.
    Returns: fresh / stale / missing for each signal source.
    """
    store = get_store()
    recipient = store.get_care_recipient(care_recipient_id)
    if not recipient:
        raise HTTPException(status_code=404, detail="Care recipient not found")

    # Use dataset's base_time for evaluation
    metadata = store.get_metadata()
    base_time_str = metadata.get("base_time", None)
    if base_time_str:
        now = datetime.fromisoformat(base_time_str.replace("Z", ""))
    else:
        now = datetime.utcnow()

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
# Audit endpoint (admin only)
# ---------------------------------------------------------------------------

@app.get("/api/audit/{care_recipient_id}")
def get_audit_log(care_recipient_id: str):
    """Get the full audit trail for a care recipient (admin only)."""
    store = get_store()
    log = store.get_audit_log(care_recipient_id)
    return {"audit_log": log, "total": len(log)}


# ---------------------------------------------------------------------------
# Metrics / ground truth (for evaluation)
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


# ---------------------------------------------------------------------------
# Content linter check (for demo/testing)
# ---------------------------------------------------------------------------

@app.post("/api/lint-check")
def lint_check(text: str = Query(...)):
    """Check text against the content linter."""
    violations = lint_text(text)
    sanitized, _ = sanitize_alert_text(text)
    return {
        "original": text,
        "is_compliant": len(violations) == 0,
        "violations": [v.to_dict() for v in violations],
        "sanitized": sanitized,
    }
