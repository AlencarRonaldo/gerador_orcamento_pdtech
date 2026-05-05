import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from base import Base
from models import Orcamento, Categoria, Item


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture
def orcamento_exemplo(db):
    """Cria um orçamento completo de exemplo no banco de teste."""
    orc = Orcamento(
        numero="ORC-2026-001",
        cliente_nome="Complexo de Saude",
        cliente_contato="Sr. Eduardo Nobuo",
        cliente_endereco="Centro – São Bernardo do Campo - SP",
        condicao_pagto="até 28 dias",
        descricao_intro="orçamento de 15 cameras Intelbras",
    )
    db.add(orc)
    db.flush()

    cat = Categoria(orcamento_id=orc.id, titulo="EQUIPAMENTOS CAMERAS", ordem=0)
    db.add(cat)
    db.flush()

    item = Item(
        categoria_id=cat.id,
        garantia="6 Meses",
        descricao="CAMERA IP VIP 1230D 2.8MM ITB",
        quantidade=15,
        valor_unitario=355.18,
        valor_total=15 * 355.18,
    )
    db.add(item)
    db.commit()
    db.refresh(orc)
    return orc