from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Float, Boolean, UniqueConstraint, Computed, Index
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from src.database import Base


class Memory(Base):
    __tablename__ = "memories"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(String(100), index=True, nullable=False, default="default")
    user_id = Column(String(100), index=True, nullable=True)

    content_hash = Column(String(64), index=True, nullable=False)  # For deduplication (SHA256)
    commit_hash = Column(String(40), index=True, nullable=True)  # Provenance

    content = Column(Text, nullable=False)  # The summarized decision
    file_paths = Column(JSON, nullable=False)  # List of files touched
    author = Column(String(255), nullable=True)
    date = Column(DateTime, default=datetime.utcnow)

    # Taxonomy Metadata
    memory_type = Column(String(50), nullable=False, default="semantic") # episodic, semantic, procedural
    module = Column(String(100), nullable=True) # e.g. auth, payments
    source = Column(String(50), nullable=False, default="git") # git, pr, conversation, direct
    confidence = Column(Float, nullable=False, default=1.0) # 0.0 to 1.0
    is_overridden = Column(Boolean, nullable=False, default=False)
    
    tags = Column(JSON, nullable=True)

    # Note: Using 384 for local models (all-MiniLM-L6-v2), or 1536 for OpenAI.
    embedding = Column(Vector, nullable=False)
    
    # TSVector for full-text search (BM25 equivalent in Postgres)
    # We use Computed to auto-populate it from the content
    search_vector = Column(TSVECTOR, Computed("to_tsvector('english', content)", persisted=True))

    __table_args__ = (
        UniqueConstraint('project_id', 'content_hash', name='uq_project_content_hash'),
        Index('ix_memories_search_vector', 'search_vector', postgresql_using='gin'),
    )
