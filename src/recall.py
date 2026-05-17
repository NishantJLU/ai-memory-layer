import os
from openai import OpenAI
from src.database import get_db
from src.models import Memory
from dotenv import load_dotenv

load_dotenv()

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_embedding(text: str) -> list[float]:
    response = client.embeddings.create(
        input=text,
        model="text-embedding-3-small"
    )
    return response.data[0].embedding

def recall_memories(query: str, limit: int = 5) -> list[dict]:
    """
    Searches the memory layer for relevant past decisions using semantic search.
    """
    db = next(get_db())
    try:
        query_embedding = get_embedding(query)
        
        # Use cosine distance for semantic search
        results = db.query(Memory).order_by(
            Memory.embedding.cosine_distance(query_embedding)
        ).limit(limit).all()
        
        memories = []
        for mem in results:
            memories.append({
                "id": mem.id,
                "commit_hash": mem.commit_hash,
                "content": mem.content,
                "file_paths": mem.file_paths,
                "author": mem.author,
                "date": mem.date.isoformat() if mem.date else None,
                "tags": mem.tags,
            })
            
        return memories
    except Exception as e:
        print(f"Error recalling memories: {e}")
        return []
