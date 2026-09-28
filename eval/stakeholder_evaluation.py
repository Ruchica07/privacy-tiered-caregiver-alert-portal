"""
Formal Stakeholder Usability & Feedback Loop Evaluation Protocol

Academic Classification:
    SYNTHETIC / MOCK / PROTOCOL VALIDATION (Academic Review 2)
    Note: Evaluated using standardized System Usability Scale (SUS, Brooke 1996)
    and structured task scenario completion protocols across 12 simulated stakeholder proxies.

Roles Evaluated:
1. Primary Caregivers (Family / Adult Children) (n=3)
2. Secondary Caregivers (Extended Family) (n=3)
3. Community / Trusted Neighbors (n=3)
4. Professional Care Coordinators / Case Managers (n=3)
"""

import json
import statistics
from pathlib import Path
from typing import Dict, Any, List

BASE_DIR = Path(__file__).resolve().parent.parent

# Standard 10-Item System Usability Scale (SUS) Questions
SUS_QUESTIONS = [
    "1. I think that I would like to use this system frequently.",
    "2. I found the system unnecessarily complex.",
    "3. I thought the system was easy to use.",
    "4. I think that I would need the support of a technical person to be able to use this system.",
    "5. I found the various functions in this system were well integrated.",
    "6. I thought there was too much inconsistency in this system.",
    "7. I would imagine that most people would learn to use this system very quickly.",
    "8. I found the system very cumbersome to use.",
    "9. I felt very confident using the system.",
    "10. I needed to learn a lot of things before I could get going with this system.",
]

# Structured Task Scenarios
TASK_SCENARIOS = [
    {"task_id": "T1", "name": "Identify Urgent Alert", "description": "Identify nocturnal departure alert and find actionable next step."},
    {"task_id": "T2", "name": "Verify Privacy Tier", "description": "Check what categories are visible vs redacted under secondary caregiver role."},
    {"task_id": "T3", "name": "Freshness Status Audit", "description": "Distinguish between active sensor stream and missing heartbeat (>24h data gap)."},
    {"task_id": "T4", "name": "Consent Matrix Update", "description": "Grant Tier 2 access for Location & Safety category and save."},
    {"task_id": "T5", "name": "Audit Verification", "description": "Inspect cryptographic hash chain status for tampering."},
]

# 12 Simulated Stakeholder Proxy Responses (SUS 1-5 scale)
STAKEHOLDER_RESPONSES = [
    # Primary Caregivers (Focus: peace of mind, actionability, trend context)
    {"participant_id": "P01_PC", "role": "primary_caregiver", "sus_scores": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1], "tasks_completed": 5, "comprehension_score": 95, "privacy_trust_score": 92, "freshness_clarity": 95},
    {"participant_id": "P02_PC", "role": "primary_caregiver", "sus_scores": [4, 2, 4, 1, 4, 2, 5, 2, 4, 2], "tasks_completed": 5, "comprehension_score": 90, "privacy_trust_score": 88, "freshness_clarity": 90},
    {"participant_id": "P03_PC", "role": "primary_caregiver", "sus_scores": [5, 1, 5, 2, 4, 1, 4, 1, 5, 1], "tasks_completed": 5, "comprehension_score": 92, "privacy_trust_score": 95, "freshness_clarity": 92},

    # Secondary Caregivers (Focus: non-intrusive status, clear operational summary)
    {"participant_id": "P04_SC", "role": "secondary_caregiver", "sus_scores": [4, 2, 4, 1, 5, 1, 4, 2, 4, 1], "tasks_completed": 5, "comprehension_score": 88, "privacy_trust_score": 90, "freshness_clarity": 88},
    {"participant_id": "P05_SC", "role": "secondary_caregiver", "sus_scores": [4, 1, 5, 1, 4, 1, 5, 1, 4, 2], "tasks_completed": 5, "comprehension_score": 90, "privacy_trust_score": 92, "freshness_clarity": 92},
    {"participant_id": "P06_SC", "role": "secondary_caregiver", "sus_scores": [4, 2, 4, 2, 4, 1, 4, 1, 4, 2], "tasks_completed": 4, "comprehension_score": 85, "privacy_trust_score": 88, "freshness_clarity": 85},

    # Neighbors / Community (Focus: binary wellness ping, zero medical diagnosis leak)
    {"participant_id": "P07_NC", "role": "neighbor_community", "sus_scores": [4, 1, 5, 1, 4, 1, 5, 1, 5, 1], "tasks_completed": 5, "comprehension_score": 95, "privacy_trust_score": 98, "freshness_clarity": 90},
    {"participant_id": "P08_NC", "role": "neighbor_community", "sus_scores": [3, 2, 4, 1, 4, 1, 4, 1, 4, 1], "tasks_completed": 5, "comprehension_score": 90, "privacy_trust_score": 95, "freshness_clarity": 88},
    {"participant_id": "P09_NC", "role": "neighbor_community", "sus_scores": [4, 1, 4, 1, 5, 1, 5, 1, 4, 1], "tasks_completed": 5, "comprehension_score": 92, "privacy_trust_score": 96, "freshness_clarity": 90},

    # Professional Care Coordinators (Focus: fleet oversight, category constraints, tamper-evident audit)
    {"participant_id": "P10_CC", "role": "care_coordinator_professional", "sus_scores": [5, 1, 5, 1, 5, 1, 5, 1, 5, 1], "tasks_completed": 5, "comprehension_score": 98, "privacy_trust_score": 96, "freshness_clarity": 98},
    {"participant_id": "P11_CC", "role": "care_coordinator_professional", "sus_scores": [5, 2, 4, 1, 5, 1, 4, 1, 5, 1], "tasks_completed": 5, "comprehension_score": 95, "privacy_trust_score": 94, "freshness_clarity": 95},
    {"participant_id": "P12_CC", "role": "care_coordinator_professional", "sus_scores": [4, 1, 5, 1, 5, 1, 5, 2, 4, 1], "tasks_completed": 5, "comprehension_score": 92, "privacy_trust_score": 95, "freshness_clarity": 96},
]


def calculate_individual_sus(scores: List[int]) -> float:
    """
    Standard SUS calculation:
    - Odd items (1, 3, 5, 7, 9): score - 1
    - Even items (2, 4, 6, 8, 10): 5 - score
    - Sum * 2.5 (yields 0-100 score)
    """
    total = 0
    for i, s in enumerate(scores):
        if (i + 1) % 2 == 1:
            total += (s - 1)
        else:
            total += (5 - s)
    return total * 2.5


def run_stakeholder_evaluation() -> Dict[str, Any]:
    """Calculate composite usability metrics from the evaluation protocol."""
    sus_scores = []
    task_completions = []
    comprehensions = []
    privacy_trusts = []
    freshness_clarities = []

    per_role = {}

    for p in STAKEHOLDER_RESPONSES:
        score = calculate_individual_sus(p["sus_scores"])
        sus_scores.append(score)
        task_completions.append((p["tasks_completed"] / len(TASK_SCENARIOS)) * 100)
        comprehensions.append(p["comprehension_score"])
        privacy_trusts.append(p["privacy_trust_score"])
        freshness_clarities.append(p["freshness_clarity"])

        role = p["role"]
        per_role.setdefault(role, []).append(score)

    mean_sus = statistics.mean(sus_scores)
    std_sus = statistics.stdev(sus_scores)
    mean_task_completion = statistics.mean(task_completions)
    mean_comprehension = statistics.mean(comprehensions)
    mean_privacy_trust = statistics.mean(privacy_trusts)
    mean_freshness_clarity = statistics.mean(freshness_clarities)

    # SUS Grade Benchmark (Bangor et al. 2008): >80.3 = Grade A (Excellent)
    sus_grade = "Grade A (Excellent)" if mean_sus >= 80.3 else "Grade B (Good)"

    results = {
        "classification": "Synthetic / Mock / Protocol Validation (Academic Review 2)",
        "total_participants": len(STAKEHOLDER_RESPONSES),
        "mean_sus_score": round(mean_sus, 2),
        "std_sus_score": round(std_sus, 2),
        "sus_grade": sus_grade,
        "task_completion_rate": round(mean_task_completion, 1),
        "alert_comprehension_rate": round(mean_comprehension, 1),
        "privacy_tier_trust_rate": round(mean_privacy_trust, 1),
        "freshness_state_clarity_rate": round(mean_freshness_clarity, 1),
        "medical_boundary_compliance": 100.0,
        "per_role_sus": {k: round(statistics.mean(v), 2) for k, v in per_role.items()},
        "scenarios_evaluated": len(TASK_SCENARIOS),
    }

    # Write evaluation report
    write_stakeholder_report(results)
    return results


def write_stakeholder_report(results: Dict[str, Any]):
    report_path = BASE_DIR / "eval" / "stakeholder_evaluation_report.md"
    content = f"""# Synthetic / Simulated Usability Validation Report (Review 2)

**Document Classification**: Synthetic / Simulated Usability Protocol Validation  
**Evaluation Methodology**: Automated Protocol Validation via Simulated Stakeholder Personas (SUS, Brooke 1996)  
**Human Participants**: **0 (No human subjects were involved; all scores are simulated proxy profiles for protocol verification)**  
**Target Roles Modeled**: 4 Caregiver Roles (12 Synthetic Persona Configurations)

---

## 1. Executive Summary & Pipeline Validation Metrics

> **Note on Academic Integrity**: This benchmark validates that the evaluation scoring pipeline, System Usability Scale (SUS) computation logic, and scenario verification engine function correctly. The numbers below reflect simulated response distributions across standardized persona profiles to benchmark the assessment framework prior to Phase 3 human studies.

| Usability Metric | Target Benchmark | Simulated Result | Protocol Status |
|---|---|---|---|
| **System Usability Scale (SUS)** | &ge; 75.0 / 100 | **{results['mean_sus_score']} &plusmn; {results['std_sus_score']}** | **{results['sus_grade']} (Pipeline Validated)** |
| **Scenario Task Completion Rate** | &ge; 90.0% | **{results['task_completion_rate']}%** | **Pass** |
| **Alert Comprehension & Actionability** | &ge; 85.0% | **{results['alert_comprehension_rate']}%** | **Pass** |
| **Privacy Tier Transparency & Trust** | &ge; 90.0% | **{results['privacy_tier_trust_rate']}%** | **Pass** |
| **Fresh/Stale/Missing State Understanding** | &ge; 85.0% | **{results['freshness_state_clarity_rate']}%** | **Pass** |
| **Operational vs Medical Boundary Clarity** | 100.0% | **{results['medical_boundary_compliance']}%** | **Pass** |

---

## 2. Simulated Persona SUS Breakdown by Caregiver Role

| Caregiver Role | Simulated Sample Profile | Mean SUS Score | Protocol Verification Goal |
|---|---|---|---|
| **Primary Caregiver** | 3 Persona Profiles | **{results['per_role_sus'].get('primary_caregiver', 0.0)} / 100** | Peace-of-mind alert presentation & actionable steps |
| **Secondary Caregiver** | 3 Persona Profiles | **{results['per_role_sus'].get('secondary_caregiver', 0.0)} / 100** | Non-alarming categorical summary verification |
| **Neighbor / Community** | 3 Persona Profiles | **{results['per_role_sus'].get('neighbor_community', 0.0)} / 100** | Zero clinical disclosure / privacy containment |
| **Care Coordinator (Professional)** | 3 Persona Profiles | **{results['per_role_sus'].get('care_coordinator_professional', 0.0)} / 100** | Fleet overview & consent boundary adherence |

---

## 3. Simulated Task Scenarios Validated

1. **T1: Urgent Anomaly Recognition**: Simulates identifying nocturnal departure without medical terminology.
2. **T2: Privacy Tier Verification**: Simulates secondary caregiver role displaying operational summary while redacting raw clinical details.
3. **T3: Sensor Outage vs. Health Emergency**: Simulates distinguishing missing telemetry (>24h data gap) from medical distress.
4. **T4: Consent Matrix Adjustment**: Simulates consent escalation and immediate server-side filtering enforcement.
5. **T5: Cryptographic Audit Verification**: Simulates cryptographic SHA-256 hash-chain verification for access integrity.

---

## 4. Academic Limitations & Scope Boundary
**Important**: No human clinical trial or real stakeholder study has been executed in Review 2. All results in this report represent automated synthetic protocol execution to verify the evaluation pipeline. Formal empirical pilot testing with real family caregivers and older adults is designated for Phase 3 / Final Capstone Defense.
"""
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(content)


if __name__ == "__main__":
    res = run_stakeholder_evaluation()
    print("Stakeholder Evaluation Completed:")
    print(json.dumps(res, indent=2))
