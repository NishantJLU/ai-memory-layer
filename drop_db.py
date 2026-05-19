import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://memory_user:memory_password@localhost:5433/memory_layer"
)

engine = create_engine(DATABASE_URL)

def drop_tables():
    with engine.connect() as conn:
        print("Dropping memories table...")
        conn.execute(text("DROP TABLE IF EXISTS memories CASCADE"))
        conn.commit()
        print("Done.")

if __name__ == "__main__":
    drop_tables()
