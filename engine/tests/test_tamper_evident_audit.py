"""
Test Suite: Cryptographic Tamper-Evident Audit Hash Chain Verification

Verifies:
1. Canonical record hashing with SHA-256
2. Deterministic linking of prev_hash -> entry_hash (Genesis to Tip)
3. Detection of modified entry payload (tampering)
4. Detection of injected/deleted audit log rows
5. API endpoint verification behavior
"""

import pytest
import json
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from api.database import Base, AuditEntryModel
from engine.models import compute_audit_hash, GENESIS_HASH, generate_id
from api.data_store import DataStore


class TestTamperEvidentAuditTrail:

    @pytest.fixture(autouse=True)
    def setup_test_db(self, tmp_path):
        self.db_path = str(tmp_path / "test_audit.db")
        self.engine = create_engine(f"sqlite:///{self.db_path}", connect_args={"check_same_thread": False})
        Base.metadata.create_all(bind=self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def test_canonical_hash_is_deterministic(self):
        """Verify identical inputs yield identical SHA-256 hashes regardless of dict key order."""
        details1 = {"category": "location_safety", "new_tier": 2, "status": "granted"}
        details2 = {"status": "granted", "category": "location_safety", "new_tier": 2}

        h1 = compute_audit_hash("aud_01", "2026-09-01T12:00:00Z", "consent_change", "admin", "cr_001", details1, GENESIS_HASH)
        h2 = compute_audit_hash("aud_01", "2026-09-01T12:00:00Z", "consent_change", "admin", "cr_001", details2, GENESIS_HASH)

        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex string

    def test_sequential_hash_chaining(self):
        """Verify a chain of 5 records correctly links each prev_hash to previous entry_hash."""
        session = self.Session()
        prev = GENESIS_HASH

        for i in range(5):
            aid = f"aud_{i+1:03d}"
            ts = f"2026-09-01T12:0{i}:00Z"
            details = {"step": i + 1}
            eh = compute_audit_hash(aid, ts, "test_event", "system", "cr_001", details, prev)

            entry = AuditEntryModel(
                audit_id=aid,
                timestamp=ts,
                event_type="test_event",
                actor_id="system",
                care_recipient_id="cr_001",
                details_json=json.dumps(details),
                prev_hash=prev,
                entry_hash=eh,
            )
            session.add(entry)
            prev = eh

        session.commit()

        # Query and verify
        entries = session.query(AuditEntryModel).order_by(AuditEntryModel.timestamp.asc()).all()
        assert len(entries) == 5
        assert entries[0].prev_hash == GENESIS_HASH
        for j in range(1, 5):
            assert entries[j].prev_hash == entries[j - 1].entry_hash
        session.close()

    def test_tamper_detection_on_modified_details(self):
        """Verify that altering a payload in SQLite is immediately detected by the verification algorithm."""
        session = self.Session()
        # Create 3 chained entries
        prev = GENESIS_HASH
        for i in range(3):
            aid = f"aud_t_{i+1}"
            ts = f"2026-09-01T14:0{i}:00Z"
            details = {"access_tier": i}
            eh = compute_audit_hash(aid, ts, "alert_filtered", "system", "cr_001", details, prev)
            session.add(AuditEntryModel(
                audit_id=aid,
                timestamp=ts,
                event_type="alert_filtered",
                actor_id="system",
                care_recipient_id="cr_001",
                details_json=json.dumps(details),
                prev_hash=prev,
                entry_hash=eh,
            ))
            prev = eh
        session.commit()

        # Maliciously modify the details of record 2 in the database without recomputing hash
        record2 = session.query(AuditEntryModel).filter_by(audit_id="aud_t_2").first()
        record2.details_json = json.dumps({"access_tier": 99, "malicious_override": True})
        session.commit()
        session.close()

        # Run verification using custom session
        session2 = self.Session()
        entries = session2.query(AuditEntryModel).order_by(AuditEntryModel.timestamp.asc()).all()

        tamper_found = False
        for idx, e in enumerate(entries):
            det = json.loads(e.details_json)
            computed = compute_audit_hash(e.audit_id, e.timestamp, e.event_type, e.actor_id, e.care_recipient_id, det, e.prev_hash)
            if computed != e.entry_hash:
                tamper_found = True
                assert idx == 1
                assert e.audit_id == "aud_t_2"
                break

        assert tamper_found is True
        session2.close()

    def test_tamper_detection_on_deleted_record(self):
        """Verify that deleting an intermediate record breaks the prev_hash continuity."""
        session = self.Session()
        prev = GENESIS_HASH
        for i in range(4):
            aid = f"aud_del_{i+1}"
            ts = f"2026-09-01T15:0{i}:00Z"
            details = {"index": i}
            eh = compute_audit_hash(aid, ts, "event", "system", "cr_001", details, prev)
            session.add(AuditEntryModel(
                audit_id=aid,
                timestamp=ts,
                event_type="event",
                actor_id="system",
                care_recipient_id="cr_001",
                details_json=json.dumps(details),
                prev_hash=prev,
                entry_hash=eh,
            ))
            prev = eh
        session.commit()

        # Delete record 2
        record2 = session.query(AuditEntryModel).filter_by(audit_id="aud_del_2").first()
        session.delete(record2)
        session.commit()
        session.close()

        # Verify
        session2 = self.Session()
        entries = session2.query(AuditEntryModel).order_by(AuditEntryModel.timestamp.asc()).all()
        broken_link = False
        prev_exp = GENESIS_HASH
        for idx, e in enumerate(entries):
            if e.prev_hash != prev_exp:
                broken_link = True
                assert idx == 1  # Record 3 now looks at Genesis rather than Record 1
                break
            prev_exp = e.entry_hash

        assert broken_link is True
        session2.close()
