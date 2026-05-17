import os
from datetime import datetime
from git import Repo
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

def summarize_commit(commit_msg: str, diff: str) -> str | None:
    """
    Uses LLM to summarize the key architectural/coding decision from a commit.
    Returns None if the commit is trivial and doesn't contain useful memories.
    """
    prompt = f"""
Analyze the following Git commit message and code diff.
Determine if there is a meaningful architectural, design, or coding convention decision being made here.
If it is just a trivial typo fix or routine update with no learning value for an AI agent, reply exactly with "NO_MEMORY".
If it is meaningful, write a concise, standalone summary of the decision, why it was made, and any conventions established.

Commit Message:
{commit_msg}

Diff snippet (truncated to 2000 chars):
{diff[:2000]}
    """
    
    response = client.chat.completions.create(
        model="gpt-4o-mini", # using a smaller model for speed/cost
        messages=[
            {"role": "system", "content": "You are an expert AI software architect extracting semantic memories from git histories."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.0
    )
    
    content = response.choices[0].message.content.strip()
    if content == "NO_MEMORY" or "NO_MEMORY" in content:
        return None
    return content

def ingest_repository(repo_path: str, max_commits: int = 10):
    db = next(get_db())
    repo = Repo(repo_path)
    commits = list(repo.iter_commits('HEAD', max_count=max_commits))
    
    ingested_count = 0
    for commit in commits:
        # Check if already ingested
        existing = db.query(Memory).filter(Memory.commit_hash == commit.hexsha).first()
        if existing:
            continue
            
        try:
            # We compare with its parent to get the diff
            if commit.parents:
                parent = commit.parents[0]
                diff_text = repo.git.diff(parent.hexsha, commit.hexsha)
            else:
                # Initial commit
                diff_text = repo.git.show(commit.hexsha)
                
            summary = summarize_commit(commit.message, diff_text)
            
            if summary:
                # Extract touched files
                touched_files = list(commit.stats.files.keys())
                
                # Get embedding
                embedding = get_embedding(summary)
                
                # Store
                memory = Memory(
                    commit_hash=commit.hexsha,
                    content=summary,
                    file_paths=touched_files,
                    author=f"{commit.author.name} <{commit.author.email}>",
                    date=datetime.fromtimestamp(commit.committed_date),
                    tags=["git_commit"],
                    embedding=embedding
                )
                db.add(memory)
                db.commit()
                ingested_count += 1
                print(f"Ingested commit {commit.hexsha[:7]}: {summary[:50]}...")
        except Exception as e:
            print(f"Failed to process commit {commit.hexsha}: {e}")
            db.rollback()
            
    return ingested_count
