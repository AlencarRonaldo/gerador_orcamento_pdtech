from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from base import Base

DATABASE_URL = "sqlite:///./orcamentos.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models import Orcamento, Categoria, Item
    Base.metadata.create_all(bind=engine)
    # Migrate: add new columns if they don't exist (SQLite doesn't support IF NOT EXISTS for columns)
    migrations = [
        "ALTER TABLE orcamentos ADD COLUMN cliente_cnpj TEXT",
        "ALTER TABLE orcamentos ADD COLUMN cliente_email TEXT",
        "ALTER TABLE orcamentos ADD COLUMN cliente_telefone TEXT",
        "ALTER TABLE orcamentos ADD COLUMN validade_dias INTEGER DEFAULT 7",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists
