"""Testes do sistema de licenciamento HMAC-SHA256."""
import hmac
import hashlib
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import get_db
from models import Orcamento, Categoria, Item, ConfigEmpresa, CatalogoItem, Base
from main import app, LICENCA_SECRET_KEY, _validar_chave_licenca
import main as main_module


import os
from pathlib import Path


@pytest.fixture
def client():
    db_path = "./orcamentos_test.db"
    if os.path.exists(db_path):
        os.remove(db_path)
    
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    TestSession = sessionmaker(bind=engine)

    def override_get_db():
        db = TestSession()
        try:
            yield db
        finally:
            db.close()

    main_module._SESSION_TOKEN = ""
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    main_module._SESSION_TOKEN = ""
    Base.metadata.drop_all(bind=engine)
    engine.dispose()  # Libera o arquivo no Windows
    if os.path.exists("./orcamentos_test.db"):
        try:
            os.remove("./orcamentos_test.db")
        except:
            pass


def _gerar_chave_teste(cnpj_limpo: str) -> str:
    return hmac.new(
        LICENCA_SECRET_KEY.encode(), cnpj_limpo.encode(), hashlib.sha256
    ).hexdigest()


# ── Validação HMAC ──────────────────────────────────────────────────────────────

def test_validar_chave_correta():
    cnpj = "12345678000190"
    chave = _gerar_chave_teste(cnpj)
    assert _validar_chave_licenca(cnpj, chave) is True


def test_validar_chave_incorreta():
    assert _validar_chave_licenca("12345678000190", "chave-errada") is False


def test_validar_chave_cnpj_formatado():
    cnpj_limpo = "12345678000190"
    chave = _gerar_chave_teste(cnpj_limpo)
    assert _validar_chave_licenca("12.345.678/0001-90", chave) is True


# ── Rotas de licença ────────────────────────────────────────────────────────────

def test_status_licenca_rota_publica(client):
    """GET /api/licenca/status deve ser acessível sem cookie de sessão."""
    res = client.get("/api/licenca/status", follow_redirects=False)
    assert res.status_code == 200
    assert "ativada" in res.json()
    assert res.json()["ativada"] is False


def test_ativar_licenca_chave_invalida(client):
    res = client.post(
        "/api/licenca/ativar",
        json={"cnpj": "12345678000190", "chave": "chave-errada"},
    )
    assert res.status_code == 400


def test_ativar_licenca_chave_valida(client):
    cnpj = "12345678000190"
    chave = _gerar_chave_teste(cnpj)
    res = client.post(
        "/api/licenca/ativar",
        json={"cnpj": "12.345.678/0001-90", "chave": chave},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    # Verifica que agora está ativa
    status = client.get("/api/licenca/status").json()
    assert status["ativada"] is True
