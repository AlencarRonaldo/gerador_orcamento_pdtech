from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from base import Base


class Orcamento(Base):
    __tablename__ = "orcamentos"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    cliente_nome = Column(String, nullable=False)
    cliente_contato = Column(String, nullable=False)
    cliente_endereco = Column(String, nullable=False)
    cliente_cnpj = Column(String, nullable=True)
    cliente_email = Column(String, nullable=True)
    cliente_telefone = Column(String, nullable=True)
    condicao_pagto = Column(String, nullable=False)
    descricao_intro = Column(String, nullable=False)
    validade_dias = Column(Integer, default=7, nullable=True)
    desconto_percent = Column(Float, default=0.0, nullable=True)
    observacoes_json = Column(Text, nullable=True)
    status = Column(String, default="Aguardando", nullable=True)
    dados_json = Column(Text, nullable=True)

    categorias = relationship(
        "Categoria", back_populates="orcamento", order_by="Categoria.ordem"
    )


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    orcamento_id = Column(Integer, ForeignKey("orcamentos.id"), nullable=False)
    titulo = Column(String, nullable=False)
    ordem = Column(Integer, default=0)

    orcamento = relationship("Orcamento", back_populates="categorias")
    itens = relationship("Item", back_populates="categoria")


class Item(Base):
    __tablename__ = "itens"

    id = Column(Integer, primary_key=True, index=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False)
    garantia = Column(String, nullable=False)
    descricao = Column(String, nullable=False)
    quantidade = Column(Integer, nullable=False)
    valor_unitario = Column(Float, nullable=False)
    valor_total = Column(Float, nullable=False)

    categoria = relationship("Categoria", back_populates="itens")


class ItemInput(BaseModel):
    garantia: str
    descricao: str
    quantidade: int
    valor_unitario: float


class CategoriaInput(BaseModel):
    titulo: str
    itens: List[ItemInput]


class OrcamentoInput(BaseModel):
    cliente_nome: str
    cliente_contato: str
    cliente_endereco: str
    cliente_cnpj: Optional[str] = None
    cliente_email: Optional[str] = None
    cliente_telefone: Optional[str] = None
    condicao_pagto: str
    descricao_intro: str
    validade_dias: int = 7
    desconto_percent: float = 0.0
    observacoes_custom: Optional[List[str]] = None
    categorias: List[CategoriaInput]


class ItemOutput(BaseModel):
    id: int
    garantia: str
    descricao: str
    quantidade: int
    valor_unitario: float
    valor_total: float

    model_config = {"from_attributes": True}


class CategoriaOutput(BaseModel):
    id: int
    titulo: str
    ordem: int
    itens: List[ItemOutput]

    model_config = {"from_attributes": True}


class OrcamentoOutput(BaseModel):
    id: int
    numero: str
    criado_em: datetime
    cliente_nome: str
    cliente_contato: str
    cliente_endereco: str
    cliente_cnpj: Optional[str] = None
    cliente_email: Optional[str] = None
    cliente_telefone: Optional[str] = None
    condicao_pagto: str
    descricao_intro: str
    validade_dias: int = 7
    desconto_percent: float = 0.0
    status: str = "Aguardando"
    categorias: List[CategoriaOutput]

    model_config = {"from_attributes": True}


class OrcamentoListItem(BaseModel):
    id: int
    numero: str
    criado_em: datetime
    cliente_nome: str
    status: str = "Aguardando"
    valor_total: float = 0.0

    model_config = {"from_attributes": True}
