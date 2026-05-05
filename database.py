from sqlalchemy import create_engine
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