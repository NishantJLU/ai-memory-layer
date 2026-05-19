import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models import Memory
from src.database import Base
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://memory_user:memory_password@localhost:5433/memory_layer"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)

def dump_memories():
    db = SessionLocal()
    memories = db.query(Memory).all()
    print(f"Total memories: {len(memories)}")
    for m in memories:
        print(f"ID: {m.id}, Project: {m.project_id}, Content: {m.content[:50]}...")
    db.close()

if __name__ == "__main__":
    dump_memories()
