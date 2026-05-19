import asyncio
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from src.database import AsyncSessionLocal
from src.models import Memory
from src.providers import generate_summary, get_embedding


async def consolidate_memories(project_id: str = "default", module: str = None):
    """
    Groups memories by module and distills them into a single high-quality memory.
    """
    async with AsyncSessionLocal() as db:
        # Fetch non-overridden memories
        stmt = select(Memory).filter(
            Memory.project_id == project_id,
            Memory.is_overridden == False
        )
        if module:
            stmt = stmt.filter(Memory.module == module)
            
        result = await db.execute(stmt)
        memories = result.scalars().all()
        
        if len(memories) < 3:
            print(f"Not enough memories to consolidate for {module or 'all modules'}")
            return
            
        context = "\n".join([f"- {m.content}" for m in memories])
        
        prompt = f"""
        You are a senior software architect. Below is a list of individual coding decisions and changes made in the '{module or 'main'}' module.
        Your task is to consolidate these into a single, high-level "Master Memory" that captures the overall architectural evolution and key patterns.
        
        Individual Decisions:
        {context}
        
        Provide a concise but comprehensive summary (3-5 sentences) of the overall state and key decisions for this module.
        """
        
        master_summary = await generate_summary(prompt, "You are a master architect distilling knowledge.")
        
        if master_summary:
            embedding = await get_embedding(master_summary)
            
            # Create the Master Memory
            master_memory = Memory(
                project_id=project_id,
                content_hash=f"master:{module or 'all'}:{len(memories)}",
                content=f"[MASTER CONSOLIDATION] {master_summary}",
                file_paths=[],
                author="Consolidation Worker",
                memory_type="semantic",
                module=module,
                source="consolidation",
                confidence=1.0,
                embedding=embedding,
                tags=["consolidated", f"count:{len(memories)}"]
            )
            
            db.add(master_memory)
            
            # Mark old memories as overridden
            for m in memories:
                m.is_overridden = True
                
            await db.commit()
            print(f"Successfully consolidated {len(memories)} memories into a Master Memory.")

if __name__ == "__main__":
    # Example usage: consolidate the 'auth' module
    asyncio.run(consolidate_memories(module="auth"))
