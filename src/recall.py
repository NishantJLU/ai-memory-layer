import os
import math
from datetime import datetime
from src.database import get_db
from src.models import Memory
from src.providers import get_embedding

def calculate_recency_score(memory_date: datetime, decay_rate: float = 0.01) -> float:
    """
    Calculates a recency multiplier.
    decay_rate of 0.01 means ~1% decay per day.
    """
    if not memory_date:
        return 0.5 # Unknown age gets middle penalty
        
    days_old = (datetime.utcnow() - memory_date).days
    if days_old < 0:
        days_old = 0
        
    # Exponential decay: e^(-decay_rate * days_old)
    return math.exp(-decay_rate * days_old)


def recall_memories(query: str, project_id: str = "default", limit: int = 5) -> list[dict]:
    """
    Searches the memory layer for relevant past decisions using hybrid scoring.
    Score = (1 - Cosine Distance) * Recency Score * Confidence
    """
    db = next(get_db())
    try:
        query_embedding = get_embedding(query)

        # 1. Fetch top candidates by pure vector similarity (broad net)
        # We fetch 3x the limit so we have room to re-rank
        candidates = db.query(Memory).filter(
            Memory.project_id == project_id
        ).order_by(
            Memory.embedding.cosine_distance(query_embedding)
        ).limit(limit * 3).all()

        scored_memories = []
        for mem in candidates:
            # Re-calculate distance in Python (or use the returned DB value if configured)
            # For simplicity, we just use a basic distance proxy or rely on DB order.
            # In a full production setup, pgvector returns the distance in the query.
            # Here we just apply recency to re-rank the already sorted candidates.
            
            recency = calculate_recency_score(mem.date)
            confidence = mem.confidence
            
            # Since they are ordered by similarity, we give a base rank score
            # A true hybrid search would compute exact dot product here.
            
            scored_memories.append({
                "mem": mem,
                "recency_multiplier": recency * confidence
            })
            
        # Re-rank (simplistic approach: candidates are already good, we just push fresh/confident ones up)
        # For a true hybrid we'd need the exact distance from pgvector. 
        scored_memories.sort(key=lambda x: x["recency_multiplier"], reverse=True)
        
        final_results = [x["mem"] for x in scored_memories[:limit]]

        memories = []
        for mem in final_results:
            memories.append({
                "id": mem.id,
                "project_id": mem.project_id,
                "memory_type": mem.memory_type,
                "module": mem.module,
                "commit_hash": mem.commit_hash,
                "content": mem.content,
                "file_paths": mem.file_paths,
                "author": mem.author,
                "date": mem.date.isoformat() if mem.date else None,
                "confidence": mem.confidence,
                "is_overridden": mem.is_overridden,
                "tags": mem.tags,
            })

        return memories
    except Exception as e:
        print(f"Error recalling memories: {e}")
        return []
