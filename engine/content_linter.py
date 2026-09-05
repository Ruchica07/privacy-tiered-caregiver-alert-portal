"""
Content Linter — Operational vs. Medical Language Safety Scanner

Scans alert text templates against a banned-phrase/pattern list to ensure
no diagnostic or prescriptive medical language reaches the UI. Runs at
build time AND runtime on every alert text.

Fail-safe: If a generated alert fails the linter, it is downgraded to a
pre-approved generic operational phrasing rather than showing risky text
or showing nothing.
"""

import re
from typing import List, Tuple, Optional


# ---------------------------------------------------------------------------
# Banned patterns — diagnostic, prescriptive, or clinically-specific language
# ---------------------------------------------------------------------------

BANNED_PATTERNS: List[Tuple[str, str]] = [
    # Diagnostic verbs / phrases
    (r"\bdiagnos(e|ed|es|is|tic)\b", "diagnostic language"),
    (r"\bindicates?\s+(a\s+)?condition\b", "diagnostic inference"),
    (r"\bsymptom(s)?\s+of\b", "symptom attribution"),
    (r"\bsuggest(s|ing)?\s+(a\s+)?(possible\s+)?condition\b", "diagnostic suggestion"),
    (r"\bsign(s)?\s+of\s+(a\s+)?(medical|clinical|health)\b", "clinical sign attribution"),
    (r"\bconsistent\s+with\s+(a\s+)?diagnos", "diagnostic consistency claim"),
    (r"\bprobable\s+(diagnos|condition|disease|illness)\b", "probable diagnosis"),
    (r"\brul(e|ing)\s+out\b", "clinical rule-out language"),
    (r"\bdifferential\s+diagnos", "differential diagnosis language"),
    (r"\bprognos(is|tic)\b", "prognostic language"),
    (r"\bclinical\s+finding\b", "clinical finding language"),
    (r"\bpatholog(y|ical)\b", "pathological language"),

    # Prescriptive medical instructions
    (r"\bgive\s+them\b", "prescriptive instruction"),
    (r"\badminister\b", "prescriptive instruction"),
    (r"\bincrease\s+the\s+dose\b", "dosage instruction"),
    (r"\bdecrease\s+the\s+dose\b", "dosage instruction"),
    (r"\btake\s+\d+\s*(mg|ml|tablet|pill|capsule)\b", "specific dosage instruction"),
    (r"\bprescri(be|bed|ption)\b", "prescription language"),
    (r"\bmedicate\b", "medication instruction"),
    (r"\bdosage\b", "dosage language"),
    (r"\btreat(ment)?\s+for\b", "treatment language"),
    (r"\btherapy\s+for\b", "therapy language"),
    (r"\bshould\s+(take|receive|be\s+given)\b", "prescriptive advice"),
    (r"\bneed(s)?\s+to\s+(take|receive|be\s+given)\b", "prescriptive advice"),

    # Specific medication / diagnosis names (common examples)
    (r"\bmetformin\b", "specific medication name"),
    (r"\binsulin\b", "specific medication name"),
    (r"\blisinopril\b", "specific medication name"),
    (r"\batorvastatin\b", "specific medication name"),
    (r"\bomeprazole\b", "specific medication name"),
    (r"\bwarfarin\b", "specific medication name"),
    (r"\blevothyroxine\b", "specific medication name"),
    (r"\bamlodipine\b", "specific medication name"),
    (r"\bhypertension\b", "specific diagnosis"),
    (r"\bdiabetes\b", "specific diagnosis"),
    (r"\bhypoglycemi(a|c)\b", "specific diagnosis"),
    (r"\bhyperglycemi(a|c)\b", "specific diagnosis"),
    (r"\batrial\s+fibrillation\b", "specific diagnosis"),
    (r"\bcongestive\s+heart\s+failure\b", "specific diagnosis"),
    (r"\bdementia\b", "specific diagnosis"),
    (r"\balzheimer\b", "specific diagnosis"),
    (r"\bparkinson\b", "specific diagnosis"),
    (r"\bosteoporosis\b", "specific diagnosis"),
    (r"\barthritis\b", "specific diagnosis"),
    (r"\bcopd\b", "specific diagnosis"),

    # Clinical measurement language (raw values)
    (r"\bblood\s+pressure\s+(\d+|is\s+\d+)\b", "raw clinical measurement"),
    (r"\bheart\s+rate\s+(\d+|is\s+\d+)\b", "raw clinical measurement"),
    (r"\bblood\s+sugar\s+(\d+|is\s+\d+|level)\b", "raw clinical measurement"),
    (r"\bsp[oO]2\s*[=:]\s*\d+\b", "raw clinical measurement"),
    (r"\bbmi\s*[=:]\s*\d+\b", "raw clinical measurement"),
    (r"\b\d+\s*mmHg\b", "raw clinical measurement"),
    (r"\b\d+\s*bpm\b", "raw clinical measurement"),
    (r"\b\d+\s*mg/dL\b", "raw clinical measurement"),

    # Emergency medical language that implies diagnosis
    (r"\bpatient\s+may\s+be\b", "diagnostic speculation"),
    (r"\bpatient\s+is\s+(likely|probably)\b", "diagnostic speculation"),
    (r"\bmedical\s+emergency\b", "medical emergency declaration"),
    (r"\bseek\s+immediate\s+medical\b", "prescriptive emergency advice"),
]

# Pre-compile all patterns for performance
_COMPILED_PATTERNS: List[Tuple[re.Pattern, str]] = [
    (re.compile(pattern, re.IGNORECASE), reason)
    for pattern, reason in BANNED_PATTERNS
]


# ---------------------------------------------------------------------------
# Pre-approved fallback phrasings (safe operational language)
# ---------------------------------------------------------------------------

FALLBACK_PHRASINGS = {
    "adherence_alert": "A scheduled check-in was not completed within the expected window. Consider reaching out.",
    "pattern_alert": "Activity patterns have deviated from the usual baseline. Consider checking in.",
    "safety_alert": "An unexpected location or safety-related pattern was detected. Consider verifying wellbeing.",
    "isolation_alert": "Social contact appears lower than usual. Consider reaching out.",
    "data_gap": "Expected data from a monitoring source has not been received. This may indicate a device or connectivity issue — it does not necessarily reflect a change in wellbeing.",
    "generic": "An operational pattern was detected that may warrant attention. Consider reaching out to check in.",
}


# ---------------------------------------------------------------------------
# Linter functions
# ---------------------------------------------------------------------------

class LintViolation:
    """A single linter violation found in alert text."""

    def __init__(self, pattern: str, reason: str, match_text: str, position: int):
        self.pattern = pattern
        self.reason = reason
        self.match_text = match_text
        self.position = position

    def __repr__(self):
        return f"LintViolation(reason='{self.reason}', match='{self.match_text}', pos={self.position})"

    def to_dict(self):
        return {
            "reason": self.reason,
            "match_text": self.match_text,
            "position": self.position,
        }


def lint_text(text: str) -> List[LintViolation]:
    """
    Scan text for banned medical/diagnostic patterns.
    
    Returns a list of LintViolation objects. Empty list = text is compliant.
    """
    if not text:
        return []

    violations = []
    for compiled_pattern, reason in _COMPILED_PATTERNS:
        for match in compiled_pattern.finditer(text):
            violations.append(LintViolation(
                pattern=compiled_pattern.pattern,
                reason=reason,
                match_text=match.group(),
                position=match.start(),
            ))

    return violations


def is_compliant(text: str) -> bool:
    """Quick check: does this text pass the linter with no violations?"""
    return len(lint_text(text)) == 0


def sanitize_alert_text(
    text: str,
    alert_type: str = "generic",
    fallback_map: Optional[dict] = None,
) -> Tuple[str, List[LintViolation]]:
    """
    Sanitize alert text: if violations are found, replace with a safe fallback.
    
    Args:
        text: The alert text to check
        alert_type: The alert type key for fallback lookup
        fallback_map: Optional custom fallback map; defaults to FALLBACK_PHRASINGS
    
    Returns:
        Tuple of (sanitized_text, list_of_violations_found).
        If no violations, sanitized_text == original text.
    """
    violations = lint_text(text)

    if not violations:
        return text, []

    fmap = fallback_map or FALLBACK_PHRASINGS
    fallback = fmap.get(alert_type, fmap.get("generic", "An operational pattern was detected."))

    return fallback, violations


def get_fallback_text(alert_type: str) -> str:
    """Get the pre-approved fallback phrasing for an alert type."""
    return FALLBACK_PHRASINGS.get(alert_type, FALLBACK_PHRASINGS["generic"])


def add_banned_pattern(pattern: str, reason: str) -> None:
    """Add a new banned pattern at runtime (e.g., for testing or extension)."""
    BANNED_PATTERNS.append((pattern, reason))
    _COMPILED_PATTERNS.append((re.compile(pattern, re.IGNORECASE), reason))
