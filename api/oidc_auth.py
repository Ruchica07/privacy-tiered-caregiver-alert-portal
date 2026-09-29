"""
OAuth2 / OpenID Connect (OIDC) Authentication Adapter (Phase 3)

Architecture:
External Identity Provider (IdP / Okta / Azure AD / Auth0 / Keycloak)
  ↓ (Bearer OIDC ID/Access Token)
OIDC Token Validator Adapter (Validates signature, issuer, audience, expiry, claims)
  ↓
Role & Claim Mapper (Maps standard OIDC claims to AegisCare Caregiver Roles)
  ↓
Server-Side RBAC Guard (Enforces care recipient assignment boundaries & anti-impersonation)
  ↓
AegisCare Protected Endpoints

Environment Configuration:
- `AEGISCARE_OIDC_ISSUER`: Expected token issuer URL (default: "https://auth.aegiscare.internal/oauth2/v1")
- `AEGISCARE_OIDC_AUDIENCE`: Expected token audience (default: "aegiscare-portal-api")
- `AEGISCARE_OIDC_JWKS_URI`: Optional JWKS endpoint for external public key discovery

Note:
This is an enterprise-ready architecture adapter. In local development and testing,
symmetric test keys or local JWTs are supported. Connecting to a real production IdP
requires deployment-specific client credentials and active IdP endpoints.
"""

import os
import jwt
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import HTTPException, status, Header

# Configurable OIDC settings
OIDC_ISSUER = os.environ.get("AEGISCARE_OIDC_ISSUER", "https://auth.aegiscare.internal/oauth2/v1")
OIDC_AUDIENCE = os.environ.get("AEGISCARE_OIDC_AUDIENCE", "aegiscare-portal-api")
OIDC_SIGNING_KEY = os.environ.get("AEGISCARE_OIDC_SIGNING_KEY", "aegiscare_oidc_signing_secret_key_2026_qbee")
OIDC_ALGORITHMS = ["HS256", "RS256"]

VALID_ROLES = {
    "primary_caregiver",
    "secondary_caregiver",
    "neighbor_community",
    "care_coordinator_professional",
    "admin",
}


class OIDCClaims(BaseModel):
    sub: str = Field(..., description="Unique subject identifier (user ID or username)")
    iss: str = Field(..., description="Token issuer identifier")
    aud: str = Field(..., description="Token target audience")
    exp: int = Field(..., description="Token expiration timestamp (epoch seconds)")
    iat: int = Field(..., description="Token issuance timestamp (epoch seconds)")
    email: Optional[str] = None
    name: Optional[str] = None
    caregiver_id: Optional[str] = None
    role: Optional[str] = "secondary_caregiver"
    care_recipient_ids: List[str] = Field(default_factory=list)


class OIDCValidationResult(BaseModel):
    is_valid: bool
    status: str
    claims: Optional[OIDCClaims] = None
    error_message: Optional[str] = None
    caregiver_profile: Optional[Dict[str, Any]] = None


def create_mock_oidc_token(
    subject: str = "jane.smith",
    caregiver_id: str = "cg_001",
    role: str = "primary_caregiver",
    care_recipient_ids: Optional[List[str]] = None,
    issuer: str = OIDC_ISSUER,
    audience: str = OIDC_AUDIENCE,
    expires_in_minutes: int = 60,
    signing_key: str = OIDC_SIGNING_KEY,
    algorithm: str = "HS256",
) -> str:
    """
    Utility for automated testing and sandbox simulation to generate a
    cryptographically valid OIDC token conforming to standard OIDC claims.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=expires_in_minutes)).timestamp()),
        "email": f"{subject}@aegiscare.internal",
        "name": subject.replace(".", " ").title(),
        "caregiver_id": caregiver_id,
        "role": role,
        "care_recipient_ids": care_recipient_ids or ["cr_001"],
    }
    return jwt.encode(payload, signing_key, algorithm=algorithm)


def validate_oidc_token(
    token: str,
    expected_issuer: str = OIDC_ISSUER,
    expected_audience: str = OIDC_AUDIENCE,
    signing_key: str = OIDC_SIGNING_KEY,
) -> OIDCValidationResult:
    """
    Validates an incoming Bearer token against standard OIDC specification:
    - Signature validity
    - Expiration (exp)
    - Issuer identity (iss)
    - Target audience (aud)
    - Required subject (sub)
    - Role claim mapping to valid AegisCare roles
    """
    if not token or not isinstance(token, str):
        return OIDCValidationResult(
            is_valid=False,
            status="invalid_token_format",
            error_message="Missing or non-string Bearer token provided."
        )

    try:
        # Decode without verification first to inspect unverified claims if debugging
        unverified_headers = jwt.get_unverified_header(token)
        algorithm = unverified_headers.get("alg", "HS256")

        # Decode and verify claims
        decoded = jwt.decode(
            token,
            signing_key,
            algorithms=[algorithm],
            issuer=expected_issuer,
            audience=expected_audience,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iss": True,
                "verify_aud": True,
                "require": ["exp", "iss", "aud", "sub"],
            }
        )

        sub = decoded.get("sub")
        if not sub:
            return OIDCValidationResult(
                is_valid=False,
                status="missing_subject_claim",
                error_message="OIDC token is missing required 'sub' claim."
            )

        role = decoded.get("role", "secondary_caregiver")
        if role not in VALID_ROLES:
            return OIDCValidationResult(
                is_valid=False,
                status="invalid_role_claim",
                error_message=f"Claimed role '{role}' is not a recognized AegisCare role."
            )

        claims = OIDCClaims(
            sub=sub,
            iss=decoded.get("iss"),
            aud=decoded.get("aud"),
            exp=decoded.get("exp"),
            iat=decoded.get("iat"),
            email=decoded.get("email"),
            name=decoded.get("name", sub),
            caregiver_id=decoded.get("caregiver_id", sub),
            role=role,
            care_recipient_ids=decoded.get("care_recipient_ids", []),
        )

        caregiver_profile = {
            "caregiver_id": claims.caregiver_id,
            "username": claims.sub,
            "name": claims.name,
            "email": claims.email,
            "role": claims.role,
            "care_recipient_ids": claims.care_recipient_ids,
            "auth_provider": "OIDC",
            "issuer": claims.iss,
        }

        return OIDCValidationResult(
            is_valid=True,
            status="validated",
            claims=claims,
            caregiver_profile=caregiver_profile,
        )

    except jwt.ExpiredSignatureError:
        return OIDCValidationResult(
            is_valid=False,
            status="token_expired",
            error_message="OIDC Bearer token has expired. Please re-authenticate."
        )
    except jwt.InvalidIssuerError:
        return OIDCValidationResult(
            is_valid=False,
            status="invalid_issuer",
            error_message=f"OIDC token issuer does not match configured trusted issuer '{expected_issuer}'."
        )
    except jwt.InvalidAudienceError:
        return OIDCValidationResult(
            is_valid=False,
            status="invalid_audience",
            error_message=f"OIDC token audience does not match configured audience '{expected_audience}'."
        )
    except jwt.InvalidSignatureError:
        return OIDCValidationResult(
            is_valid=False,
            status="invalid_signature",
            error_message="OIDC token cryptographic signature verification failed."
        )
    except jwt.InvalidTokenError as e:
        return OIDCValidationResult(
            is_valid=False,
            status="malformed_token",
            error_message=f"Malformed or unreadable OIDC token: {str(e)}"
        )
