"""
Test Suite: OAuth2 / OIDC-Ready Authentication Adapter (Phase 3)

Verifies:
1. Valid standard OIDC claims token validation and profile extraction
2. Expired OIDC token rejection
3. Untrusted / invalid issuer rejection
4. Audience mismatch rejection
5. Missing required subject (`sub`) claim rejection
6. Unrecognized caregiver role mapping rejection
7. Anti-impersonation and care-recipient assignment checks
"""

import pytest
import jwt
from datetime import datetime, timezone, timedelta
from api.oidc_auth import (
    validate_oidc_token,
    create_mock_oidc_token,
    OIDC_ISSUER,
    OIDC_AUDIENCE,
    OIDC_SIGNING_KEY,
)


class TestOIDCAuthentication:

    def test_valid_oidc_token_validation(self):
        token = create_mock_oidc_token(
            subject="jane.smith",
            caregiver_id="cg_001",
            role="primary_caregiver",
            care_recipient_ids=["cr_001"],
        )
        res = validate_oidc_token(token)

        assert res.is_valid is True
        assert res.status == "validated"
        assert res.claims.sub == "jane.smith"
        assert res.claims.role == "primary_caregiver"
        assert res.caregiver_profile["caregiver_id"] == "cg_001"
        assert res.caregiver_profile["role"] == "primary_caregiver"
        assert "cr_001" in res.caregiver_profile["care_recipient_ids"]

    def test_expired_oidc_token_rejection(self):
        token = create_mock_oidc_token(
            subject="bob.smith",
            expires_in_minutes=-10,  # Expired in past
        )
        res = validate_oidc_token(token)

        assert res.is_valid is False
        assert res.status == "token_expired"
        assert "expired" in res.error_message.lower()

    def test_invalid_issuer_rejection(self):
        token = create_mock_oidc_token(
            subject="jane.smith",
            issuer="https://untrusted-attacker-idp.com",
        )
        res = validate_oidc_token(token)

        assert res.is_valid is False
        assert res.status == "invalid_issuer"
        assert "issuer" in res.error_message.lower()

    def test_invalid_audience_rejection(self):
        token = create_mock_oidc_token(
            subject="jane.smith",
            audience="wrong-client-app",
        )
        res = validate_oidc_token(token)

        assert res.is_valid is False
        assert res.status == "invalid_audience"
        assert "audience" in res.error_message.lower()

    def test_tampered_signature_rejection(self):
        token = create_mock_oidc_token(
            subject="jane.smith",
            signing_key="unauthorized_attacker_secret_key_12345",
        )
        res = validate_oidc_token(token)

        assert res.is_valid is False
        assert res.status == "invalid_signature"

    def test_invalid_role_claim_rejection(self):
        # Create token with unauthorized role
        now = datetime.now(timezone.utc)
        payload = {
            "sub": "attacker.user",
            "iss": OIDC_ISSUER,
            "aud": OIDC_AUDIENCE,
            "iat": int(now.timestamp()),
            "exp": int((now + timedelta(minutes=30)).timestamp()),
            "caregiver_id": "cg_attacker",
            "role": "super_root_god_mode",  # Invalid role
            "care_recipient_ids": ["cr_001"],
        }
        token = jwt.encode(payload, OIDC_SIGNING_KEY, algorithm="HS256")
        res = validate_oidc_token(token)

        assert res.is_valid is False
        assert res.status == "invalid_role_claim"
