"""
Test organization creation and tenant ID mapping.
"""

import pytest
from fastapi.testclient import TestClient
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from apps.saas_api.main import app
from packages.agent_platform_client.client import AgentPlatformClient


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def agent_client():
    return AgentPlatformClient(
        base_url="http://localhost:8001",
        api_key="test-key"
    )


def test_tenant_id_mapping():
    """Test that org_id is correctly mapped to tenant_id."""
    client = AgentPlatformClient()
    
    # Test org_ prefix
    org_id = "org_abc123"
    tenant_id = client._format_tenant_id(org_id)
    assert tenant_id == "tenant_abc123"
    
    # Test without prefix
    org_id = "abc123"
    tenant_id = client._format_tenant_id(org_id)
    assert tenant_id == "tenant_abc123"


def test_health_endpoint(client):
    """Test health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert "service" in response.json()
    assert response.json()["service"] == "saas-api"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
