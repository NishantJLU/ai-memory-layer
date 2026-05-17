from mcp.server.fastmcp import FastMCP
from src.recall import recall_memories
from src.database import get_db
from src.models import Memory
from src.providers import get_embedding
from src.ingest import generate_content_hash

mcp = FastMCP("MemoryLayer")


@mcp.tool()
def recall_memory(query: str, project_id: str = "default", limit: int = 5) -> str:
    """
    Search the AI Memory Layer for past architectural and coding decisions.
    Use this tool when trying to understand why a certain technical choice was made,
    what conventions exist in the codebase, or how past bugs were resolved.
    """
    memories = recall_memories(query, project_id, limit)

    if not memories:
        return "No relevant memories found."

    formatted = []
    for mem in memories:
        status = "[OVERRIDDEN] " if mem.get('is_overridden') else ""
        formatted.append(
            f"--- Memory {mem['id']} {status}---\n"
            f"Type: {mem['memory_type']} | Module: {mem['module']}\n"
            f"Date: {mem['date']} | Confidence: {mem.get('confidence', 1.0)}\n"
            f"Touched Files: {', '.join(mem['file_paths']) if mem['file_paths'] else 'None'}\n\n"
            f"Summary/Decision:\n{mem['content']}\n"
        )

    return "\n".join(formatted)


@mcp.tool()
def store_memory(content: str, memory_type: str, module: str, project_id: str = "default") -> str:
    """
    Actively save a new architectural decision, bug fix, or pattern mid-conversation.
     memory_type must be one of: episodic, semantic, procedural.
    """
    db = next(get_db())
    try:
        content_hash = generate_content_hash(project_id, "direct", content)

        # Check if already exists
        existing = db.query(Memory).filter(Memory.content_hash == content_hash).first()
        if existing:
            return f"Memory already exists with ID {existing.id}"

        embedding = get_embedding(content)

        memory = Memory(
            project_id=project_id,
            content_hash=content_hash,
            content=content,
            file_paths=[],
            author="AI Agent",
            memory_type=memory_type,
            module=module,
            source="conversation",
            confidence=1.0,
            embedding=embedding
        )
        db.add(memory)
        db.commit()
        return f"Successfully stored memory with ID {memory.id}"
    except Exception as e:
        db.rollback()
        return f"Failed to store memory: {e}"


@mcp.tool()
def list_recent_memories(project_id: str = "default", module: str = None, limit: int = 10) -> str:
    """
    Surface what is known about a specific module sorted by recency.
    """
    db = next(get_db())
    try:
        query = db.query(Memory).filter(Memory.project_id == project_id)
        if module:
            query = query.filter(Memory.module == module)

        memories = query.order_by(Memory.date.desc()).limit(limit).all()

        if not memories:
            return "No recent memories found."

        formatted = [f"Recent Memories for {module or 'all modules'}:"]
        for mem in memories:
            formatted.append(f"- [{mem.date.strftime('%Y-%m-%d')}] (ID: {mem.id}) {mem.content[:100]}...")

        return "\n".join(formatted)
    except Exception as e:
        return f"Error listing memories: {e}"


@mcp.tool()
def flag_contradiction(memory_id: int, reason: str) -> str:
    """
    Let the agent report a conflict or state that a memory is obsolete.
    This lowers the confidence of the memory and tags it.
    """
    db = next(get_db())
    try:
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            return f"Memory ID {memory_id} not found."

        memory.confidence = max(0.1, memory.confidence - 0.5)

        # Append to tags safely
        current_tags = list(memory.tags) if memory.tags else []
        current_tags.append(f"conflict: {reason}")
        memory.tags = current_tags

        db.commit()
        return f"Memory {memory_id} flagged for contradiction. Confidence lowered."
    except Exception as e:
        db.rollback()
        return f"Failed to flag contradiction: {e}"


if __name__ == "__main__":
    # Start the MCP stdio server
    mcp.run()
