import pytest
import secrets
import os
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timezone

from main import app
from database import get_db
from base import Base
from models import ConfigEmpresa, Orcamento, CatalogoItem

# Banco isolado por função
DB_FILE = "orcamentos_test_saas_final.db"
SQLALCHEMY_DATABASE_URL = f"sqlite:///./{DB_FILE}"

@pytest.fixture
def db_session():
    engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = TestingSessionLocal()
    cfg = ConfigEmpresa(
        id=1,
        empresa_nome="Test Empresa",
        login_email="admin@admin.com",
        login_senha="admin123",
        licenca_ativa=True
    )
    db.add(cfg)
    db.commit()
    db.close()
    
    yield engine
    
    engine.dispose()
    if os.path.exists(DB_FILE):
        try:
            os.remove(DB_FILE)
        except:
            pass

@pytest.fixture
def client(db_session):
    def override_get_db():
        TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=db_session)
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    app.dependency_overrides[get_db] = override_get_db
    import main
    main._SESSION_TOKEN = ""
    
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()

def test_login_fluxo_completo(client):
    # 1. Login com sucesso
    res = client.post("/api/login", json={"email": "admin@admin.com", "password": "admin123"})
    assert res.status_code == 200
    
    # 2. Acesso protegido
    res = client.get("/api/config")
    assert res.status_code == 200
    assert res.json()["empresa_nome"] == "Test Empresa"

def test_seguranca_alterar_senha(client):
    # 1. Login
    client.post("/api/login", json={"email": "admin@admin.com", "password": "admin123"})
    
    # 2. Altera senha (isso deve invalidar o token atual)
    res = client.put("/api/config", json={
        "empresa_nome": "Test Empresa",
        "login_senha": "nova_senha_999"
    })
    assert res.status_code == 200
    
    # 3. Tenta acessar com a sessão antiga (deve ser 401)
    res = client.get("/api/config")
    assert res.status_code == 401

    # 4. Novo login com a nova senha
    res = client.post("/api/login", json={"email": "admin@admin.com", "password": "nova_senha_999"})
    assert res.status_code == 200

def test_workflow_orcamento_completo(client):
    # Login
    client.post("/api/login", json={"email": "admin@admin.com", "password": "admin123"})
    
    # Criar orçamento com TODOS os campos obrigatórios
    payload = {
        "cliente_nome": "Empresa Teste",
        "cliente_cnpj": "12.345.678/0001-00",
        "cliente_contato": "Sr. Teste",
        "cliente_endereco": "Rua dos Testes, 123",
        "cliente_email": "teste@teste.com.br",
        "cliente_telefone": "(11) 99999-9999",
        "condicao_pagto": "30 dias",
        "descricao_intro": "Apresentação do teste",
        "categorias": [
            {
                "titulo": "Hardware",
                "itens": [
                    {"descricao": "Teclado", "quantidade": 10, "valor_unitario": 50.0, "garantia": "12 meses"}
                ]
            }
        ]
    }
    res = client.post("/orcamentos", json=payload)
    if res.status_code != 200:
        print(res.json()) # Debug se falhar
    assert res.status_code == 200
    
    data = res.json()
    orc_id = data["id"]
    orc_uuid = data["uuid_publico"]
    
    # Verificar acesso público (SEM login)
    public_client = TestClient(app) # Novo cliente sem cookies
    res = public_client.get(f"/p/{orc_uuid}")
    assert res.status_code == 200
    assert "Empresa Teste" in res.text
    
    # Aceite público
    res = public_client.post(f"/api/p/{orc_uuid}/aceitar", json={"assinatura_nome": "Assinatura de Teste", "assinatura_cpf": "12345678901", "assinatura_telefone": "11999999999"})
    assert res.status_code == 200
    
    # Verificar no admin (com o cliente logado)
    res = client.get(f"/orcamentos/{orc_id}")
    assert res.json()["status"] == "Aprovado"

def test_catalogo_crud(client):
    client.post("/api/login", json={"email": "admin@admin.com", "password": "admin123"})
    
    # Adicionar item
    res = client.post("/api/catalogo", json={
        "categoria": "Infraestrutura",
        "descricao": "Cabo de Rede Cat6",
        "preco": 5.50,
        "garantia": "Vida útil",
        "ativo": True,
        "ordem": 1
    })
    assert res.status_code == 200
    item_id = res.json()["id"]
    
    # Listar e validar agrupamento
    res = client.get("/api/catalogo")
    assert "Infraestrutura" in res.json()
    
    # Deletar
    res = client.delete(f"/api/catalogo/{item_id}")
    assert res.status_code == 200
