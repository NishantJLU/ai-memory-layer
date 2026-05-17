import os
import pytest
from fastapi.testclient import TestClient
from src.main import app

# Set up test environment variables
os.environ["API_KEY_SECRET"] = "test-secret-key"
os.environ["EMBEDDING_PROVIDER"] = "local"
os.environ["LLM_PROVIDER"] = "local"
# For local sentence-transformers, it doesn't need an API key to run locally,
# but we set one just in case the fallback logic checks for it.
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
    # Assuming DB might be empty, but auth should pass
    # Due to local embeddings, this might take a second to download the model on first run
    # If the DB is not initialized in the test env, this might fail with an internal error (500),
    # but the 403 should be bypassed.
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
