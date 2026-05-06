import base64
import hashlib
import hmac
import json
import secrets
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import Response, RedirectResponse
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import create_tables, get_db
from models import (
    Categoria,
    CatalogoItem,
    CatalogoItemInput,
    CatalogoItemOutput,
    ConfigEmpresa,
    ConfigEmpresaInput,
    Item,
    Orcamento,
    OrcamentoInput,
    OrcamentoOutput,
)

app = FastAPI(title="Gerador de Orçamentos")
templates = Jinja2Templates(directory="templates")

def _formatar_moeda(valor):
    formatted = f"{valor:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")

templates.env.filters["moeda"] = _formatar_moeda

# SESSION_TOKEN é carregado do banco no startup (persiste entre reinicializações)
_SESSION_TOKEN: str = ""

def _get_session_token(db: Session = None) -> str:
    """Retorna o token de sessão persistente do banco."""
    global _SESSION_TOKEN
    if _SESSION_TOKEN:
        return _SESSION_TOKEN
    if db is None:
        db_factory = app.dependency_overrides.get(get_db, get_db)
        db_gen = db_factory()
        db = next(db_gen)
        close_gen = db_gen
    else:
        close_gen = None
    try:
        cfg = db.query(ConfigEmpresa).first()
        if cfg and cfg.session_token:
            _SESSION_TOKEN = cfg.session_token
        else:
            _SESSION_TOKEN = secrets.token_urlsafe(32)
            if cfg:
                cfg.session_token = _SESSION_TOKEN
                db.commit()
        return _SESSION_TOKEN
    finally:
        if close_gen:
            try:
                next(close_gen)
            except StopIteration:
                pass


def _get_config(db: Session) -> ConfigEmpresa:
    """Retorna o registro de config ou cria um padrão se não existir."""
    cfg = db.query(ConfigEmpresa).first()
    if not cfg:
        cfg = ConfigEmpresa(id=1)
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def _config_to_dict(cfg: ConfigEmpresa) -> dict:
    import json as _json
    obs = _json.loads(cfg.obs_padrao_json) if cfg.obs_padrao_json else [
        "Instalação: mediante orçamento adicional",
        "Garantia: fabricante (equipamentos) + 12 meses (mão de obra)",
        "Suporte pós-venda: 30 dias após a conclusão dos serviços",
    ]
    return {
        "empresa_nome": cfg.empresa_nome or "Minha Empresa",
        "empresa_cnpj": cfg.empresa_cnpj or "",
        "empresa_telefone": cfg.empresa_telefone or "",
        "empresa_email": cfg.empresa_email or "",
        "empresa_endereco": cfg.empresa_endereco or "",
        "empresa_cidade": cfg.empresa_cidade or "",
        "empresa_slogan": cfg.empresa_slogan or "",
        "empresa_diferenciais": cfg.empresa_diferenciais or "",
        "empresa_logo_b64": cfg.empresa_logo_b64 or "",
        "cor_primaria": cfg.cor_primaria or "#0097b2",
        "obs_padrao": obs,
        "cond_pagto_opcao1": cfg.cond_pagto_opcao1 or "50% de entrada + 50% em 30 dias",
        "cond_pagto_opcao3_desconto": cfg.cond_pagto_opcao3_desconto or "5%",
        "login_email": cfg.login_email or "",
        "numero_base": cfg.numero_base or 0,
    }


class LoginData(BaseModel):
    email: str
    password: str

@app.post("/api/login")
def login_api(data: LoginData, response: Response, db: Session = Depends(get_db)):
    cfg = _get_config(db)
    login_email = cfg.login_email or "admin@admin.com"
    login_senha = cfg.login_senha or "admin123"
    correct_username = secrets.compare_digest(data.email, login_email)
    correct_password = secrets.compare_digest(data.password, login_senha)
    
    if correct_username and correct_password:
        token = _get_session_token(db)
        response.set_cookie(key="session_token", value=token, httponly=True, max_age=86400 * 7)
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Credenciais inválidas")

@app.post("/api/logout")
def logout_api(response: Response):
    response.delete_cookie("session_token")
    return {"ok": True}

ROTAS_PUBLICAS = {
    "/login.html", "/api/login", "/favicon.ico",
    "/ativacao.html", "/api/licenca/status", "/api/licenca/ativar",
}


@app.get("/login.html")
def login_page(request: Request, db: Session = Depends(get_db)):
    cfg = _get_config(db)
    return templates.TemplateResponse("login.html", {
        "request": request,
        "config": _config_to_dict(cfg)
    })


LICENCA_SECRET_KEY = "orcamentos-saas-secret-2026-xyz"


def _validar_chave_licenca(cnpj: str, chave: str) -> bool:
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())
    esperado = hmac.new(
        LICENCA_SECRET_KEY.encode(), cnpj_limpo.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, chave.strip())


def _licenca_ativa_db() -> bool:
    # Respeita dependency_overrides (para testes com DB in-memory)
    db_factory = app.dependency_overrides.get(get_db, get_db)
    db_gen = db_factory()
    db = next(db_gen)
    try:
        cfg = db.query(ConfigEmpresa).first()
        return bool(cfg and cfg.licenca_ativa)
    except Exception:
        return False
    finally:
        try:
            next(db_gen)
        except StopIteration:
            pass


class LicencaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in ROTAS_PUBLICAS
            or path.startswith("/p/")
            or path.startswith("/api/p/")
            or path.startswith("/static/")
        ):
            return await call_next(request)
        if not _licenca_ativa_db():
            if path.endswith(".html") or path == "/":
                return RedirectResponse(url="/ativacao.html", status_code=303)
            return Response(content="Licença inativa", status_code=403)
        return await call_next(request)


class SessaoMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in ROTAS_PUBLICAS
            or path.startswith("/p/")
            or path.startswith("/api/p/")
            or path.startswith("/static/")
        ):
            return await call_next(request)
        token = request.cookies.get("session_token")
        if not token or not secrets.compare_digest(token, _get_session_token()):
            # Se for uma requisição de página (HTML ou raiz), redireciona
            # Se for API ou outro recurso, retorna 401
            is_page = path == "/" or "." not in path or path.endswith(".html")
            if is_page and not path.startswith("/api/"):
                return RedirectResponse(url="/login.html", status_code=303)
            return Response(content="Não autorizado", status_code=401)
        return await call_next(request)


# SessaoMiddleware registrado primeiro (executa por último).
# LicencaMiddleware registrado depois (executa primeiro).
app.add_middleware(SessaoMiddleware)
app.add_middleware(LicencaMiddleware)

@app.on_event("startup")
def startup():
    create_tables()
    from database import SessionLocal
    db = SessionLocal()
    try:
        cfg = db.query(ConfigEmpresa).first()
        if not cfg:
            # Primeira execução: semeia com dados da instalação atual
            cfg = ConfigEmpresa(
                id=1,
                empresa_nome="Minha Empresa",
                login_email="admin@admin.com",
                login_senha="admin123",
                cor_primaria="#0097b2",
            )
            db.add(cfg)
            db.commit()
    finally:
        db.close()


def _gerar_numero(db: Session) -> str:
    cfg = _get_config(db)
    ano = datetime.now(timezone.utc).year
    base = cfg.numero_base or 0
    count = db.query(Orcamento).count() + 1 + base
    return f"ORC-{ano}-{count:03d}"


def _orc_to_dict(orc: Orcamento) -> dict:
    """Converte ORM para dict incluindo campos calculados."""
    obs = json.loads(orc.observacoes_json) if orc.observacoes_json else None
    return {
        "id": orc.id,
        "numero": orc.numero,
        "criado_em": orc.criado_em.isoformat(),
        "cliente_nome": orc.cliente_nome,
        "cliente_contato": orc.cliente_contato,
        "cliente_endereco": orc.cliente_endereco,
        "cliente_cnpj": orc.cliente_cnpj,
        "cliente_email": orc.cliente_email,
        "cliente_telefone": orc.cliente_telefone,
        "condicao_pagto": orc.condicao_pagto,
        "descricao_intro": orc.descricao_intro,
        "validade_dias": orc.validade_dias or 7,
        "desconto_percent": orc.desconto_percent or 0.0,
        "observacoes_custom": obs,
        "status": orc.status or "Aguardando",
        "uuid_publico": orc.uuid_publico,
        "aceito_em": orc.aceito_em.isoformat() if orc.aceito_em else None,
        "assinatura_nome": orc.assinatura_nome,
        "categorias": [
            {
                "id": cat.id,
                "titulo": cat.titulo,
                "ordem": cat.ordem,
                "itens": [
                    {
                        "id": item.id,
                        "garantia": item.garantia,
                        "descricao": item.descricao,
                        "quantidade": item.quantidade,
                        "valor_unitario": item.valor_unitario,
                        "valor_total": item.valor_total,
                    }
                    for item in cat.itens
                ],
            }
            for cat in orc.categorias
        ],
    }


def _criar_categorias(db: Session, orcamento_id: int, categorias_data):
    for ordem, cat_data in enumerate(categorias_data):
        categoria = Categoria(
            orcamento_id=orcamento_id,
            titulo=cat_data.titulo,
            ordem=ordem,
        )
        db.add(categoria)
        db.flush()
        for item_data in cat_data.itens:
            db.add(Item(
                categoria_id=categoria.id,
                garantia=item_data.garantia,
                descricao=item_data.descricao,
                quantidade=item_data.quantidade,
                valor_unitario=item_data.valor_unitario,
                valor_total=item_data.quantidade * item_data.valor_unitario,
            ))


# ── Criar orçamento ──────────────────────────────────────────────────────────

@app.post("/orcamentos")
def criar_orcamento(data: OrcamentoInput, db: Session = Depends(get_db)):
    orcamento = Orcamento(
        numero=_gerar_numero(db),
        uuid_publico=secrets.token_urlsafe(16),
        cliente_nome=data.cliente_nome,
        cliente_contato=data.cliente_contato,
        cliente_endereco=data.cliente_endereco,
        cliente_cnpj=data.cliente_cnpj,
        cliente_email=data.cliente_email,
        cliente_telefone=data.cliente_telefone,
        condicao_pagto=data.condicao_pagto,
        descricao_intro=data.descricao_intro,
        validade_dias=data.validade_dias,
        desconto_percent=data.desconto_percent,
        observacoes_json=json.dumps(data.observacoes_custom) if data.observacoes_custom else None,
    )
    db.add(orcamento)
    db.flush()
    _criar_categorias(db, orcamento.id, data.categorias)
    db.commit()
    db.refresh(orcamento)
    return _orc_to_dict(orcamento)


# ── Listar orçamentos ────────────────────────────────────────────────────────

@app.get("/orcamentos")
def listar_orcamentos(db: Session = Depends(get_db)):
    orcamentos = db.query(Orcamento).order_by(Orcamento.criado_em.desc()).all()
    result = []
    for orc in orcamentos:
        total = sum(item.valor_total for cat in orc.categorias for item in cat.itens)
        result.append({
            "id": orc.id,
            "numero": orc.numero,
            "criado_em": orc.criado_em.isoformat(),
            "cliente_nome": orc.cliente_nome,
            "status": orc.status or "Aguardando",
            "valor_total": total,
            "uuid_publico": orc.uuid_publico,
            "assinatura_nome": orc.assinatura_nome,
        })
    return result


# ── Obter orçamento ──────────────────────────────────────────────────────────

@app.get("/orcamentos/{id}")
def obter_orcamento(id: int, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.id == id).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return _orc_to_dict(orc)


# ── Atualizar status ─────────────────────────────────────────────────────────

@app.patch("/orcamentos/{id}/status")
def atualizar_status(id: int, body: dict, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.id == id).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    status = body.get("status", "Aguardando")
    if status not in ("Aguardando", "Aprovado", "Reprovado", "Expirado"):
        raise HTTPException(status_code=400, detail="Status inválido")
    orc.status = status
    db.commit()
    return {"ok": True}


# ── Duplicar orçamento ───────────────────────────────────────────────────────

@app.post("/orcamentos/{id}/duplicar")
def duplicar_orcamento(id: int, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.id == id).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")

    novo = Orcamento(
        numero=_gerar_numero(db),
        uuid_publico=secrets.token_urlsafe(16),
        cliente_nome=orc.cliente_nome,
        cliente_contato=orc.cliente_contato,
        cliente_endereco=orc.cliente_endereco,
        cliente_cnpj=orc.cliente_cnpj,
        cliente_email=orc.cliente_email,
        cliente_telefone=orc.cliente_telefone,
        condicao_pagto=orc.condicao_pagto,
        descricao_intro=orc.descricao_intro,
        validade_dias=orc.validade_dias,
        desconto_percent=orc.desconto_percent,
        observacoes_json=orc.observacoes_json,
    )
    db.add(novo)
    db.flush()

    for cat in orc.categorias:
        nova_cat = Categoria(orcamento_id=novo.id, titulo=cat.titulo, ordem=cat.ordem)
        db.add(nova_cat)
        db.flush()
        for item in cat.itens:
            db.add(Item(
                categoria_id=nova_cat.id,
                garantia=item.garantia,
                descricao=item.descricao,
                quantidade=item.quantidade,
                valor_unitario=item.valor_unitario,
                valor_total=item.valor_total,
            ))

    db.commit()
    db.refresh(novo)
    return {"id": novo.id}


# ── Listar clientes únicos ───────────────────────────────────────────────────

@app.get("/clientes")
def listar_clientes(db: Session = Depends(get_db)):
    subq = db.query(
        func.max(Orcamento.id).label("id")
    ).group_by(Orcamento.cliente_nome).subquery()

    clientes = db.query(Orcamento).join(
        subq, Orcamento.id == subq.c.id
    ).order_by(Orcamento.cliente_nome).all()

    return [
        {
            "nome": c.cliente_nome,
            "contato": c.cliente_contato,
            "endereco": c.cliente_endereco,
            "cnpj": c.cliente_cnpj or "",
            "email": c.cliente_email or "",
            "telefone": c.cliente_telefone or "",
        }
        for c in clientes
    ]


# ── Gerar PDF ─────────────────────────────────────────────────────────────────

@app.get("/orcamentos/{id}/pdf")
def baixar_pdf(id: int, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.id == id).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")

    orc_dict = _orc_to_dict(orc)
    cfg = _get_config(db)
    payload = {"orcamento": orc_dict, "config": _config_to_dict(cfg)}

    result = subprocess.run(
        ["python", str(Path(__file__).parent / "pdf_worker.py")],
        input=json.dumps(payload).encode(),
        capture_output=True,
    )

    if result.returncode != 0:
        error_msg = result.stderr.decode("latin-1", errors="replace")
        raise HTTPException(status_code=500, detail=error_msg)

    return Response(
        content=result.stdout,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{orc.numero}.pdf"'},
    )


# ── Rotas Públicas (Aceite Digital) ─────────────────────────────────────────

@app.get("/p/{uuid}")
def ver_proposta_publica(request: Request, uuid: str, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.uuid_publico == uuid).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    
    orc_dict = _orc_to_dict(orc)
    cfg = _get_config(db)
    config_dict = _config_to_dict(cfg)
    
    valor_subtotal = sum(
        item["valor_total"]
        for cat in orc_dict.get("categorias", [])
        for item in cat.get("itens", [])
    )
    desconto_percent = float(orc_dict.get("desconto_percent") or 0)
    valor_desconto = valor_subtotal * desconto_percent / 100 if desconto_percent else 0
    valor_total_geral = valor_subtotal - valor_desconto
    
    return templates.TemplateResponse("proposta_publica.html", {
        "request": request, 
        "orc": orc_dict,
        "config": config_dict,
        "valor_subtotal": valor_subtotal,
        "desconto_percent": desconto_percent,
        "valor_desconto": valor_desconto,
        "valor_total_geral": valor_total_geral,
    })

class AceiteInput(BaseModel):
    assinatura_nome: str

@app.post("/api/p/{uuid}/aceitar")
def aceitar_proposta(uuid: str, data: AceiteInput, request: Request, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.uuid_publico == uuid).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    
    orc.status = "Aprovado"
    orc.aceito_em = datetime.now(timezone.utc)
    orc.aceito_ip = request.client.host if request.client else None
    orc.assinatura_nome = data.assinatura_nome
    db.commit()
    return {"ok": True}

@app.post("/api/p/{uuid}/recusar")
def recusar_proposta(uuid: str, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.uuid_publico == uuid).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Proposta não encontrada")
    
    orc.status = "Recusado"
    db.commit()
    return {"ok": True}


# ── Licença ──────────────────────────────────────────────────────────────────

class AtivarLicencaInput(BaseModel):
    cnpj: str
    chave: str


@app.get("/api/licenca/status")
def status_licenca(db: Session = Depends(get_db)):
    cfg = _get_config(db)
    return {"ativada": bool(cfg.licenca_ativa)}


@app.post("/api/licenca/ativar")
def ativar_licenca(data: AtivarLicencaInput, db: Session = Depends(get_db)):
    if not _validar_chave_licenca(data.cnpj, data.chave):
        raise HTTPException(status_code=400, detail="Chave de licença inválida")
    cfg = _get_config(db)
    cfg.licenca_chave = data.chave
    cfg.licenca_ativa = True
    cfg.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}


# ── Config da Empresa ───────────────────────────────────────────────────────────

@app.get("/api/config")
def obter_config(db: Session = Depends(get_db)):
    cfg = _get_config(db)
    return _config_to_dict(cfg)

@app.put("/api/config")
def salvar_config(data: ConfigEmpresaInput, db: Session = Depends(get_db)):
    cfg = _get_config(db)
    
    # Se mudar email ou senha, invalida a sessão atual para forçar relogin
    payload = data.model_dump(exclude_none=True)
    if "login_email" in payload or "login_senha" in payload:
        cfg.session_token = None
        global _SESSION_TOKEN
        _SESSION_TOKEN = "" # Limpa cache em memória
        
    for field, value in payload.items():
        setattr(cfg, field, value)
    cfg.atualizado_em = datetime.now(timezone.utc)
    db.commit()
    return {"ok": True}



# ── Catálogo de Itens ───────────────────────────────────────────────────────────

@app.get("/api/catalogo")
def listar_catalogo(db: Session = Depends(get_db)):
    itens = db.query(CatalogoItem).order_by(CatalogoItem.categoria, CatalogoItem.ordem, CatalogoItem.descricao).all()
    # Agrupa por categoria
    grupos = {}
    for item in itens:
        cat = item.categoria
        if cat not in grupos:
            grupos[cat] = []
        grupos[cat].append({
            "id": item.id, "categoria": item.categoria,
            "descricao": item.descricao, "preco": item.preco,
            "garantia": item.garantia, "ativo": item.ativo, "ordem": item.ordem,
        })
    return grupos

@app.get("/api/catalogo/buscar")
def buscar_catalogo(q: str = "", db: Session = Depends(get_db)):
    """Autocomplete: retorna até 10 itens ativos que contenham o termo."""
    itens = db.query(CatalogoItem).filter(
        CatalogoItem.ativo == True,
        CatalogoItem.descricao.ilike(f"%{q}%")
    ).order_by(CatalogoItem.categoria, CatalogoItem.descricao).limit(20).all()
    return [
        {"id": i.id, "categoria": i.categoria, "descricao": i.descricao,
         "preco": i.preco, "garantia": i.garantia}
        for i in itens
    ]

@app.post("/api/catalogo")
def criar_item_catalogo(data: CatalogoItemInput, db: Session = Depends(get_db)):
    item = CatalogoItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, **data.model_dump()}

@app.put("/api/catalogo/{item_id}")
def editar_item_catalogo(item_id: int, data: CatalogoItemInput, db: Session = Depends(get_db)):
    item = db.query(CatalogoItem).filter(CatalogoItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    db.commit()
    return {"ok": True}

@app.delete("/api/catalogo/{item_id}")
def excluir_item_catalogo(item_id: int, db: Session = Depends(get_db)):
    item = db.query(CatalogoItem).filter(CatalogoItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item não encontrado")
    db.delete(item)
    db.commit()
    return {"ok": True}


static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
