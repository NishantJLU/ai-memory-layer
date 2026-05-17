import os
import json
import hashlib
from datetime import datetime
from git import Repo
from src.database import get_db
from src.models import Memory
from src.providers import get_embedding, generate_summary
from sqlalchemy.exc import IntegrityError


def generate_content_hash(project_id: str, commit_hash: str, text: str) -> str:
    """Generate a stable hash to prevent duplicate memory ingestion."""
    raw = f"{project_id}:{commit_hash}:{text}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def detect_conflict(new_memory_text: str, project_id: str) -> str | None:
    """Checks if the new memory contradicts existing memories in the DB."""
    # For a real system, we'd do a quick recall here and ask the LLM.
    # To keep MVP simple but functional, we do a basic semantic search first.
    from src.recall import recall_memories
    # Just a light check of top 2
    past_memories = recall_memories(new_memory_text, project_id=project_id, limit=2)
    if not past_memories:
        return None
        
    context = "\n".join([m['content'] for m in past_memories])
    prompt = f"""
    You are an AI assistant checking for architectural contradictions.
    New Decision: {new_memory_text}
    
    Existing Decisions:
    {context}
    
    Does the New Decision strictly contradict or override the Existing Decisions?
    If yes, explain why in one sentence.
    If no, reply exactly with "NO_CONFLICT".
    """
    
    result = generate_summary(prompt, "You are a strict architectural reviewer.")
    if "NO_CONFLICT" in result:
        return None
    return result


def summarize_commit(commit_msg: str, diff: str) -> dict | None:
    """
    Uses LLM to summarize the key architectural/coding decision from a commit.
    Returns structured JSON with memory_type, module, and content.
    """
    prompt = f"""
Analyze the following Git commit message and code diff.
Determine if there is a meaningful architectural, design, or coding convention decision being made here.
If it is just a trivial typo fix or routine update, reply exactly with '{{"memory": "NO_MEMORY"}}'.
If it is meaningful, return a valid JSON object with the following keys:
- "memory": concise, standalone summary of the decision and why it was made.
- "memory_type": strictly one of ["episodic", "semantic", "procedural"]
- "module": the name of the core module this affects (e.g. "auth", "database", "ui")

Commit Message:
{commit_msg}

Diff snippet (truncated to 2000 chars):
{diff[:2000]}
    """

    content = generate_summary(prompt, "You are an expert AI software architect extracting memories from git histories. Always reply in valid JSON.")
    
    try:
        # Sometimes LLMs wrap JSON in markdown blocks
        if content.startswith("```json"):
            content = content[7:-3]
        elif content.startswith("```"):
            content = content[3:-3]
            
        data = json.loads(content.strip())
        if data.get("memory") == "NO_MEMORY":
            return None
        return data
    except Exception as e:
        print(f"Failed to parse LLM JSON: {e} -> Raw: {content}")
        return None


def ingest_repository(repo_path: str, project_id: str = "default", max_commits: int = 10):
    db = next(get_db())
    repo = Repo(repo_path)
    commits = list(repo.iter_commits('HEAD', max_count=max_commits))

    ingested_count = 0
    for commit in commits:
        try:
            # We compare with its parent to get the diff
            if commit.parents:
                parent = commit.parents[0]
                diff_text = repo.git.diff(parent.hexsha, commit.hexsha)
            else:
                diff_text = repo.git.show(commit.hexsha)

            structured_data = summarize_commit(commit.message, diff_text)

            if structured_data:
                summary = structured_data.get("memory")
                mem_type = structured_data.get("memory_type", "episodic")
                module = structured_data.get("module", "unknown")
                
                content_hash = generate_content_hash(project_id, commit.hexsha, summary)
                
                # Deduplication check
                existing = db.query(Memory).filter(Memory.content_hash == content_hash).first()
                if existing:
                    continue
                
                # Conflict Check
                conflict_reason = detect_conflict(summary, project_id)
                confidence = 0.5 if conflict_reason else 1.0

                touched_files = list(commit.stats.files.keys())
                embedding = get_embedding(summary)

                memory = Memory(
                    project_id=project_id,
                    content_hash=content_hash,
                    commit_hash=commit.hexsha,
                    content=summary,
                    file_paths=touched_files,
                    author=f"{commit.author.name} <{commit.author.email}>",
                    date=datetime.fromtimestamp(commit.committed_date),
                    memory_type=mem_type,
                    module=module,
                    source="git",
                    confidence=confidence,
                    tags=["git_commit"] + (["conflict_flagged"] if conflict_reason else []),
                    embedding=embedding
                )
                db.add(memory)
                db.commit()
                ingested_count += 1
                print(f"Ingested commit {commit.hexsha[:7]}: {summary[:50]}...")
                if conflict_reason:
                    print(f"  -> WARNING: Conflict detected: {conflict_reason}")
                    
        except IntegrityError:
            # DB level deduplication catch
            db.rollback()
        except Exception as e:
            print(f"Failed to process commit {commit.hexsha}: {e}")
            db.rollback()

    return ingested_count
