import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from base import Base
from database import get_db
from models import Orcamento, Categoria, Item
from main import app

# Importar modelos para registar no Base ANTES de criar engine de teste
from models import Orcamento, Categoria, Item


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite:///:memory:", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


PAYLOAD = {
    "cliente_nome": "Empresa Teste",
    "cliente_contato": "Sr. Teste",
    "cliente_endereco": "Rua Teste, 123 – SBC – SP",
    "condicao_pagto": "até 28 dias",
    "descricao_intro": "orçamento de equipamentos de teste",
    "categorias": [
        {
            "titulo": "EQUIPAMENTOS",
            "itens": [
                {
                    "garantia": "12 Meses",
                    "descricao": "Equipamento A",
                    "quantidade": 2,
                    "valor_unitario": 500.00,
                }
            ],
        }
    ],
}


def test_criar_orcamento(client):
    resp = client.post("/orcamentos", json=PAYLOAD)
    assert resp.status_code == 200
    data = resp.json()
    assert data["numero"].startswith("ORC-")
    assert data["cliente_nome"] == "Empresa Teste"
    assert len(data["categorias"]) == 1
    assert data["categorias"][0]["itens"][0]["valor_total"] == pytest.approx(1000.00)


def test_valor_total_calculado_pelo_backend(client):
    resp = client.post("/orcamentos", json=PAYLOAD)
    assert resp.status_code == 200
    item = resp.json()["categorias"][0]["itens"][0]
    assert item["valor_total"] == pytest.approx(2 * 500.00)


def test_listar_orcamentos(client):
    client.post("/orcamentos", json=PAYLOAD)
    resp = client.get("/orcamentos")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


def test_obter_orcamento(client):
    create_resp = client.post("/orcamentos", json=PAYLOAD)
    orc_id = create_resp.json()["id"]
    resp = client.get(f"/orcamentos/{orc_id}")
    assert resp.status_code == 200
    assert resp.json()["id"] == orc_id


def test_obter_orcamento_inexistente(client):
    resp = client.get("/orcamentos/9999")
    assert resp.status_code == 404


def test_numero_sequencial(client):
    r1 = client.post("/orcamentos", json=PAYLOAD)
    r2 = client.post("/orcamentos", json=PAYLOAD)
    assert r1.json()["numero"] != r2.json()["numero"]