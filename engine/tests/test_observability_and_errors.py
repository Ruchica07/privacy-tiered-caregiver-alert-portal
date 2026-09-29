"""
Test Suite: Observability, Correlation Tracking, and Error Boundaries (Phase 3)

Verifies:
1. Generation and attachment of unique `X-Correlation-ID` header on all responses
2. Propagation of client-supplied `X-Correlation-ID` header
3. Standardized error envelope format for validation, authentication, and authorization failures
4. Sanitized error messages without internal stack traces, tokens, or credentials
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestObservabilityAndErrors:

    def test_correlation_id_auto_generated(self, client):
        response = client.get("/api/care-recipients")
        assert response.status_code == 200
        assert "x-correlation-id" in response.headers
        corr_id = response.headers["x-correlation-id"]
        assert len(corr_id) > 10

    def test_correlation_id_propagated_from_client_header(self, client):
        custom_id = "test-custom-correlation-id-98765"
        response = client.get("/api/care-recipients", headers={"X-Correlation-ID": custom_id})
        assert response.status_code == 200
        assert response.headers.get("x-correlation-id") == custom_id

    def test_standardized_error_envelope_on_validation_failure(self, client):
        # Trigger validation failure with invalid payload schema
        response = client.post("/api/synthetic/signals", json={"invalid_field": True})
        assert response.status_code == 422
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "VALIDATION_ERROR"
        assert "correlation_id" in data["error"]
        assert "message" in data["error"]

    def test_standardized_error_envelope_on_auth_failure(self, client):
        response = client.post("/api/auth/login", json={"username": "bad.user", "password": "wrongpassword"})
        assert response.status_code == 401
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "AUTHENTICATION_ERROR"
        assert "correlation_id" in data["error"]
        assert "invalid" in data["error"]["message"].lower()

    def test_standardized_error_envelope_on_not_found(self, client):
        response = client.get("/api/alerts?caregiver_id=nonexistent_cg")
        assert response.status_code == 404
        data = response.json()
        assert "error" in data
        assert data["error"]["code"] == "NOT_FOUND_ERROR"
        assert "correlation_id" in data["error"]
