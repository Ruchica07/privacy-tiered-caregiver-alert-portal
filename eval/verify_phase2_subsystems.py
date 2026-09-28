import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.security import HTTPAuthorizationCredentials
from api.data_store import get_store
from api.auth import create_access_token, decode_access_token, verify_caregiver_access, get_current_user
from engine.ingestion import get_ingestion_pipeline
from api.mqtt_adapter import get_mqtt_adapter, MQTTMessage

def test_all():
    print("--- Starting Review 2 Independent Subsystem Verification ---")
    
    # 1. JWT & Anti-impersonation
    token = create_access_token({"sub": "cg_001", "username": "jane.smith", "role": "primary_caregiver"})
    payload = decode_access_token(token)
    assert payload["sub"] == "cg_001"
    assert payload["username"] == "jane.smith"
    
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    user = get_current_user(creds)
    assert user["caregiver_id"] == "cg_001"
    assert verify_caregiver_access("cg_001", current_user=user) == True
    
    impersonation_caught = False
    try:
        verify_caregiver_access("cg_002", current_user=user)
    except Exception as e:
        if "403" in str(e):
            impersonation_caught = True
    assert impersonation_caught, "Impersonation was not caught by RBAC!"
    print("1. JWT Server-Side RBAC & Anti-Impersonation: PASS")
    
    # 2. HMAC WebHook
    import hmac
    import hashlib
    pipeline = get_ingestion_pipeline()
    payload_bytes = b'{"event_id": "evt_test_01", "type": "heartbeat", "care_recipient_id": "cr_001"}'
    signature = "sha256=" + hmac.new(
        pipeline.webhook_secret.encode("utf-8"),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()
    
    assert pipeline.verify_signature(payload_bytes, signature) == True, "Valid signature failed"
    assert pipeline.verify_signature(payload_bytes + b"tampered", signature) == False, "Tampered payload accepted"
    assert pipeline.verify_signature(payload_bytes, "sha256=invalid_sig_hex_000") == False, "Invalid signature accepted"
    print("2. HMAC-SHA256 WebHook Auth & Tamper Rejection: PASS")
    
    # 3. MQTT Ingestion
    mqtt = get_mqtt_adapter()
    mqtt_msg = MQTTMessage(
        topic="aegiscare/cr_001/device_heartbeat",
        payload=json.dumps({"status": "ok", "battery_level": 98.5, "timestamp": "2026-09-28T10:00:00Z"})
    )
    res = mqtt.handle_message(mqtt_msg)
    assert res.success == True, f"MQTT ingestion failed: {res.validation_errors}"
    print("3. MQTT IoT Telemetry Ingestion Pipeline: PASS")
    
    # 4. Cryptographic SHA-256 Audit Chain & Tamper Detection
    store = get_store()
    audit_res = store.verify_audit_chain()
    assert audit_res["is_valid"] == True, f"Audit chain broken: {audit_res}"
    print(f"4. SHA-256 Audit Hash Chain Verification: PASS ({audit_res['total_records']} chained entries, 0 breaks)")
    
    print("--- All Subsystem Verifications Completed Successfully ---")

if __name__ == "__main__":
    test_all()
