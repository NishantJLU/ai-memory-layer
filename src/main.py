import os
from fastapi import FastAPI, HTTPException, BackgroundTasks, Security, Depends
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel
from typing import Optional
from src.database import Base, engine
from src.ingest import ingest_repository
from src.recall import recall_memories
from src.dashboard import router as dashboard_router
from dotenv import load_dotenv

load_dotenv()

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Memory Layer", version="1.0.0")

app.include_router(dashboard_router)

# Security
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def get_api_key(api_key_header: str = Security(api_key_header)):
    expected_key = os.getenv("API_KEY_SECRET", "super-secret-key-change-me-in-prod")
    if api_key_header == expected_key:
        return api_key_header
    raise HTTPException(status_code=403, detail="Could not validate API Key")


class IngestRequest(BaseModel):
    repo_path: str
    project_id: str = "default"
    max_commits: int = 10


class IngestResponse(BaseModel):
    message: str
    status: str


class RecallRequest(BaseModel):
    query: str
    project_id: str = "default"
    limit: int = 5


@app.post("/ingest", response_model=IngestResponse)
async def trigger_ingestion(request: IngestRequest, background_tasks: BackgroundTasks, api_key: str = Depends(get_api_key)):
    """
    Trigger the git parser to ingest a local repository in the background.
    """
    if not os.path.exists(request.repo_path):
        raise HTTPException(status_code=400, detail="Repository path does not exist")

    def _run_ingest():
        print(f"Starting ingestion for {request.repo_path} (Project: {request.project_id})")
        count = ingest_repository(request.repo_path, request.project_id, request.max_commits)
        print(f"Ingestion complete. Added {count} new memories.")

    background_tasks.add_task(_run_ingest)
    return IngestResponse(
        message=f"Started ingestion for {request.repo_path} in the background.",
        status="processing"
    )


@app.post("/recall")
async def recall(request: RecallRequest, api_key: str = Depends(get_api_key)):
    """
    Search memories by semantic similarity, filtered by project.
    """
    memories = recall_memories(request.query, request.project_id, request.limit)
    return {"results": memories}


@app.get("/health")
async def health_check():
    return {"status": "ok", "auth_enabled": True}
