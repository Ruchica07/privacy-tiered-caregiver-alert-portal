"""
Test Suite: Advanced Synthetic Evaluation & Stakeholder Usability Protocol

Verifies:
1. Advanced stress dataset generation
2. Stress evaluation execution
3. Stakeholder SUS usability metrics computation
"""

import pytest
from data.generate_advanced_synthetic import generate_advanced_stress_dataset
from eval.advanced_metrics import evaluate_advanced_stress
from eval.stakeholder_evaluation import run_stakeholder_evaluation, calculate_individual_sus


class TestAdvancedEvaluationSuite:

    def test_advanced_stress_dataset_generation(self):
        ds = generate_advanced_stress_dataset(seed=42)
        assert "signals" in ds
        assert "injected_stress_metadata" in ds
        meta = ds["injected_stress_metadata"]
        assert len(meta.get("duplicates", [])) == 50
        assert len(meta.get("future_timestamps", [])) == 20
        assert len(meta.get("sensor_noise_spikes", [])) == 30

    def test_advanced_stress_evaluation_metrics(self):
        results = evaluate_advanced_stress()
        assert results["duplicate_detection_accuracy"] >= 98.0
        assert results["future_timestamp_rejection_rate"] >= 98.0
        assert results["noise_smoothing_interventions"] >= 10
        assert results["fail_safe_operational_rate"] == 100.0

    def test_sus_scoring_formula(self):
        # Perfect SUS (5s on odd items, 1s on even items) = (4 * 5 + 4 * 5) * 2.5 = 100.0
        perfect_scores = [5, 1, 5, 1, 5, 1, 5, 1, 5, 1]
        assert calculate_individual_sus(perfect_scores) == 100.0

        # Worst SUS = 0.0
        worst_scores = [1, 5, 1, 5, 1, 5, 1, 5, 1, 5]
        assert calculate_individual_sus(worst_scores) == 0.0

    def test_stakeholder_evaluation_results(self):
        res = run_stakeholder_evaluation()
        assert res["total_participants"] == 12
        assert res["mean_sus_score"] >= 75.0
        assert res["task_completion_rate"] >= 90.0
        assert res["privacy_tier_trust_rate"] >= 85.0
