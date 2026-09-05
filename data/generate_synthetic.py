"""
Synthetic Dataset Generator

Produces reproducible synthetic data for the Privacy-Tiered Caregiver Alert Portal:
- N care recipients with randomized baselines
- M caregivers per recipient with randomized roles + consent matrices
- 30-day time series with injected anomalies at known ground-truth points

Usage:
    python generate_synthetic.py           # Generate and save to sample_dataset.json
    python generate_synthetic.py --days 60 # Generate 60 days of data
"""

import json
import random
import argparse
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Add parent dir to path so we can import engine
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engine.models import (
    CaregiverRole, InformationCategory, ConsentStatus,
    SignalType, DEFAULT_TIERS, generate_id,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEED = 42
NUM_RECIPIENTS = 3
CAREGIVERS_PER_RECIPIENT = 4
DAYS = 30

CAREGIVER_NAMES = [
    ("Jane Smith", CaregiverRole.PRIMARY_CAREGIVER),
    ("Bob Smith", CaregiverRole.SECONDARY_CAREGIVER),
    ("Maria Garcia", CaregiverRole.NEIGHBOR_COMMUNITY),
    ("Dr. Sarah Chen", CaregiverRole.CARE_COORDINATOR_PROFESSIONAL),
    ("Tom Wilson", CaregiverRole.PRIMARY_CAREGIVER),
    ("Lisa Park", CaregiverRole.SECONDARY_CAREGIVER),
    ("James Brown", CaregiverRole.NEIGHBOR_COMMUNITY),
    ("Dr. Anil Patel", CaregiverRole.CARE_COORDINATOR_PROFESSIONAL),
    ("Karen Davis", CaregiverRole.PRIMARY_CAREGIVER),
    ("Mike Johnson", CaregiverRole.SECONDARY_CAREGIVER),
    ("Rosa Martinez", CaregiverRole.NEIGHBOR_COMMUNITY),
    ("Dr. Emily Wong", CaregiverRole.CARE_COORDINATOR_PROFESSIONAL),
]

RECIPIENT_NAMES = [
    "Dorothy Thompson",
    "Harold Mitchell",
    "Margaret Williams",
]


# ---------------------------------------------------------------------------
# Generator functions
# ---------------------------------------------------------------------------

def generate_care_recipients(n: int, rng: random.Random) -> List[dict]:
    """Generate N synthetic care recipients with randomized baselines."""
    recipients = []
    for i in range(n):
        name = RECIPIENT_NAMES[i] if i < len(RECIPIENT_NAMES) else f"Recipient {i+1}"
        recipients.append({
            "id": f"cr_{i+1:03d}",
            "name": name,
            "baseline_activity_mean": round(rng.uniform(35, 70), 1),
            "baseline_activity_stddev": round(rng.uniform(5, 15), 1),
            "expected_checkin_window_hours": rng.choice([3.0, 4.0, 6.0]),
            "expected_medication_window_hours": rng.choice([8.0, 12.0, 24.0]),
            "night_hours_start": rng.choice([21, 22, 23]),
            "night_hours_end": rng.choice([5, 6, 7]),
            "social_contact_expected_days": rng.choice([2, 3, 4]),
            "device_heartbeat_expected_hours": rng.choice([1.0, 2.0, 3.0]),
        })
    return recipients


def generate_caregivers(recipients: List[dict], per_recipient: int, rng: random.Random) -> List[dict]:
    """Generate caregivers for each recipient with assigned roles."""
    caregivers = []
    name_idx = 0
    for r_idx, recipient in enumerate(recipients):
        for c_idx in range(per_recipient):
            if name_idx < len(CAREGIVER_NAMES):
                name, role = CAREGIVER_NAMES[name_idx]
            else:
                role = rng.choice(list(CaregiverRole))
                name = f"Caregiver {name_idx + 1}"

            caregivers.append({
                "id": f"cg_{name_idx + 1:03d}",
                "name": name,
                "role": role.value,
                "care_recipient_ids": [recipient["id"]],
            })
            name_idx += 1
    return caregivers


def generate_consent_matrix(
    recipients: List[dict],
    caregivers: List[dict],
    rng: random.Random,
    base_time: datetime,
) -> List[dict]:
    """
    Generate consent matrices with intentional edge cases:
    - Some expired consents
    - Some pending consents
    - Some partial category grants
    - Some revoked consents
    """
    consent_records = []
    categories = list(InformationCategory)

    for caregiver in caregivers:
        role = CaregiverRole(caregiver["role"])
        default_tier = DEFAULT_TIERS[role]

        for recipient_id in caregiver["care_recipient_ids"]:
            for cat in categories:
                # Determine consent status with some edge cases
                roll = rng.random()

                if roll < 0.05:
                    # 5% chance of expired consent
                    status = ConsentStatus.GRANTED.value
                    expires = (base_time - timedelta(days=rng.randint(1, 10))).isoformat() + "Z"
                    max_tier = default_tier
                elif roll < 0.08:
                    # 3% chance of pending consent
                    status = ConsentStatus.PENDING.value
                    expires = None
                    max_tier = default_tier
                elif roll < 0.12:
                    # 4% chance of revoked consent
                    status = ConsentStatus.REVOKED.value
                    expires = None
                    max_tier = default_tier
                elif roll < 0.25:
                    # 13% chance of lower-than-default tier
                    status = ConsentStatus.GRANTED.value
                    expires = None
                    max_tier = max(0, default_tier - rng.randint(1, 2))
                else:
                    # Normal: granted at default tier
                    status = ConsentStatus.GRANTED.value
                    expires = None
                    max_tier = default_tier

                # Diagnosis category is always highest sensitivity
                if cat == InformationCategory.DIAGNOSIS_CONDITIONS:
                    if role != CaregiverRole.CARE_COORDINATOR_PROFESSIONAL:
                        max_tier = 0  # Non-professionals can't see diagnosis info
                        if rng.random() < 0.5:
                            status = ConsentStatus.REVOKED.value

                override_reason = None
                if rng.random() < 0.05:
                    override_reason = rng.choice([
                        "Dr. approved sharing vitals summary with daughter",
                        "Family meeting decision",
                        "Care recipient explicitly requested",
                    ])

                consent_records.append({
                    "consent_id": generate_id(),
                    "care_recipient_id": recipient_id,
                    "caregiver_id": caregiver["id"],
                    "category": cat.value,
                    "max_tier": max_tier,
                    "consent_status": status,
                    "granted_at": (base_time - timedelta(days=rng.randint(30, 90))).isoformat() + "Z",
                    "expires_at": expires,
                    "override_reason": override_reason,
                })

    return consent_records


def generate_signals(
    recipients: List[dict],
    days: int,
    rng: random.Random,
    base_time: datetime,
) -> tuple:
    """
    Generate a time series of synthetic signals with injected anomalies.
    Returns (signals, ground_truth_anomalies).
    """
    signals = []
    ground_truth = []
    start_time = base_time - timedelta(days=days)

    for recipient in recipients:
        rid = recipient["id"]
        checkin_window = recipient["expected_checkin_window_hours"]
        med_window = recipient["expected_medication_window_hours"]
        activity_mean = recipient["baseline_activity_mean"]
        activity_std = recipient["baseline_activity_stddev"]
        heartbeat_hours = recipient["device_heartbeat_expected_hours"]
        social_days = recipient["social_contact_expected_days"]

        # --- Generate normal signals across the time range ---
        current = start_time

        while current < base_time:
            hour = current.hour
            day_offset = (current - start_time).days

            # Check-ins (roughly every checkin_window hours during waking hours)
            if 7 <= hour <= 22 and hour % int(checkin_window) == 0:
                # Add some natural variance
                jitter = timedelta(minutes=rng.randint(-30, 30))
                ts = current + jitter

                signals.append({
                    "signal_id": generate_id(),
                    "care_recipient_id": rid,
                    "signal_type": "check_in",
                    "timestamp": ts.isoformat() + "Z",
                    "value": None,
                    "metadata": {"source": "check_in_app"},
                })

            # Activity scores (2-3 per day during waking hours)
            if hour in [9, 14, 19]:
                score = max(0, min(100, rng.gauss(activity_mean, activity_std)))
                signals.append({
                    "signal_id": generate_id(),
                    "care_recipient_id": rid,
                    "signal_type": "activity_score",
                    "timestamp": current.isoformat() + "Z",
                    "value": round(score, 1),
                    "metadata": {"source": "wearable"},
                })

            # Medication events (1-2 per day)
            if hour in [8, 20]:
                signals.append({
                    "signal_id": generate_id(),
                    "care_recipient_id": rid,
                    "signal_type": "medication_event",
                    "timestamp": current.isoformat() + "Z",
                    "value": None,
                    "metadata": {"source": "medication_dispenser", "completed": True},
                })

            # Device heartbeats (every heartbeat_hours)
            if hour % max(1, int(heartbeat_hours)) == 0:
                signals.append({
                    "signal_id": generate_id(),
                    "care_recipient_id": rid,
                    "signal_type": "device_heartbeat",
                    "timestamp": current.isoformat() + "Z",
                    "value": None,
                    "metadata": {"source": "wearable", "battery": rng.randint(20, 100)},
                })

            # Social contacts (roughly every social_days days)
            if hour == 15 and day_offset % social_days == 0:
                contact_type = rng.choice(["phone_call", "visit", "video_call"])
                signals.append({
                    "signal_id": generate_id(),
                    "care_recipient_id": rid,
                    "signal_type": "social_contact",
                    "timestamp": current.isoformat() + "Z",
                    "value": None,
                    "metadata": {"contact_type": contact_type},
                })

            # Vitals readings (2 per day)
            if hour in [8, 20]:
                flagged = rng.random() < 0.05  # 5% chance flagged normally
                signals.append({
                    "signal_id": generate_id(),
                    "care_recipient_id": rid,
                    "signal_type": "vitals_reading",
                    "timestamp": current.isoformat() + "Z",
                    "value": None,  # No raw values — by design
                    "metadata": {
                        "source": "health_monitor",
                        "flagged": flagged,
                        "qualitative": "within_normal_range" if not flagged else "outside_expected_range",
                    },
                })

            current += timedelta(hours=1)

        # --- Inject anomalies at known ground-truth points ---

        # Anomaly 1: Missed check-ins (day 20-21)
        anomaly_start = start_time + timedelta(days=20)
        anomaly_end = anomaly_start + timedelta(days=2)
        signals = [
            s for s in signals
            if not (
                s["care_recipient_id"] == rid
                and s["signal_type"] == "check_in"
                and anomaly_start.isoformat() <= s["timestamp"] <= anomaly_end.isoformat() + "Z"
            )
        ]
        ground_truth.append({
            "type": "missed_checkin",
            "care_recipient_id": rid,
            "start": anomaly_start.isoformat() + "Z",
            "end": anomaly_end.isoformat() + "Z",
            "category": "activity_engagement",
            "description": "Check-ins removed for day 20-21",
        })

        # Anomaly 2: Low activity scores (day 15-18)
        anomaly_start = start_time + timedelta(days=15)
        for s in signals:
            if (s["care_recipient_id"] == rid
                    and s["signal_type"] == "activity_score"
                    and anomaly_start.isoformat() <= s["timestamp"]):
                ts = datetime.fromisoformat(s["timestamp"].replace("Z", ""))
                if (ts - anomaly_start).days < 4:
                    # Drop activity to well below baseline
                    s["value"] = round(max(0, activity_mean - 3 * activity_std + rng.gauss(0, 2)), 1)

        ground_truth.append({
            "type": "activity_deviation",
            "care_recipient_id": rid,
            "start": anomaly_start.isoformat() + "Z",
            "end": (anomaly_start + timedelta(days=4)).isoformat() + "Z",
            "category": "activity_engagement",
            "description": "Activity scores dropped well below baseline for 4 days",
        })

        # Anomaly 3: Night wandering event (day 22)
        wander_time = start_time + timedelta(days=22, hours=23, minutes=15)
        signals.append({
            "signal_id": generate_id(),
            "care_recipient_id": rid,
            "signal_type": "location_event",
            "timestamp": wander_time.isoformat() + "Z",
            "value": None,
            "metadata": {"left_home": True, "returned_home": False, "source": "smart_home"},
        })
        ground_truth.append({
            "type": "night_wandering",
            "care_recipient_id": rid,
            "start": wander_time.isoformat() + "Z",
            "end": (wander_time + timedelta(hours=2)).isoformat() + "Z",
            "category": "location_safety",
            "description": "Left home at 11:15 PM, no return within 2 hours",
        })

        # Anomaly 4: Social isolation (no contacts for days 24-30)
        signals = [
            s for s in signals
            if not (
                s["care_recipient_id"] == rid
                and s["signal_type"] == "social_contact"
                and s["timestamp"] >= (start_time + timedelta(days=24)).isoformat()
            )
        ]
        ground_truth.append({
            "type": "social_isolation",
            "care_recipient_id": rid,
            "start": (start_time + timedelta(days=24)).isoformat() + "Z",
            "end": base_time.isoformat() + "Z",
            "category": "social_isolation_signal",
            "description": "All social contacts removed from day 24 onward",
        })

        # Anomaly 5: Device offline (day 25-26, no heartbeats)
        offline_start = start_time + timedelta(days=25)
        offline_end = offline_start + timedelta(days=2)
        signals = [
            s for s in signals
            if not (
                s["care_recipient_id"] == rid
                and s["signal_type"] == "device_heartbeat"
                and offline_start.isoformat() <= s["timestamp"] <= offline_end.isoformat() + "Z"
            )
        ]
        ground_truth.append({
            "type": "data_gap",
            "care_recipient_id": rid,
            "start": offline_start.isoformat() + "Z",
            "end": offline_end.isoformat() + "Z",
            "category": "activity_engagement",
            "description": "Device heartbeats removed for day 25-26 (total device offline)",
        })

        # Anomaly 6: Missed medication (day 23)
        med_anomaly_start = start_time + timedelta(days=23)
        med_anomaly_end = med_anomaly_start + timedelta(days=1)
        signals = [
            s for s in signals
            if not (
                s["care_recipient_id"] == rid
                and s["signal_type"] == "medication_event"
                and med_anomaly_start.isoformat() <= s["timestamp"] <= med_anomaly_end.isoformat() + "Z"
            )
        ]
        ground_truth.append({
            "type": "missed_medication",
            "care_recipient_id": rid,
            "start": med_anomaly_start.isoformat() + "Z",
            "end": med_anomaly_end.isoformat() + "Z",
            "category": "medication_adherence",
            "description": "Medication events removed for day 23",
        })

        # Anomaly 7: Flagged vitals (day 26-28)
        vitals_anomaly_start = start_time + timedelta(days=26)
        for s in signals:
            if (s["care_recipient_id"] == rid
                    and s["signal_type"] == "vitals_reading"
                    and s["timestamp"] >= vitals_anomaly_start.isoformat()):
                ts = datetime.fromisoformat(s["timestamp"].replace("Z", ""))
                if (ts - vitals_anomaly_start).days < 3:
                    s["metadata"]["flagged"] = True
                    s["metadata"]["qualitative"] = "outside_expected_range"

        ground_truth.append({
            "type": "vitals_flagged",
            "care_recipient_id": rid,
            "start": vitals_anomaly_start.isoformat() + "Z",
            "end": (vitals_anomaly_start + timedelta(days=3)).isoformat() + "Z",
            "category": "vitals_summary",
            "description": "Vitals readings flagged as outside expected range for 3 days",
        })

    # Sort signals by timestamp
    signals.sort(key=lambda s: s.get("timestamp", ""))

    return signals, ground_truth


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_dataset(
    num_recipients: int = NUM_RECIPIENTS,
    caregivers_per_recipient: int = CAREGIVERS_PER_RECIPIENT,
    days: int = DAYS,
    seed: int = SEED,
) -> dict:
    """Generate a complete synthetic dataset."""
    rng = random.Random(seed)
    base_time = datetime(2025, 6, 15, 12, 0, 0)  # Fixed base time for reproducibility

    recipients = generate_care_recipients(num_recipients, rng)
    caregivers = generate_caregivers(recipients, caregivers_per_recipient, rng)
    consent_matrix = generate_consent_matrix(recipients, caregivers, rng, base_time)
    signals, ground_truth = generate_signals(recipients, days, rng, base_time)

    dataset = {
        "metadata": {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "seed": seed,
            "num_recipients": num_recipients,
            "caregivers_per_recipient": caregivers_per_recipient,
            "days": days,
            "base_time": base_time.isoformat() + "Z",
            "total_signals": len(signals),
            "total_anomalies": len(ground_truth),
        },
        "care_recipients": recipients,
        "caregivers": caregivers,
        "consent_matrix": consent_matrix,
        "signals": signals,
        "ground_truth_anomalies": ground_truth,
        "audit_log": [],  # Will be populated at runtime
    }

    return dataset


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic dataset")
    parser.add_argument("--days", type=int, default=DAYS, help="Number of days to simulate")
    parser.add_argument("--recipients", type=int, default=NUM_RECIPIENTS, help="Number of care recipients")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    parser.add_argument("--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    dataset = generate_dataset(
        num_recipients=args.recipients,
        days=args.days,
        seed=args.seed,
    )

    output_path = args.output or os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "sample_dataset.json"
    )

    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2, default=str)

    print(f"Dataset generated:")
    print(f"  Recipients: {len(dataset['care_recipients'])}")
    print(f"  Caregivers: {len(dataset['caregivers'])}")
    print(f"  Consent records: {len(dataset['consent_matrix'])}")
    print(f"  Signals: {len(dataset['signals'])}")
    print(f"  Ground truth anomalies: {len(dataset['ground_truth_anomalies'])}")
    print(f"  Saved to: {output_path}")


if __name__ == "__main__":
    main()
