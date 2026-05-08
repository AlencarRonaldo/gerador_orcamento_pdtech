import os
import sys
import shutil
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from base import Base

db_url = os.environ.get("DATABASE_URL", "sqlite:///./orcamentos.db")

print(f"[DB] DATABASE_URL: {db_url}", file=sys.stderr)

backup_path = Path("/app/orcamentos.db")

if db_url.startswith("sqlite:///"):
    actual_path = db_url.replace("sqlite:///", "")
    
    if actual_path.startswith("/data/") and os.path.exists("/data") and os.access("/data", os.W_OK):
        volume_path = Path(actual_path)
        print(f"[DB] Using volume /data", file=sys.stderr)
    else:
        volume_path = Path("./orcamentos.db").resolve()
        print(f"[DB] Using local path", file=sys.stderr)
    
    print(f"[DB] Database file: {volume_path}", file=sys.stderr)
    
    if backup_path.exists() and not volume_path.exists():
        print(f"[DB] Restoring from backup", file=sys.stderr)
        shutil.copy(backup_path, volume_path)
    
    volume_path.parent.mkdir(parents=True, exist_ok=True)
    if not volume_path.exists():
        volume_path.touch()
        print(f"[DB] Created new database file", file=sys.stderr)
    else:
        print(f"[DB] Database file exists, size: {volume_path.stat().st_size} bytes", file=sys.stderr)
        if backup_path.exists():
            os.remove(backup_path)
        print(f"[DB] Creating backup at /app", file=sys.stderr)
        shutil.copy(volume_path, backup_path)
    
    db_url = f"sqlite:///{volume_path}"

engine = create_engine(db_url, connect_args={"check_same_thread": False})
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
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists
