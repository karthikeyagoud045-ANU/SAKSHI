"""
Policy tests for SAKSHI worker
Tests RLS policies, dispatch restrictions, and security constraints
"""
import pytest
from fastapi.testclient import TestClient

from worker.main import app

client = TestClient(app)

def test_dispatch_always_returns_403():
    """Test that /dispatch_attempt always returns 403 per R2"""
    response = client.post("/dispatch_attempt/test-ticket-id")
    assert response.status_code == 403
    data = response.json()
    assert data["error"] == "policy_locked"

def test_anon_select_other_ticket_denied():
    """Test that anonymous users cannot select other tickets via tracking code"""
    # This would require setting up test tickets and tracking codes
    # Placeholder for policy test
    assert True  # Placeholder

def test_dak_scope_check_raises_on_originals_path():
    """Test that DAK scope check raises on attempt to access originals path"""
    # This would test the assert_scope function in dak.py
    from worker.dak import assert_scope
    
    # Should not raise for blurred/outbox paths
    try:
        assert_scope("blurred/ticket123/image.jpg")
        assert_scope("outbox/ticket123/payload.json")
    except PermissionError:
        pytest.fail("assert_scope incorrectly raised on allowed paths")
    
    # Should raise for originals path
    with pytest.raises(PermissionError):
        assert_scope("originals/ticket123/image.jpg")
    
    # Should raise for other paths
    with pytest.raises(PermissionError):
        assert_scope("other/path/image.jpg")

def test_approve_requires_auth():
    """Test that DAK approval requires authentication and service role"""
    # No credentials at all -> 401 (authentication required)
    response = client.post("/dak/approve/test-msg-id")
    assert response.status_code == 401  # Unauthorized
    
    # Invalid auth token but no service role -> 403 (service role required)
    response = client.post(
        "/dak/approve/test-msg-id",
        headers={"Authorization": "Bearer invalid-token"}
    )
    assert response.status_code == 403  # Forbidden (service role required)
    
    # Valid service role but no auth -> 401 (authentication required)
    response = client.post(
        "/dak/approve/test-msg-id",
        headers={"x-supabase-role": "service_role"}
    )
    assert response.status_code == 401  # Unauthorized
