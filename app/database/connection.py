from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from pathlib import Path

# Resolve absolute path to the SQLite database in the project root
# connection.py is at: <project>/app/database/connection.py
# So project root is parents[2]
BASE_DIR = Path(__file__).resolve().parents[2]
DB_PATH = BASE_DIR / "intern_sys.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH.as_posix()}"

# Connect to SQLite
engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False, "timeout": 30}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for models
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
