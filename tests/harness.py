import os
import sys
import time
from sqlalchemy import text


# Add src to python path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


from src.database import Base, engine  # noqa: E402
from src.ingest import ingest_repository  # noqa: E402
from src.recall import recall_memories  # noqa: E402


def run_test_harness():
    print("=== AI Memory Layer Test Harness ===")

    # 1. Initialize database (assuming postgres is up via docker-compose)
    print("\n1. Initializing DB Tables...")
    try:
        # Create extension if not exists
        with engine.connect() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            conn.commit()

        Base.metadata.create_all(bind=engine)
        print("Database initialized successfully.")
    except Exception as e:
        print(f"Failed to initialize DB. Is Postgres running? Error: {e}")
        return

    # 2. Setup a dummy git repo for testing or use current directory if it's a git repo
    test_repo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if not os.path.exists(os.path.join(test_repo_path, ".git")):
        print(f"\nNo .git folder found in {test_repo_path}. Please initialize git to test ingestion.")
        print("Run: cd .. && git init && git add . && git commit -m 'Initial commit'")
        return

    # 3. Run ingestion
    print(f"\n2. Running Ingestion on {test_repo_path} (limit 5 commits)...")
    try:
        count = ingest_repository(test_repo_path, max_commits=5)
        print(f"Ingestion complete. Extracted {count} memories.")
    except Exception as e:
        print(f"Ingestion failed: {e}")
        return

    # Wait for DB to settle
    time.sleep(1)

    # 4. Test Recall
    print("\n3. Testing Recall Engine...")
    test_queries = [
        "What are the main database models we defined?",
        "How is the MCP server set up?",
        "Did we make any decisions about the vector database used?"
    ]

    for query in test_queries:
        print(f"\nQuery: '{query}'")
        results = recall_memories(query, limit=2)
        if not results:
            print("  -> No results found.")
        else:
            for r in results:
                print(f"  -> Score Match: {r['id']} (Commit: {r['commit_hash'][:7]})")
                print(f"     {r['content'][:150]}...")

    print("\n=== Test Harness Complete ===")


if __name__ == "__main__":
    # Note: Make sure OPENAI_API_KEY is set in .env before running
    run_test_harness()
