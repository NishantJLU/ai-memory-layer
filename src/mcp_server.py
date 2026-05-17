import json
from mcp.server.fastmcp import FastMCP
from src.recall import recall_memories

mcp = FastMCP("MemoryLayer")

@mcp.tool()
def recall_memory(query: str, limit: int = 5) -> str:
    """
    Search the AI Memory Layer for past architectural and coding decisions.
    Use this tool when trying to understand why a certain technical choice was made,
    what conventions exist in the codebase, or how past bugs were resolved.
    """
    memories = recall_memories(query, limit)
    
    if not memories:
        return "No relevant memories found."
        
    formatted = []
    for mem in memories:
        formatted.append(
            f"--- Memory {mem['id']} ---\n"
            f"Commit: {mem['commit_hash']}\n"
            f"Author: {mem['author']}\n"
            f"Date: {mem['date']}\n"
            f"Touched Files: {', '.join(mem['file_paths']) if mem['file_paths'] else 'None'}\n\n"
            f"Summary/Decision:\n{mem['content']}\n"
        )
        
    return "\n".join(formatted)

if __name__ == "__main__":
    # Start the MCP stdio server
    mcp.run()
