import pytest
import os
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import String, Text, JSON
from unittest.mock import MagicMock

# Mock Postgres-specific types for SQLite tests
import sqlalchemy.dialects.postgresql as pg_dialect
pg_dialect.TSVECTOR = String

import pgvector.sqlalchemy
pgvector.sqlalchemy.Vector = String # Simplified for SQLite

from sqlalchemy import Computed
def mock_computed(sql, **kwargs):
    return None # SQLite doesn't need the Postgres computed logic in tests
# We can't easily mock Computed as it's a class, but we can try to intercept its __init__
import sqlalchemy
sqlalchemy.Computed = lambda *args, **kwargs: None

from src.main import app, get_api_key
from src.database import Base, get_async_db
from src.config import settings

# Override settings for testing
settings.API_KEY_SECRET = "test-secret-key"
settings.EMBEDDING_PROVIDER = "local"
settings.LLM_PROVIDER = "local"

# Use in-memory SQLite for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"
test_engine = create_async_engine(TEST_DATABASE_URL)
TestAsyncSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def override_get_async_db():
    async with TestAsyncSessionLocal() as session:
        yield session

app.dependency_overrides[get_async_db] = override_get_async_db


@pytest.fixture(autouse=True, scope="module")
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "auth_enabled": True}


@pytest.mark.asyncio
async def test_recall_without_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/recall",
            json={"query": "test query", "project_id": "test_project"}
        )
    # Should be rejected because missing X-API-Key header
    assert response.status_code == 403
    assert "validate API Key" in response.json()["detail"]


@pytest.mark.asyncio
async def test_recall_with_invalid_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/recall",
            json={"query": "test query", "project_id": "test_project"},
            headers={"X-API-Key": "wrong-key"}
        )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_recall_with_valid_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/recall",
            json={"query": "test query", "project_id": "test_project", "limit": 1},
            headers={"X-API-Key": "test-secret-key"}
        )
    # Auth should pass
    assert response.status_code == 200
    assert "results" in response.json()


@pytest.mark.asyncio
async def test_ingest_auth():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/ingest",
            json={"repo_path": "/invalid/path/for/test"},
            headers={"X-API-Key": "test-secret-key"}
        )
    # Auth passes, but path is invalid
    assert response.status_code == 400
    assert "Repository path does not exist" in response.json()["detail"]
