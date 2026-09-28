"""
Data Store — SQLite and SQLAlchemy ORM persistence layer.

Provides CRUD operations backed by SQLite relational database and SQLAlchemy models
for care recipients, caregivers, consent records, signals, alerts, and audit logs.
"""

import json
import os
import copy
from datetime import datetime
from typing import List, Optional, Dict, Any

from api.database import (
    init_db, SessionLocal,
    CareRecipientModel, CaregiverModel, ConsentRecordModel,
    SignalModel, AlertModel, AuditEntryModel
)
from engine.models import generate_id, compute_audit_hash, GENESIS_HASH


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
DATASET_PATH = os.path.join(DATA_DIR, "sample_dataset.json")


class DataStore:
    """Database-backed data store using SQLAlchemy ORM."""

    def __init__(self, dataset_path: str = DATASET_PATH):
        self.dataset_path = dataset_path
        self._ground_truth = []
        self._metadata = {}
        self.load()

    def load(self):
        """Ensure database schema is initialized and seeded."""
        init_db(self.dataset_path)
        if os.path.exists(self.dataset_path):
            try:
                with open(self.dataset_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._ground_truth = data.get("ground_truth_anomalies", [])
                    self._metadata = data.get("metadata", {})
            except Exception:
                pass

    # --- Care Recipients ---

    def get_care_recipients(self) -> List[dict]:
        session = SessionLocal()
        try:
            records = session.query(CareRecipientModel).all()
            return [r.to_dict() for r in records]
        finally:
            session.close()

    def get_care_recipient(self, recipient_id: str) -> Optional[dict]:
        session = SessionLocal()
        try:
            record = session.query(CareRecipientModel).filter(CareRecipientModel.id == recipient_id).first()
            return record.to_dict() if record else None
        finally:
            session.close()

    # --- Caregivers ---

    def get_caregivers(self) -> List[dict]:
        session = SessionLocal()
        try:
            records = session.query(CaregiverModel).all()
            return [c.to_dict() for c in records]
        finally:
            session.close()

    def get_caregiver(self, caregiver_id: str) -> Optional[dict]:
        session = SessionLocal()
        try:
            record = session.query(CaregiverModel).filter(CaregiverModel.id == caregiver_id).first()
            return record.to_dict() if record else None
        finally:
            session.close()

    def get_caregivers_for_recipient(self, recipient_id: str) -> List[dict]:
        all_caregivers = self.get_caregivers()
        return [c for c in all_caregivers if recipient_id in c.get("care_recipient_ids", [])]

    # --- Consent Matrix ---

    def get_consent_matrix(self, care_recipient_id: Optional[str] = None) -> List[dict]:
        session = SessionLocal()
        try:
            query = session.query(ConsentRecordModel)
            if care_recipient_id:
                query = query.filter(ConsentRecordModel.care_recipient_id == care_recipient_id)
            return [c.to_dict() for c in query.all()]
        finally:
            session.close()

    def get_consent_for_caregiver(self, caregiver_id: str, care_recipient_id: Optional[str] = None) -> List[dict]:
        matrix = self.get_consent_matrix(care_recipient_id)
        return [c for c in matrix if c.get("caregiver_id") == caregiver_id]

    def update_consent(self, care_recipient_id: str, updates: List[dict], actor_id: str = "admin") -> List[dict]:
        """
        Update consent records in SQLite via SQLAlchemy.
        """
        session = SessionLocal()
        audit_entries = []
        now_str = datetime.utcnow().isoformat() + "Z"

        try:
            for update in updates:
                caregiver_id = update["caregiver_id"]
                category = update["category"]

                existing = session.query(ConsentRecordModel).filter(
                    ConsentRecordModel.caregiver_id == caregiver_id,
                    ConsentRecordModel.category == category,
                    ConsentRecordModel.care_recipient_id == care_recipient_id
                ).first()

                if existing:
                    old_tier = existing.max_tier
                    old_status = existing.consent_status

                    existing.max_tier = update.get("max_tier", existing.max_tier)
                    existing.consent_status = update.get("consent_status", existing.consent_status)
                    existing.expires_at = update.get("expires_at", existing.expires_at)
                    if update.get("override_reason"):
                        existing.override_reason = update["override_reason"]
                    if update.get("consent_status") == "granted":
                        existing.granted_at = now_str

                    audit_entry = {
                        "audit_id": generate_id(),
                        "timestamp": now_str,
                        "event_type": "consent_change",
                        "actor_id": actor_id,
                        "care_recipient_id": care_recipient_id,
                        "details": {
                            "caregiver_id": caregiver_id,
                            "category": category,
                            "old_tier": old_tier,
                            "new_tier": existing.max_tier,
                            "old_status": old_status,
                            "new_status": existing.consent_status,
                        },
                    }
                else:
                    new_id = update.get("consent_id", generate_id())
                    new_record = ConsentRecordModel(
                        consent_id=new_id,
                        care_recipient_id=care_recipient_id,
                        caregiver_id=caregiver_id,
                        category=category,
                        max_tier=update.get("max_tier", 0),
                        consent_status=update.get("consent_status", "pending"),
                        granted_at=now_str if update.get("consent_status") == "granted" else None,
                        expires_at=update.get("expires_at"),
                        override_reason=update.get("override_reason"),
                    )
                    session.add(new_record)

                    audit_entry = {
                        "audit_id": generate_id(),
                        "timestamp": now_str,
                        "event_type": "consent_change",
                        "actor_id": actor_id,
                        "care_recipient_id": care_recipient_id,
                        "details": {
                            "caregiver_id": caregiver_id,
                            "category": category,
                            "old_tier": None,
                            "new_tier": update.get("max_tier", 0),
                            "old_status": None,
                            "new_status": update.get("consent_status", "pending"),
                        },
                    }

                last_entry = session.query(AuditEntryModel).order_by(AuditEntryModel.timestamp.desc(), AuditEntryModel.audit_id.desc()).first()
                prev_hash = last_entry.entry_hash if last_entry and last_entry.entry_hash else GENESIS_HASH

                entry_hash = compute_audit_hash(
                    audit_id=audit_entry["audit_id"],
                    timestamp=audit_entry["timestamp"],
                    event_type=audit_entry["event_type"],
                    actor_id=audit_entry["actor_id"],
                    care_recipient_id=audit_entry["care_recipient_id"],
                    details=audit_entry["details"],
                    prev_hash=prev_hash,
                )
                audit_entry["prev_hash"] = prev_hash
                audit_entry["entry_hash"] = entry_hash

                audit_entries.append(audit_entry)
                # Also save audit log to DB
                audit_obj = AuditEntryModel(
                    audit_id=audit_entry["audit_id"],
                    timestamp=audit_entry["timestamp"],
                    event_type=audit_entry["event_type"],
                    actor_id=audit_entry["actor_id"],
                    care_recipient_id=audit_entry["care_recipient_id"],
                    details_json=json.dumps(audit_entry["details"]),
                    prev_hash=prev_hash,
                    entry_hash=entry_hash,
                )
                session.add(audit_obj)
                session.flush()

            session.commit()
            return audit_entries
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- Signals ---

    def get_signals(self, care_recipient_id: Optional[str] = None,
                    signal_type: Optional[str] = None) -> List[dict]:
        session = SessionLocal()
        try:
            query = session.query(SignalModel)
            if care_recipient_id:
                query = query.filter(SignalModel.care_recipient_id == care_recipient_id)
            if signal_type:
                query = query.filter(SignalModel.signal_type == signal_type)
            return [s.to_dict() for s in query.all()]
        finally:
            session.close()

    def add_signal(self, signal: dict):
        session = SessionLocal()
        try:
            sig_id = signal.get("signal_id", generate_id())
            obj = SignalModel(
                signal_id=sig_id,
                care_recipient_id=signal["care_recipient_id"],
                signal_type=signal["signal_type"],
                timestamp=signal.get("timestamp", datetime.utcnow().isoformat() + "Z"),
                value=signal.get("value"),
                metadata_json=json.dumps(signal.get("metadata", {})),
            )
            session.add(obj)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # --- Alerts ---

    def get_alerts(self, care_recipient_id: Optional[str] = None) -> List[dict]:
        session = SessionLocal()
        try:
            query = session.query(AlertModel)
            if care_recipient_id:
                query = query.filter(AlertModel.care_recipient_id == care_recipient_id)
            alerts = [a.to_dict() for a in query.all()]
            return sorted(alerts, key=lambda a: a.get("generated_at", ""), reverse=True)
        finally:
            session.close()

    def add_alert(self, alert: dict):
        session = SessionLocal()
        try:
            obj = AlertModel(
                alert_id=alert.get("alert_id", generate_id()),
                care_recipient_id=alert["care_recipient_id"],
                alert_type=getattr(alert.get("alert_type"), "value", str(alert.get("alert_type", "generic"))),
                category=getattr(alert.get("category"), "value", str(alert.get("category", "general"))),
                severity=getattr(alert.get("severity"), "value", str(alert.get("severity", "medium"))),
                rule_fired=alert.get("rule_fired", ""),
                evidence_summary=alert.get("evidence_summary", ""),
                generated_at=alert.get("generated_at", datetime.utcnow().isoformat() + "Z"),
                requires_tier=alert.get("requires_tier", 1),
                is_data_gap=alert.get("is_data_gap", False),
                trend_info=alert.get("trend_info"),
                clinical_note=alert.get("clinical_note"),
                evidence_data_json=json.dumps(alert.get("evidence_data", {})),
                actionable_step=alert.get("actionable_step"),
            )
            session.add(obj)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def clear_alerts(self, care_recipient_id: Optional[str] = None):
        session = SessionLocal()
        try:
            query = session.query(AlertModel)
            if care_recipient_id:
                query = query.filter(AlertModel.care_recipient_id == care_recipient_id)
            query.delete(synchronize_session=False)
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def set_alerts(self, alerts: List[dict]):
        self.clear_alerts()
        for a in alerts:
            self.add_alert(a)

    # --- Audit Log ---

    def get_audit_log(self, care_recipient_id: Optional[str] = None) -> List[dict]:
        session = SessionLocal()
        try:
            query = session.query(AuditEntryModel)
            if care_recipient_id:
                query = query.filter(AuditEntryModel.care_recipient_id == care_recipient_id)
            log = [e.to_dict() for e in query.all()]
            return sorted(log, key=lambda e: e.get("timestamp", ""), reverse=True)
        finally:
            session.close()

    def add_audit_entry(self, entry: dict) -> dict:
        """Add a new audit entry with cryptographic hash chaining."""
        session = SessionLocal()
        try:
            audit_id = entry.get("audit_id", generate_id())
            timestamp = entry.get("timestamp", datetime.utcnow().isoformat() + "Z")
            event_type = entry.get("event_type", "audit_event")
            actor_id = entry.get("actor_id", "system")
            care_recipient_id = entry.get("care_recipient_id", "")
            details = entry.get("details", {})

            # Retrieve the latest entry to link the hash chain
            last_entry = session.query(AuditEntryModel).order_by(AuditEntryModel.timestamp.desc(), AuditEntryModel.audit_id.desc()).first()
            prev_hash = last_entry.entry_hash if last_entry and last_entry.entry_hash else GENESIS_HASH

            entry_hash = compute_audit_hash(
                audit_id=audit_id,
                timestamp=timestamp,
                event_type=event_type,
                actor_id=actor_id,
                care_recipient_id=care_recipient_id,
                details=details,
                prev_hash=prev_hash,
            )

            obj = AuditEntryModel(
                audit_id=audit_id,
                timestamp=timestamp,
                event_type=event_type,
                actor_id=actor_id,
                care_recipient_id=care_recipient_id,
                details_json=json.dumps(details),
                prev_hash=prev_hash,
                entry_hash=entry_hash,
            )
            session.add(obj)
            session.commit()
            return obj.to_dict()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def verify_audit_chain(self, care_recipient_id: Optional[str] = None) -> dict:
        """
        Cryptographically verify the integrity of the audit hash chain.
        Ensures prev_hash correctly references previous entry_hash and entry_hash matches data.
        """
        session = SessionLocal()
        try:
            query = session.query(AuditEntryModel)
            if care_recipient_id:
                query = query.filter(AuditEntryModel.care_recipient_id == care_recipient_id)
            entries = query.all()

            # Sort chronologically to verify forward hash chain
            sorted_entries = sorted(entries, key=lambda e: (e.timestamp, e.audit_id))

            if not sorted_entries:
                return {
                    "is_valid": True,
                    "total_records": 0,
                    "verified_at": datetime.utcnow().isoformat() + "Z",
                    "root_hash": GENESIS_HASH,
                    "tip_hash": GENESIS_HASH,
                    "status": "empty_chain",
                }

            prev_expected_hash = GENESIS_HASH
            for idx, entry in enumerate(sorted_entries):
                # Verify prev_hash matches
                if idx == 0 and not entry.prev_hash:
                    pass  # Genesis record
                elif entry.prev_hash != prev_expected_hash:
                    return {
                        "is_valid": False,
                        "tampered_index": idx,
                        "tampered_audit_id": entry.audit_id,
                        "reason": f"Broken hash chain link: prev_hash ({entry.prev_hash[:16]}...) does not match expected ({prev_expected_hash[:16]}...)",
                        "verified_at": datetime.utcnow().isoformat() + "Z",
                    }

                # Verify entry_hash recomputation
                try:
                    det = json.loads(entry.details_json)
                except Exception:
                    det = {}

                computed = compute_audit_hash(
                    audit_id=entry.audit_id,
                    timestamp=entry.timestamp,
                    event_type=entry.event_type,
                    actor_id=entry.actor_id,
                    care_recipient_id=entry.care_recipient_id,
                    details=det,
                    prev_hash=entry.prev_hash,
                )

                if entry.entry_hash != computed:
                    return {
                        "is_valid": False,
                        "tampered_index": idx,
                        "tampered_audit_id": entry.audit_id,
                        "reason": f"Data tampering detected: entry_hash ({entry.entry_hash[:16]}...) does not match computed hash ({computed[:16]}...)",
                        "verified_at": datetime.utcnow().isoformat() + "Z",
                    }

                prev_expected_hash = entry.entry_hash

            return {
                "is_valid": True,
                "total_records": len(sorted_entries),
                "verified_at": datetime.utcnow().isoformat() + "Z",
                "root_hash": sorted_entries[0].prev_hash,
                "tip_hash": sorted_entries[-1].entry_hash,
                "status": "valid_tamper_evident",
            }
        finally:
            session.close()

    # --- Ground Truth ---

    def get_ground_truth(self) -> List[dict]:
        return self._ground_truth

    # --- Metadata ---

    def get_metadata(self) -> dict:
        return self._metadata


# Singleton instance
_store: Optional[DataStore] = None


def get_store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore()
    return _store
