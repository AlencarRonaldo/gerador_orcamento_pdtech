import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import List

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session

from database import create_tables, get_db
from models import (
    Categoria,
    Item,
    Orcamento,
    OrcamentoInput,
    OrcamentoListItem,
    OrcamentoOutput,
)

app = FastAPI(title="RC Suporte — Gerador de Orçamentos")


@app.on_event("startup")
def startup():
    create_tables()


def _gerar_numero(db: Session) -> str:
    ano = datetime.utcnow().year
    count = db.query(Orcamento).count() + 1
    return f"ORC-{ano}-{count:03d}"


@app.post("/orcamentos", response_model=OrcamentoOutput)
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
    )
    db.add(orcamento)
    db.flush()

    for ordem, cat_data in enumerate(data.categorias):
        categoria = Categoria(
            orcamento_id=orcamento.id,
            titulo=cat_data.titulo,
            ordem=ordem,
        )
        db.add(categoria)
        db.flush()

        for item_data in cat_data.itens:
            db.add(
                Item(
                    categoria_id=categoria.id,
                    garantia=item_data.garantia,
                    descricao=item_data.descricao,
                    quantidade=item_data.quantidade,
                    valor_unitario=item_data.valor_unitario,
                    valor_total=item_data.quantidade * item_data.valor_unitario,
                )
            )

    db.commit()
    db.refresh(orcamento)
    return orcamento


@app.get("/orcamentos", response_model=List[OrcamentoListItem])
def listar_orcamentos(db: Session = Depends(get_db)):
    return db.query(Orcamento).order_by(Orcamento.criado_em.desc()).all()


@app.get("/orcamentos/{id}", response_model=OrcamentoOutput)
def obter_orcamento(id: int, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.id == id).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")
    return orc


@app.get("/orcamentos/{id}/pdf")
def baixar_pdf(id: int, db: Session = Depends(get_db)):
    orc = db.query(Orcamento).filter(Orcamento.id == id).first()
    if not orc:
        raise HTTPException(status_code=404, detail="Orçamento não encontrado")

    orc_dict = {
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

    result = subprocess.run(
        ["python", str(Path(__file__).parent / "pdf_worker.py")],
        input=json.dumps(orc_dict).encode(),
        capture_output=True,
    )

    if result.returncode != 0:
        error_msg = result.stderr.decode("latin-1", errors="replace")
        raise HTTPException(status_code=500, detail=error_msg)

    pdf_bytes = result.stdout
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{orc.numero}.pdf"'},
    )


static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
