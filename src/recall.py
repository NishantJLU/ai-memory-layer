import math
from datetime import datetime, timezone
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from src.models import Memory
from src.providers import get_embedding


def calculate_recency_score(memory_date: datetime, decay_rate: float = 0.01) -> float:
    """
    Calculates a recency multiplier.
    decay_rate of 0.01 means ~1% decay per day.
    """
    if not memory_date:
        return 0.5  # Unknown age gets middle penalty

    # Ensure memory_date is timezone-aware if it's not already
    if memory_date.tzinfo is None:
        memory_date = memory_date.replace(tzinfo=timezone.utc)
        
    days_old = (datetime.now(timezone.utc) - memory_date).days
    if days_old < 0:
        days_old = 0

    # Exponential decay: e^(-decay_rate * days_old)
    return math.exp(-decay_rate * days_old)


from src.cache import get_cached_recall, set_cached_recall


async def recall_memories(query: str, project_id: str = "default", limit: int = 5, db: AsyncSession = None) -> list[dict]:
    """
    Searches the memory layer for relevant past decisions using HYBRID search.
    Combining Vector Similarity (pgvector) + Full-Text Search (tsvector/BM25)
    + Recency Decay.
    """
    # Check Cache First
    cached = get_cached_recall(project_id, query)
    if cached:
        return cached[:limit]

    if db is None:
        from src.database import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            results = await _recall_logic(query, project_id, limit, session)
    else:
        results = await _recall_logic(query, project_id, limit, db)
    
    # Cache the results
    set_cached_recall(project_id, query, results)
    return results


async def _recall_logic(query: str, project_id: str, limit: int, db: AsyncSession) -> list[dict]:
    try:
        query_embedding = await get_embedding(query)

        # Build Full-Text Query
        ft_query = func.websearch_to_tsquery('english', query)

        # Broad Fetch: Candidates from either Vector or Full-Text Match
        # Calculate scores in the query for performance
        vector_score = (1 - Memory.embedding.cosine_distance(query_embedding))
        text_score = func.ts_rank(Memory.search_vector, ft_query)

        # Filter by project and (vector similarity OR keyword match)
        stmt = select(
            Memory,
            vector_score.label("v_score"),
            text_score.label("t_score")
        ).filter(
            Memory.project_id == project_id
        ).filter(
            or_(
                Memory.embedding.cosine_distance(query_embedding) < 0.5,  # High vector match
                Memory.search_vector.op('@@')(ft_query)                  # OR Keyword match
            )
        )
        
        result = await db.execute(stmt)
        candidates = result.all()

        scored_memories = []
        for mem, v_s, t_s in candidates:
            recency = calculate_recency_score(mem.date)
            confidence = mem.confidence

            # Hybrid Calculation
            # Vector (0.7) and Keywords (0.3)
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
        import traceback
        traceback.print_exc()
        return []
