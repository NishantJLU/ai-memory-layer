from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, text
from pgvector.sqlalchemy import Vector
from src.database import Base
from datetime import datetime

class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    commit_hash = Column(String(40), index=True, nullable=True) # Provenance
    content = Column(Text, nullable=False) # The summarized decision
    file_paths = Column(JSON, nullable=False) # List of files touched
    author = Column(String(255), nullable=True)
    date = Column(DateTime, default=datetime.utcnow)
    tags = Column(JSON, nullable=True) # E.g., module name, decision type
    # text-embedding-3-small generates 1536 dimensional vectors by default
    embedding = Column(Vector(1536), nullable=False)
