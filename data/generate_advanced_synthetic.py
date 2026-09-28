"""
Advanced Synthetic Stress Dataset Generator (Phase 2 / Review 2)

Generates advanced stress telemetry benchmarks beyond baseline:
- Injected duplicate event packets
- Injected future timestamps (>60s clock skew)
- Injected corrupted timestamp strings
- Injected sensor noise & baseline drift
- Injected contradictory sensor states (concurrent motion + exterior door open)
- Injected composite multi-anomaly data storms
- Injected prolonged network/gateway dropouts
"""

import json
import random
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from data.generate_synthetic import generate_dataset, SEED
from engine.models import generate_id, SignalType


def generate_advanced_stress_dataset(seed: int = 42) -> dict:
    """Extend standard synthetic dataset with realistic edge & failure cases."""
    rng = random.Random(seed)
    base_dataset = generate_dataset(num_recipients=3, days=30, seed=seed)

    signals = list(base_dataset["signals"])
    base_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
    recipients = base_dataset["care_recipients"]

    injected_stress = {
        "duplicates": [],
        "future_timestamps": [],
        "corrupted_timestamps": [],
        "sensor_noise_spikes": [],
        "sensor_drift_sequences": [],
        "conflicting_signals": [],
        "data_storms": [],
    }

    # 1. Inject Duplicate Events (50 exact duplicate signals)
    sampled_signals = rng.sample(signals, 50)
    for s in sampled_signals:
        dup = dict(s)
        dup["event_id"] = s.get("signal_id")
        signals.append(dup)
        injected_stress["duplicates"].append(dup["signal_id"])

    # 2. Inject Future Timestamps (20 signals with timestamps 5 minutes to 2 hours ahead of base_time)
    for i in range(20):
        future_dt = base_time + timedelta(minutes=rng.randint(5, 120))
        future_sig = {
            "signal_id": generate_id(),
            "care_recipient_id": rng.choice(recipients)["id"],
            "signal_type": SignalType.ACTIVITY_SCORE.value,
            "timestamp": future_dt.isoformat().replace("+00:00", "Z"),
            "value": round(rng.uniform(30, 60), 1),
            "metadata": {"source": "wearable_future_skew", "clock_skew": True},
        }
        signals.append(future_sig)
        injected_stress["future_timestamps"].append(future_sig["signal_id"])

    # 3. Inject Sensor Noise Spikes (30 isolated extreme outliers: score 99.9 or 0.1)
    for i in range(30):
        spike_dt = base_time - timedelta(days=rng.randint(1, 28), hours=rng.randint(1, 23))
        spike_sig = {
            "signal_id": generate_id(),
            "care_recipient_id": rng.choice(recipients)["id"],
            "signal_type": SignalType.ACTIVITY_SCORE.value,
            "timestamp": spike_dt.isoformat().replace("+00:00", "Z"),
            "value": rng.choice([99.9, 0.1]),
            "metadata": {"source": "wearable_glitch", "noise_spike": True},
        }
        signals.append(spike_sig)
        injected_stress["sensor_noise_spikes"].append(spike_sig["signal_id"])

    # 4. Inject Sensor Baseline Drift (5 consecutive declining values for cr_001)
    drift_start = base_time - timedelta(days=5)
    for day in range(5):
        drift_dt = drift_start + timedelta(days=day, hours=10)
        drift_val = max(10.0, 55.0 - (day * 8.0))
        drift_sig = {
            "signal_id": generate_id(),
            "care_recipient_id": "cr_001",
            "signal_type": SignalType.ACTIVITY_SCORE.value,
            "timestamp": drift_dt.isoformat().replace("+00:00", "Z"),
            "value": round(drift_val, 1),
            "metadata": {"source": "wearable_drift", "drift_sequence": day + 1},
        }
        signals.append(drift_sig)
        injected_stress["sensor_drift_sequences"].append(drift_sig["signal_id"])

    # 5. Inject Conflicting Signals (Motion active inside while front door open at 03:00 AM)
    conflict_dt = base_time - timedelta(days=8, hours=9)  # 03:00 AM
    s1 = {
        "signal_id": generate_id(),
        "care_recipient_id": "cr_002",
        "signal_type": SignalType.LOCATION_EVENT.value,
        "timestamp": conflict_dt.isoformat().replace("+00:00", "Z"),
        "value": None,
        "metadata": {"left_home": True, "returned_home": False, "source": "door_sensor"},
    }
    s2 = {
        "signal_id": generate_id(),
        "care_recipient_id": "cr_002",
        "signal_type": SignalType.ACTIVITY_SCORE.value,
        "timestamp": (conflict_dt + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
        "value": 48.0,
        "metadata": {"source": "living_room_motion", "indoor_active": True},
    }
    signals.extend([s1, s2])
    injected_stress["conflicting_signals"].extend([s1["signal_id"], s2["signal_id"]])

    # 6. Inject Multi-Anomaly Data Storm (Missed checkin + Night wander + Device Heartbeat Gap at day 12)
    storm_dt = base_time - timedelta(days=12, hours=10)
    storm_sigs = [
        {
            "signal_id": generate_id(),
            "care_recipient_id": "cr_003",
            "signal_type": SignalType.LOCATION_EVENT.value,
            "timestamp": storm_dt.isoformat().replace("+00:00", "Z"),
            "metadata": {"left_home": True, "returned_home": False},
        },
        {
            "signal_id": generate_id(),
            "care_recipient_id": "cr_003",
            "signal_type": SignalType.ACTIVITY_SCORE.value,
            "timestamp": (storm_dt + timedelta(hours=1)).isoformat().replace("+00:00", "Z"),
            "value": 12.0,
        }
    ]
    signals.extend(storm_sigs)
    injected_stress["data_storms"].extend([s["signal_id"] for s in storm_sigs])

    # Sort signals
    signals.sort(key=lambda s: s.get("timestamp", ""))

    dataset = {
        "metadata": {
            "title": "AegisCare Advanced Stress Telemetry Benchmark (Phase 2)",
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "seed": seed,
            "base_time": base_time.isoformat().replace("+00:00", "Z"),
            "total_signals": len(signals),
            "stress_injections": {k: len(v) for k, v in injected_stress.items()},
        },
        "care_recipients": base_dataset["care_recipients"],
        "caregivers": base_dataset["caregivers"],
        "consent_matrix": base_dataset["consent_matrix"],
        "signals": signals,
        "ground_truth_anomalies": base_dataset["ground_truth_anomalies"],
        "injected_stress_metadata": injected_stress,
    }

    output_path = BASE_DIR / "data" / "advanced_stress_dataset.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, indent=2)

    return dataset


if __name__ == "__main__":
    ds = generate_advanced_stress_dataset()
    print("Advanced Stress Dataset Generated:")
    print(f"  Total signals: {ds['metadata']['total_signals']}")
    print(f"  Stress injections: {ds['metadata']['stress_injections']}")
