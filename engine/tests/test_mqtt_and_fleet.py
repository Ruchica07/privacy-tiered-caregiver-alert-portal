"""
Test Suite: MQTT Ingestion Adapter & Multi-Resident Fleet View

Verifies:
1. MQTT topic parsing & signal mapping
2. MQTT message ingestion into data store
3. Multi-resident fleet coordinator overview aggregation
"""

import pytest
import json
from api.mqtt_adapter import MQTTIngestionAdapter, MQTTMessage
from api.data_store import get_store


class TestMQTTAndFleet:

    @pytest.fixture
    def mqtt_adapter(self):
        return MQTTIngestionAdapter()

    def test_mqtt_topic_parsing(self, mqtt_adapter):
        topic1 = "aegiscare/cr_001/sensor/door"
        r1, s1 = mqtt_adapter.parse_topic(topic1)
        assert r1 == "cr_001"
        assert s1 == "sensor"

        topic2 = "devices/cr_002/wearable/telemetry"
        r2, s2 = mqtt_adapter.parse_topic(topic2)
        assert r2 == "cr_002"
        assert s2 == "wearable"

    def test_mqtt_message_ingestion_pipeline(self, mqtt_adapter):
        msg = MQTTMessage(
            topic="aegiscare/cr_001/activity_score",
            payload=json.dumps({
                "value": 52.5,
                "metadata": {"source": "ble_wristband"},
            }),
            qos=1,
        )
        res = mqtt_adapter.handle_message(msg)

        assert res.success is True
        assert res.normalized_signal is not None
        assert res.normalized_signal["care_recipient_id"] == "cr_001"
        assert res.normalized_signal["signal_type"] == "activity_score"
        assert res.normalized_signal["value"] == 52.5

    def test_fleet_overview_logic(self):
        store = get_store()
        recipients = store.get_care_recipients()
        assert len(recipients) >= 3

        for r in recipients:
            assert "id" in r
            assert "name" in r
            assert "baseline_activity_mean" in r
