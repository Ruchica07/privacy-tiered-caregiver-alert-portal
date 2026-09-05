"""
Test suite for the Content Linter — highest priority test coverage.

Tests that:
1. Compliant operational text passes cleanly
2. Banned medical/diagnostic patterns are caught
3. Fallback phrasings are applied when violations found
4. Edge cases and borderline text are handled
5. The linter never silently drops alerts (fail-safe)
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

import pytest
from engine.content_linter import (
    lint_text, is_compliant, sanitize_alert_text, get_fallback_text,
    BANNED_PATTERNS, FALLBACK_PHRASINGS,
)


# ---------------------------------------------------------------------------
# Compliant text (should PASS the linter)
# ---------------------------------------------------------------------------

COMPLIANT_TEXTS = [
    "No check-in received in the last 6 hours.",
    "Activity patterns have deviated from the usual baseline.",
    "Consider reaching out to check in.",
    "An unexpected departure from home was detected during nighttime hours.",
    "No social contact has been logged in the last 5 days.",
    "Expected data from a monitoring source has not been received.",
    "This may indicate a device or connectivity issue.",
    "Recent wellness readings show 3 of 10 readings flagged outside the expected range.",
    "Consider consulting with the care recipient's healthcare provider.",
    "Check if the monitoring device is charged and connected.",
    "A scheduled check-in was not completed within the expected window.",
    "This is an operational pattern alert, not a medical assessment.",
    "Everything looks on track.",
    "Attention may be needed soon.",
]


@pytest.mark.parametrize("text", COMPLIANT_TEXTS)
def test_compliant_text_passes(text):
    """Compliant operational text should have zero violations."""
    violations = lint_text(text)
    assert len(violations) == 0, f"Expected compliant, got violations: {violations}"
    assert is_compliant(text) is True


# ---------------------------------------------------------------------------
# Non-compliant text (should FAIL the linter)
# ---------------------------------------------------------------------------

NON_COMPLIANT_TEXTS = [
    # Diagnostic language
    ("Patient may be hypoglycemic", "specific diagnosis"),
    ("This indicates a condition of heart failure", "diagnostic inference"),
    ("Symptoms of diabetes detected", "specific diagnosis"),
    ("Diagnosis: atrial fibrillation", "specific diagnosis"),
    ("Signs of a medical emergency", "clinical sign attribution"),
    ("Probable diagnosis of dementia", "specific diagnosis"),
    ("Consistent with a diagnosis", "diagnostic consistency claim"),

    # Prescriptive medical instructions
    ("Give them 500mg of metformin", "specific medication name"),
    ("Administer insulin immediately", "specific medication name"),
    ("Increase the dose of lisinopril", "specific medication name"),
    ("Patient should take 2 tablets", "prescriptive advice"),
    ("Needs to receive warfarin", "specific medication name"),

    # Raw clinical measurements
    ("Blood pressure 140/90 mmHg", "raw clinical measurement"),
    ("Heart rate 120 bpm detected", "raw clinical measurement"),
    ("Blood sugar 250 mg/dL", "raw clinical measurement"),
    ("SpO2: 88%", "raw clinical measurement"),

    # Specific medications/conditions
    ("The patient is on atorvastatin", "specific medication name"),
    ("History of Parkinson's disease", "specific diagnosis"),
    ("Alzheimer's progression noted", "specific diagnosis"),
    ("COPD exacerbation", "specific diagnosis"),
]


@pytest.mark.parametrize("text,expected_reason", NON_COMPLIANT_TEXTS)
def test_non_compliant_text_caught(text, expected_reason):
    """Non-compliant text must be caught by the linter."""
    violations = lint_text(text)
    assert len(violations) > 0, f"Expected violation for: '{text}'"
    assert is_compliant(text) is False


# ---------------------------------------------------------------------------
# Sanitization (fail-safe: violations → fallback text)
# ---------------------------------------------------------------------------

def test_sanitize_replaces_with_fallback():
    """When violations found, sanitize should return the safe fallback."""
    bad_text = "Patient may be hypoglycemic, administer insulin"
    sanitized, violations = sanitize_alert_text(bad_text, "adherence_alert")

    assert len(violations) > 0
    assert sanitized == FALLBACK_PHRASINGS["adherence_alert"]
    assert sanitized != bad_text


def test_sanitize_preserves_compliant_text():
    """Compliant text should pass through unchanged."""
    good_text = "No check-in received in the last 6 hours."
    sanitized, violations = sanitize_alert_text(good_text, "adherence_alert")

    assert len(violations) == 0
    assert sanitized == good_text


def test_sanitize_unknown_alert_type_uses_generic():
    """Unknown alert types should fall back to the generic phrasing."""
    bad_text = "Diagnosis: diabetes confirmed"
    sanitized, violations = sanitize_alert_text(bad_text, "unknown_type")

    assert len(violations) > 0
    assert sanitized == FALLBACK_PHRASINGS["generic"]


def test_sanitize_empty_text():
    """Empty text should pass cleanly."""
    sanitized, violations = sanitize_alert_text("", "generic")
    assert len(violations) == 0
    assert sanitized == ""


# ---------------------------------------------------------------------------
# Fallback phrasings
# ---------------------------------------------------------------------------

def test_all_alert_types_have_fallbacks():
    """Every alert type referenced in the system should have a fallback."""
    expected_types = ["adherence_alert", "pattern_alert", "safety_alert",
                      "isolation_alert", "data_gap", "generic"]
    for alert_type in expected_types:
        fallback = get_fallback_text(alert_type)
        assert fallback, f"No fallback for {alert_type}"
        assert is_compliant(fallback), f"Fallback for {alert_type} fails its own linter!"


def test_fallback_texts_are_compliant():
    """All pre-approved fallback texts must themselves pass the linter."""
    for alert_type, text in FALLBACK_PHRASINGS.items():
        violations = lint_text(text)
        assert len(violations) == 0, (
            f"Fallback text for '{alert_type}' has linter violations: {violations}"
        )


# ---------------------------------------------------------------------------
# Edge case: Borderline / ambiguous text (5th edge case)
# ---------------------------------------------------------------------------

BORDERLINE_TEXTS = [
    # Should be caught — medical-adjacent
    ("This could be a symptom of something serious", True),
    ("Treatment for the condition should begin", True),
    ("Consider ruling out cardiac issues", True),

    # Should pass — operational language that sounds medical-ish but isn't
    ("The check-in pattern suggests a change in routine", False),
    ("Activity levels have been lower than expected", False),
    ("No data from the health monitor device", False),
]


@pytest.mark.parametrize("text,should_fail", BORDERLINE_TEXTS)
def test_borderline_text(text, should_fail):
    """Borderline text must be correctly classified."""
    violations = lint_text(text)
    if should_fail:
        assert len(violations) > 0, f"Expected borderline text to be caught: '{text}'"
    else:
        assert len(violations) == 0, f"Expected borderline text to pass: '{text}', got: {violations}"


# ---------------------------------------------------------------------------
# Linter never produces empty output (fail-safe)
# ---------------------------------------------------------------------------

def test_sanitize_never_returns_none():
    """Sanitize must always return a string, never None."""
    for text in ["", "safe text", "Diagnosis: diabetes", "Give them insulin"]:
        for atype in list(FALLBACK_PHRASINGS.keys()) + ["unknown"]:
            result, _ = sanitize_alert_text(text, atype)
            assert result is not None, f"sanitize_alert_text returned None for '{text}', type='{atype}'"
            assert isinstance(result, str)


# ---------------------------------------------------------------------------
# Pattern count / coverage
# ---------------------------------------------------------------------------

def test_banned_patterns_not_empty():
    """We must have a meaningful set of banned patterns."""
    assert len(BANNED_PATTERNS) >= 20, f"Only {len(BANNED_PATTERNS)} patterns — too few for safety"
