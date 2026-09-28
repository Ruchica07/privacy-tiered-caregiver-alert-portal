"""
MQTT IoT Sensor & Gateway Ingestion Adapter

Simulates an MQTT broker client/subscriber that ingests telemetry streams from:
- Smart-home door contact sensors (MQTT topic: `aegiscare/{recipient_id}/sensor/door`)
- BLE wearable activity trackers (MQTT topic: `aegiscare/{recipient_id}/wearable/activity`)
- Medication dispenser hubs (MQTT topic: `aegiscare/{recipient_id}/dispenser/event`)
- Ambient wellness hubs (MQTT topic: `aegiscare/{recipient_id}/hub/heartbeat`)

Routes messages through the `IngestionPipeline` (deduplication, timestamp validation,
normalization) and persists valid signals with audit logging.
"""

import json
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Callable, List, Tuple
from dataclasses import dataclass, field

from engine.ingestion import get_ingestion_pipeline, IngestionResult
from api.data_store import get_store
from engine.models import generate_id


@dataclass
class MQTTMessage:
    topic: str
    payload: str
    qos: int = 1
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))


class MQTTIngestionAdapter:
    """
    Subscribes to MQTT topics and processes incoming IoT sensor telemetry payloads.
    """

    def __init__(self):
        self.pipeline = get_ingestion_pipeline()
        self.message_history: List[MQTTMessage] = []

    def parse_topic(self, topic: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract recipient_id and device/sensor type from MQTT topic.
        Supported patterns:
        - aegiscare/{recipient_id}/{sensor_type}
        - devices/{recipient_id}/{sensor_type}/telemetry
        """
        parts = topic.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "aegiscare":
            return parts[1], parts[2]
        elif len(parts) >= 3 and parts[0] == "devices":
            return parts[1], parts[2]
        return None, None

    def handle_message(self, message: MQTTMessage) -> IngestionResult:
        """Process an incoming MQTT message from an IoT gateway or wearable."""
        self.message_history.append(message)
        recipient_id_topic, sensor_type_topic = self.parse_topic(message.topic)

        try:
            payload_data = json.loads(message.payload) if isinstance(message.payload, str) else dict(message.payload)
        except Exception:
            # Handle plain text payloads (e.g. "OPEN", "HEARTBEAT_OK", "35.5")
            payload_data = {
                "raw_text": message.payload,
            }

        # Inject topic context if not in payload
        if recipient_id_topic and "care_recipient_id" not in payload_data and "recipient_id" not in payload_data:
            payload_data["care_recipient_id"] = recipient_id_topic
        if sensor_type_topic and "signal_type" not in payload_data and "type" not in payload_data:
            payload_data["signal_type"] = sensor_type_topic

        # Process through pipeline
        res = self.pipeline.process_incoming_event(payload_data)

        if res.success and not res.is_duplicate and res.normalized_signal:
            store = get_store()
            store.add_signal(res.normalized_signal)
            # Record audit
            store.add_audit_entry({
                "audit_id": generate_id(),
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "event_type": "mqtt_ingested",
                "actor_id": f"mqtt_client:{message.topic}",
                "care_recipient_id": res.normalized_signal["care_recipient_id"],
                "details": {
                    "topic": message.topic,
                    "signal_id": res.signal_id,
                    "signal_type": res.normalized_signal["signal_type"],
                    "qos": message.qos,
                },
            })

        return res


# Global singleton instance
_mqtt_adapter = MQTTIngestionAdapter()

def get_mqtt_adapter() -> MQTTIngestionAdapter:
    return _mqtt_adapter
