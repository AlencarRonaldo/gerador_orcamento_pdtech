import os

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from base import Base

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./orcamentos.db")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
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
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                pass  # Column already exists
