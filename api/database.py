"""
Database Module — SQLite & SQLAlchemy ORM for the Caregiver Alert Portal.

Defines SQLAlchemy ORM models and manages database sessions and migrations
from synthetic dataset seeds.
"""

import os
import json
from datetime import datetime
from typing import List, Optional, Dict, Any

from sqlalchemy import (
    create_engine, Column, String, Float, Integer, Boolean, Text, DateTime, ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, Session

# Base directory for the database file
DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "portal.db")
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


# ---------------------------------------------------------------------------
# SQLAlchemy ORM Models
# ---------------------------------------------------------------------------

class CareRecipientModel(Base):
    __tablename__ = "care_recipients"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    baseline_activity_mean = Column(Float, default=50.0)
    baseline_activity_stddev = Column(Float, default=10.0)
    expected_checkin_window_hours = Column(Float, default=4.0)
    expected_medication_window_hours = Column(Float, default=12.0)
    night_hours_start = Column(Integer, default=22)
    night_hours_end = Column(Integer, default=6)
    social_contact_expected_days = Column(Integer, default=3)
    device_heartbeat_expected_hours = Column(Float, default=2.0)

    def to_dict(self) -> dict:
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


class CaregiverModel(Base):
    __tablename__ = "caregivers"

    id = Column(String(64), primary_key=True, index=True)
    name = Column(String(128), nullable=False)
    role = Column(String(64), nullable=False)
    care_recipient_ids_json = Column(Text, default="[]")

    def to_dict(self) -> dict:
        try:
            r_ids = json.loads(self.care_recipient_ids_json)
        except Exception:
            r_ids = []
        return {
            "id": self.id,
            "name": self.name,
            "role": self.role,
            "care_recipient_ids": r_ids,
        }


class ConsentRecordModel(Base):
    __tablename__ = "consent_records"

    consent_id = Column(String(64), primary_key=True, index=True)
    care_recipient_id = Column(String(64), index=True, nullable=False)
    caregiver_id = Column(String(64), index=True, nullable=False)
    category = Column(String(64), nullable=False)
    max_tier = Column(Integer, default=0)
    consent_status = Column(String(32), default="pending")
    granted_at = Column(String(64), nullable=True)
    expires_at = Column(String(64), nullable=True)
    override_reason = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "consent_id": self.consent_id,
            "care_recipient_id": self.care_recipient_id,
            "caregiver_id": self.caregiver_id,
            "category": self.category,
            "max_tier": self.max_tier,
            "consent_status": self.consent_status,
            "granted_at": self.granted_at,
            "expires_at": self.expires_at,
            "override_reason": self.override_reason,
        }


class SignalModel(Base):
    __tablename__ = "signals"

    signal_id = Column(String(64), primary_key=True, index=True)
    care_recipient_id = Column(String(64), index=True, nullable=False)
    signal_type = Column(String(64), index=True, nullable=False)
    timestamp = Column(String(64), index=True, nullable=False)
    value = Column(Float, nullable=True)
    metadata_json = Column(Text, default="{}")

    def to_dict(self) -> dict:
        try:
            meta = json.loads(self.metadata_json)
        except Exception:
            meta = {}
        return {
            "signal_id": self.signal_id,
            "care_recipient_id": self.care_recipient_id,
            "signal_type": self.signal_type,
            "timestamp": self.timestamp,
            "value": self.value,
            "metadata": meta,
        }


class AlertModel(Base):
    __tablename__ = "alerts"

    alert_id = Column(String(64), primary_key=True, index=True)
    care_recipient_id = Column(String(64), index=True, nullable=False)
    alert_type = Column(String(64), nullable=False)
    category = Column(String(64), nullable=False)
    severity = Column(String(32), nullable=False)
    rule_fired = Column(String(128), nullable=False)
    evidence_summary = Column(Text, nullable=False)
    generated_at = Column(String(64), index=True, nullable=False)
    requires_tier = Column(Integer, default=1)
    is_data_gap = Column(Boolean, default=False)
    trend_info = Column(Text, nullable=True)
    clinical_note = Column(Text, nullable=True)
    evidence_data_json = Column(Text, default="{}")
    actionable_step = Column(Text, nullable=True)

    def to_dict(self) -> dict:
        try:
            ev_data = json.loads(self.evidence_data_json)
        except Exception:
            ev_data = {}
        return {
            "alert_id": self.alert_id,
            "care_recipient_id": self.care_recipient_id,
            "alert_type": self.alert_type,
            "category": self.category,
            "severity": self.severity,
            "rule_fired": self.rule_fired,
            "evidence_summary": self.evidence_summary,
            "generated_at": self.generated_at,
            "requires_tier": self.requires_tier,
            "is_data_gap": self.is_data_gap,
            "trend_info": self.trend_info,
            "clinical_note": self.clinical_note,
            "evidence_data": ev_data,
            "actionable_step": self.actionable_step,
        }


class AuditEntryModel(Base):
    __tablename__ = "audit_log"

    audit_id = Column(String(64), primary_key=True, index=True)
    timestamp = Column(String(64), index=True, nullable=False)
    event_type = Column(String(64), index=True, nullable=False)
    actor_id = Column(String(64), nullable=False)
    care_recipient_id = Column(String(64), index=True, nullable=False)
    details_json = Column(Text, default="{}")

    def to_dict(self) -> dict:
        try:
            det = json.loads(self.details_json)
        except Exception:
            det = {}
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "actor_id": self.actor_id,
            "care_recipient_id": self.care_recipient_id,
            "details": det,
        }


# ---------------------------------------------------------------------------
# Database Initialization & Seeding
# ---------------------------------------------------------------------------

def init_db(dataset_path: Optional[str] = None):
    """
    Creates SQLite tables and seeds them from dataset JSON if empty.
    """
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        # Check if care recipients already seeded
        recipient_count = session.query(CareRecipientModel).count()
        if recipient_count == 0:
            if not dataset_path:
                dataset_path = os.path.join(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "data",
                    "sample_dataset.json",
                )

            if os.path.exists(dataset_path):
                with open(dataset_path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                # 1. Care Recipients
                for r in data.get("care_recipients", []):
                    obj = CareRecipientModel(
                        id=r["id"],
                        name=r["name"],
                        baseline_activity_mean=r.get("baseline_activity_mean", 50.0),
                        baseline_activity_stddev=r.get("baseline_activity_stddev", 10.0),
                        expected_checkin_window_hours=r.get("expected_checkin_window_hours", 4.0),
                        expected_medication_window_hours=r.get("expected_medication_window_hours", 12.0),
                        night_hours_start=r.get("night_hours_start", 22),
                        night_hours_end=r.get("night_hours_end", 6),
                        social_contact_expected_days=r.get("social_contact_expected_days", 3),
                        device_heartbeat_expected_hours=r.get("device_heartbeat_expected_hours", 2.0),
                    )
                    session.add(obj)

                # 2. Caregivers
                for c in data.get("caregivers", []):
                    obj = CaregiverModel(
                        id=c["id"],
                        name=c["name"],
                        role=c["role"],
                        care_recipient_ids_json=json.dumps(c.get("care_recipient_ids", [])),
                    )
                    session.add(obj)

                # 3. Consent Records
                for cr in data.get("consent_matrix", []):
                    obj = ConsentRecordModel(
                        consent_id=cr["consent_id"],
                        care_recipient_id=cr["care_recipient_id"],
                        caregiver_id=cr["caregiver_id"],
                        category=cr["category"],
                        max_tier=cr.get("max_tier", 0),
                        consent_status=cr.get("consent_status", "pending"),
                        granted_at=cr.get("granted_at"),
                        expires_at=cr.get("expires_at"),
                        override_reason=cr.get("override_reason"),
                    )
                    session.add(obj)

                # 4. Signals
                for s in data.get("signals", []):
                    obj = SignalModel(
                        signal_id=s["signal_id"],
                        care_recipient_id=s["care_recipient_id"],
                        signal_type=s["signal_type"],
                        timestamp=s["timestamp"],
                        value=s.get("value"),
                        metadata_json=json.dumps(s.get("metadata", {})),
                    )
                    session.add(obj)

                # 5. Audit Log
                for a in data.get("audit_log", []):
                    obj = AuditEntryModel(
                        audit_id=a["audit_id"],
                        timestamp=a["timestamp"],
                        event_type=a["event_type"],
                        actor_id=a["actor_id"],
                        care_recipient_id=a["care_recipient_id"],
                        details_json=json.dumps(a.get("details", {})),
                    )
                    session.add(obj)

                session.commit()
    finally:
        session.close()


def get_db():
    """Dependency helper to yield database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
