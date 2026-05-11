import os
import sys
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from base import Base

db_url = os.environ.get("DATABASE_URL", "sqlite:///./orcamentos.db")

print(f"[DB] DATABASE_URL: {db_url[:50]}...", file=sys.stderr)

if db_url.startswith("postgres"):
    # Supabase / Railway PostgreSQL — força sslmode=require
    print("[DB] Using PostgreSQL", file=sys.stderr)
    if "sslmode" not in db_url:
        sep = "&" if "?" in db_url else "?"
        db_url = db_url + sep + "sslmode=require"
    # SQLAlchemy 2.x exige postgresql+psycopg2://
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=0,
        connect_args={"connect_timeout": 15, "sslmode": "require"},
    )
elif db_url.startswith("sqlite:///"):
    actual_path = db_url.replace("sqlite:///", "")
    if not actual_path.startswith("/"):
        if os.path.exists("/data") and os.access("/data", os.W_OK):
            actual_path = "/data/" + os.path.basename(actual_path)
            print("[DB] Using /data volume", file=sys.stderr)
        else:
            actual_path = os.path.join(os.getcwd(), actual_path)
            print("[DB] Using local path", file=sys.stderr)
    path_obj = Path(actual_path).resolve()
    path_obj.parent.mkdir(parents=True, exist_ok=True)
    if not path_obj.exists():
        path_obj.touch()
        print("[DB] Created new database file", file=sys.stderr)
    else:
        print(f"[DB] Database exists, size: {path_obj.stat().st_size} bytes", file=sys.stderr)
    db_url = f"sqlite:///{path_obj}"
    print(f"[DB] Final path: {path_obj}", file=sys.stderr)
    engine = create_engine(db_url, connect_args={"check_same_thread": False})
else:
    print("[DB] Fallback to local SQLite", file=sys.stderr)
    engine = create_engine("sqlite:///./orcamentos.db", connect_args={"check_same_thread": False})

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    from models import Orcamento, Categoria, Item, ConfigEmpresa, CatalogoItem
    Base.metadata.create_all(bind=engine)
    migrations = [
        "ALTER TABLE orcamentos ADD COLUMN cliente_cnpj TEXT",
        "ALTER TABLE orcamentos ADD COLUMN cliente_email TEXT",
        "ALTER TABLE orcamentos ADD COLUMN cliente_telefone TEXT",
        "ALTER TABLE orcamentos ADD COLUMN validade_dias INTEGER DEFAULT 7",
        "ALTER TABLE orcamentos ADD COLUMN desconto_percent REAL DEFAULT 0.0",
        "ALTER TABLE orcamentos ADD COLUMN observacoes_json TEXT",
        "ALTER TABLE orcamentos ADD COLUMN status TEXT DEFAULT 'Aguardando'",
        "ALTER TABLE orcamentos ADD COLUMN uuid_publico TEXT",
        "ALTER TABLE orcamentos ADD COLUMN aceito_em DATETIME",
        "ALTER TABLE orcamentos ADD COLUMN aceito_ip TEXT",
        "ALTER TABLE orcamentos ADD COLUMN assinatura_nome TEXT",
        "ALTER TABLE config_empresa ADD COLUMN session_token TEXT",
        "ALTER TABLE config_empresa ADD COLUMN licenca_chave TEXT",
        "ALTER TABLE config_empresa ADD COLUMN licenca_ativa BOOLEAN DEFAULT 0",
        "ALTER TABLE config_empresa ADD COLUMN numero_base INTEGER DEFAULT 0",
        "ALTER TABLE orcamentos ADD COLUMN cliente_id INTEGER",
        "ALTER TABLE config_empresa ADD COLUMN prazo_equipamentos TEXT",
        "ALTER TABLE config_empresa ADD COLUMN prazo_instalacao TEXT",
        "ALTER TABLE config_empresa ADD COLUMN pagto_info TEXT",
"ALTER TABLE orcamentos ADD COLUMN qtd_visualizacoes INTEGER DEFAULT 0",
        "ALTER TABLE orcamentos ADD COLUMN primeira_abertura_em DATETIME",
        "ALTER TABLE orcamentos ADD COLUMN consultor_nome TEXT",
        "ALTER TABLE config_empresa ADD COLUMN consultor_nome TEXT",
        "ALTER TABLE config_empresa ADD COLUMN consultores_json TEXT",
        "ALTER TABLE config_empresa ADD COLUMN smtp_host TEXT",
        "ALTER TABLE config_empresa ADD COLUMN smtp_port INTEGER DEFAULT 587",
        "ALTER TABLE config_empresa ADD COLUMN smtp_user TEXT",
        "ALTER TABLE config_empresa ADD COLUMN smtp_pass TEXT",
        "ALTER TABLE config_empresa ADD COLUMN notif_email_dest TEXT",
        "ALTER TABLE orcamentos ADD COLUMN assinatura_hash TEXT",
        "ALTER TABLE catalogo_itens ADD COLUMN tipo TEXT DEFAULT 'unidade'",
        "ALTER TABLE catalogo_itens ADD COLUMN largura REAL",
        "ALTER TABLE catalogo_itens ADD COLUMN altura REAL",
        "ALTER TABLE itens ADD COLUMN tipo TEXT DEFAULT 'unidade'",
        "ALTER TABLE itens ADD COLUMN metragem REAL",
        "ALTER TABLE itens ADD COLUMN largura REAL",
        "ALTER TABLE itens ADD COLUMN altura REAL",
        "ALTER TABLE orcamentos ADD COLUMN prazo_equipamentos TEXT",
        "ALTER TABLE orcamentos ADD COLUMN prazo_instalacao TEXT",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists
