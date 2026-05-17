import os
import math
from datetime import datetime
from sqlalchemy import func, or_
from src.database import get_db
from src.models import Memory
from src.providers import get_embedding


def calculate_recency_score(memory_date: datetime, decay_rate: float = 0.01) -> float:
    """
    Calculates a recency multiplier.
    decay_rate of 0.01 means ~1% decay per day.
    """
    if not memory_date:
        return 0.5  # Unknown age gets middle penalty

    days_old = (datetime.utcnow() - memory_date).days
    if days_old < 0:
        days_old = 0

    # Exponential decay: e^(-decay_rate * days_old)
    return math.exp(-decay_rate * days_old)


def recall_memories(query: str, project_id: str = "default", limit: int = 5) -> list[dict]:
    """
    Searches the memory layer for relevant past decisions using HYBRID search.
    Combining Vector Similarity (pgvector) + Full-Text Search (tsvector/BM25)
    + Recency Decay.
    """
    db = next(get_db())
    try:
        query_embedding = get_embedding(query)

        # Build Full-Text Query
        # We transform the query into a websearch_to_tsquery or plainto_tsquery
        ft_query = func.websearch_to_tsquery('english', query)

        # 1. Broad Fetch: Candidates from either Vector or Full-Text Match
        # In Postgres, we can combine these scores.
        # We fetch 3x limit to re-rank.
        
        # Calculate scores in the query for performance
        # Vector score: 1 - distance
        vector_score = (1 - Memory.embedding.cosine_distance(query_embedding))
        # Text score: ts_rank (normalized 0 to 1)
        text_score = func.ts_rank(Memory.search_vector, ft_query)

        # Filter by project and (vector similarity OR keyword match)
        candidates = db.query(
            Memory,
            vector_score.label("v_score"),
            text_score.label("t_score")
        ).filter(
            Memory.project_id == project_id
        ).filter(
            or_(
                Memory.embedding.cosine_distance(query_embedding) < 0.5, # High vector match
                Memory.search_vector.op('@@')(ft_query)                 # OR Keyword match
            )
        ).all()

        scored_memories = []
        for mem, v_s, t_s in candidates:
            recency = calculate_recency_score(mem.date)
            confidence = mem.confidence
            
            # Hybrid Calculation (RRF or simple weighted average)
            # We give Vector a higher weight (0.7) and Keywords (0.3)
            # Then apply recency and confidence.
            base_score = (v_s * 0.7) + (t_s * 0.3)
            final_score = base_score * recency * confidence
            
            scored_memories.append({
                "mem": mem,
                "score": final_score
            })
            
        # Re-rank by combined score
        scored_memories.sort(key=lambda x: x["score"], reverse=True)
        
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
