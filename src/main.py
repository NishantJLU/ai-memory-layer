from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Optional
from src.database import Base, engine, get_db
from src.ingest import ingest_repository
from src.recall import recall_memories

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="AI Memory Layer", version="1.0.0")

class IngestRequest(BaseModel):
    repo_path: str
    max_commits: int = 10

class IngestResponse(BaseModel):
    message: str
    status: str

class RecallRequest(BaseModel):
    query: str
    limit: int = 5

@app.post("/ingest", response_model=IngestResponse)
async def trigger_ingestion(request: IngestRequest, background_tasks: BackgroundTasks):
    """
    Trigger the git parser to ingest a local repository in the background.
    """
    import os
    if not os.path.exists(request.repo_path):
        raise HTTPException(status_code=400, detail="Repository path does not exist")
        
    def _run_ingest():
        print(f"Starting ingestion for {request.repo_path}")
        count = ingest_repository(request.repo_path, request.max_commits)
        print(f"Ingestion complete. Added {count} new memories.")
        
    background_tasks.add_task(_run_ingest)
    return IngestResponse(
        message=f"Started ingestion for {request.repo_path} in the background.",
        status="processing"
    )

@app.post("/recall")
async def recall(request: RecallRequest):
    """
    Search memories by semantic similarity.
    """
    memories = recall_memories(request.query, request.limit)
    return {"results": memories}

@app.get("/health")
async def health_check():
    return {"status": "ok"}
