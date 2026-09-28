"""
Test Suite: Authentication, JWT Token Issuance, and Server-Side RBAC

Verifies:
1. Salted password hashing and verification
2. JWT access token creation and decoding
3. JWT expiration handling
4. Server-side RBAC anti-impersonation guard
5. Caregiver recipient assignment authorization
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException

from api.auth import (
    hash_password, verify_password, create_access_token, decode_access_token,
    verify_caregiver_access, SEED_USERS, DEFAULT_PASSWORD, JWT_SECRET_KEY, JWT_ALGORITHM
)


class TestAuthAndRBAC:

    def test_password_hashing_and_verification(self):
        pwd = "SecureEldercarePassword2026!"
        hashed = hash_password(pwd)

        assert hashed != pwd
        assert "$" in hashed
        assert verify_password(pwd, hashed) is True
        assert verify_password("WrongPassword", hashed) is False

    def test_pre_seeded_user_credentials(self):
        for username, user in SEED_USERS.items():
            assert verify_password(DEFAULT_PASSWORD, user["password_hash"]) is True

    def test_jwt_token_creation_and_decoding(self):
        payload = {
            "sub": "jane.smith",
            "caregiver_id": "cg_001",
            "role": "primary_caregiver",
            "care_recipient_ids": ["cr_001"],
        }
        token = create_access_token(payload, expires_delta=timedelta(hours=2))
        decoded = decode_access_token(token)

        assert decoded["sub"] == "jane.smith"
        assert decoded["caregiver_id"] == "cg_001"
        assert decoded["role"] == "primary_caregiver"
        assert decoded["care_recipient_ids"] == ["cr_001"]

    def test_expired_jwt_token_raises_401(self):
        payload = {
            "sub": "jane.smith",
            "caregiver_id": "cg_001",
        }
        # Expired 10 minutes ago
        expired_token = create_access_token(payload, expires_delta=timedelta(minutes=-10))

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(expired_token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_tampered_jwt_token_signature_raises_401(self):
        payload = {"sub": "jane.smith", "role": "neighbor_community"}
        # Signed with a different secret
        fake_token = jwt.encode(payload, "malicious_fake_secret_key", algorithm=JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(fake_token)

        assert exc_info.value.status_code == 401

    def test_rbac_guard_blocks_impersonation(self):
        """Authenticated user 'jane.smith' (cg_001) cannot request alerts claiming to be 'cg_004'."""
        authenticated_user = {
            "username": "jane.smith",
            "caregiver_id": "cg_001",
            "role": "primary_caregiver",
            "care_recipient_ids": ["cr_001"],
        }

        # Attempt to impersonate Dr. Sarah Chen (cg_004)
        with pytest.raises(HTTPException) as exc_info:
            verify_caregiver_access("cg_004", current_user=authenticated_user)

        assert exc_info.value.status_code == 403
        assert "Access denied" in exc_info.value.detail

    def test_rbac_guard_blocks_unassigned_recipient_access(self):
        """Caregiver assigned to cr_001 cannot query data for cr_002."""
        authenticated_user = {
            "username": "jane.smith",
            "caregiver_id": "cg_001",
            "role": "primary_caregiver",
            "care_recipient_ids": ["cr_001"],
        }

        with pytest.raises(HTTPException) as exc_info:
            verify_caregiver_access("cg_001", requested_recipient_id="cr_002", current_user=authenticated_user)

        assert exc_info.value.status_code == 403
        assert "not authorized to access care recipient" in exc_info.value.detail

    def test_admin_role_can_inspect_any_caregiver_or_recipient(self):
        admin_user = {
            "username": "admin",
            "caregiver_id": "admin_001",
            "role": "admin",
            "care_recipient_ids": ["cr_001", "cr_002", "cr_003"],
        }
        # Admin can access without exception
        assert verify_caregiver_access("cg_001", requested_recipient_id="cr_001", current_user=admin_user) is True
        assert verify_caregiver_access("cg_004", requested_recipient_id="cr_003", current_user=admin_user) is True
