import os
from fastapi.testclient import TestClient
from src.main import app

# Set up test environment variables
os.environ["API_KEY_SECRET"] = "test-secret-key"
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["LLM_PROVIDER"] = "local"
os.environ["OPENAI_API_KEY"] = "test-openai-key"

client = TestClient(app)


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "auth_enabled": True}


def test_recall_without_auth():
    response = client.post(
        "/recall",
        json={"query": "test query", "project_id": "test_project"}
    )
    # Should be rejected because missing X-API-Key header
    assert response.status_code == 403
    assert "validate API Key" in response.json()["detail"]


def test_recall_with_invalid_auth():
    response = client.post(
        "/recall",
        json={"query": "test query", "project_id": "test_project"},
        headers={"X-API-Key": "wrong-key"}
    )
    assert response.status_code == 403


def test_recall_with_valid_auth():
    response = client.post(
        "/recall",
        json={"query": "test query", "project_id": "test_project", "limit": 1},
        headers={"X-API-Key": "test-secret-key"}
    )
    # Auth should pass
    assert response.status_code in [200, 500]

    if response.status_code == 200:
        assert "results" in response.json()


def test_ingest_auth():
    response = client.post(
        "/ingest",
        json={"repo_path": "/invalid/path/for/test"},
        headers={"X-API-Key": "test-secret-key"}
    )
    # Auth passes, but path is invalid
    assert response.status_code == 400
    assert "Repository path does not exist" in response.json()["detail"]
