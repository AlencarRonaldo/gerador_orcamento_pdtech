import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import create_tables, get_db
from models import (
    Categoria,
    Item,
    Orcamento,
    OrcamentoInput,
    OrcamentoOutput,
)

app = FastAPI(title="RC Suporte — Gerador de Orçamentos")


@app.on_event("startup")
def startup():
    create_tables()


BASE_NUMERO = 35


def _gerar_numero(db: Session) -> str:
    ano = datetime.utcnow().year
    count = db.query(Orcamento).count() + 1 + BASE_NUMERO
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


# ── Gerar PDF ────────────────────────────────────────────────────────────────

@app.get("/orcamentos/{id}/pdf")
def baixar_pdf(id: int, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.id == id).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")

    orc_dict = _orc_to_dict(orc)

    result = subprocess.run(
        ["python", str(Path(__file__).parent / "pdf_worker.py")],
        input=json.dumps(orc_dict).encode(),
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


static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
