from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from base import Base


def _utc_now():
    return datetime.now(timezone.utc)


class ConfigEmpresa(Base):
    __tablename__ = "config_empresa"

    id = Column(Integer, primary_key=True, default=1)
    empresa_nome = Column(String, default="Minha Empresa")
    empresa_cnpj = Column(String, nullable=True)
    empresa_telefone = Column(String, nullable=True)
    empresa_email = Column(String, nullable=True)
    empresa_endereco = Column(String, nullable=True)
    empresa_cidade = Column(String, nullable=True)
    empresa_slogan = Column(String, nullable=True)
    empresa_diferenciais = Column(String, nullable=True)
    empresa_logo_b64 = Column(Text, nullable=True)
    cor_primaria = Column(String, default="#0097b2")
    obs_padrao_json = Column(Text, nullable=True)
    prazo_equipamentos = Column(String, nullable=True)
    prazo_instalacao = Column(String, nullable=True)
    pagto_info = Column(String, nullable=True)
    cond_pagto_opcao1 = Column(String, default="50% de entrada + 50% em 30 dias")
    cond_pagto_opcao3_desconto = Column(String, default="5%")
    login_email = Column(String, default="admin@admin.com")
    login_senha = Column(String, default="admin123")
    session_token = Column(String, nullable=True)
    licenca_chave = Column(String, nullable=True)
    licenca_ativa = Column(Boolean, default=False)
    numero_base = Column(Integer, default=0)
    atualizado_em = Column(DateTime, default=_utc_now, onupdate=_utc_now)
    smtp_host = Column(String, nullable=True)
    smtp_port = Column(Integer, default=587, nullable=True)
    smtp_user = Column(String, nullable=True)
    smtp_pass = Column(String, nullable=True)
    notif_email_dest = Column(String, nullable=True)
    consultor_nome = Column(String, nullable=True)


class Cliente(Base):
    __tablename__ = "clientes"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String, nullable=False)
    contato = Column(String)
    email = Column(String)
    telefone = Column(String)
    cnpj_cpf = Column(String)
    endereco = Column(String)
    cidade = Column(String)
    criado_em = Column(DateTime, default=_utc_now)

    orcamentos = relationship("Orcamento", back_populates="cliente_reg")


class CatalogoItem(Base):
    __tablename__ = "catalogo_itens"

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String, nullable=False, index=True)
    descricao = Column(String, nullable=False)
    preco = Column(Float, nullable=False, default=0.0)
    garantia = Column(String, default="12 Meses")
    ativo = Column(Boolean, default=True)
    ordem = Column(Integer, default=0)
    criado_em = Column(DateTime, default=_utc_now)


class Orcamento(Base):
    __tablename__ = "orcamentos"

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("clientes.id"), nullable=True)
    numero = Column(String, unique=True, index=True)
    criado_em = Column(DateTime, default=_utc_now)
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
    
    uuid_publico = Column(String, unique=True, index=True, nullable=True)
    aceito_em = Column(DateTime, nullable=True)
    aceito_ip = Column(String, nullable=True)
    assinatura_nome = Column(String, nullable=True)
    assinatura_cpf = Column(String, nullable=True)
    assinatura_telefone = Column(String, nullable=True)
    assinatura_hash = Column(String, nullable=True)
    assinatura_termos = Column(Boolean, default=False, nullable=True)
    qtd_visualizacoes = Column(Integer, default=0, nullable=True)
    primeira_abertura_em = Column(DateTime, nullable=True)
    consultor_nome = Column(String, nullable=True)

    categorias = relationship(
        "Categoria", back_populates="orcamento", order_by="Categoria.ordem"
    )
    cliente_reg = relationship("Cliente", back_populates="orcamentos")


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
    cliente_cnpj: str  # CPF ou CNPJ obrigatório
    cliente_contato: Optional[str] = ""
    cliente_endereco: Optional[str] = ""
    cliente_email: str
    cliente_telefone: str
    condicao_pagto: str
    descricao_intro: Optional[str] = ""
    validade_dias: int = 7
    desconto_percent: float = 0.0
    observacoes_custom: Optional[List[str]] = None
    cliente_id: Optional[int] = None
    consultor_nome: Optional[str] = None
    categorias: List[CategoriaInput]


class ClienteInput(BaseModel):
    nome: str
    contato: Optional[str] = ""
    email: Optional[str] = ""
    telefone: Optional[str] = ""
    cnpj_cpf: Optional[str] = ""
    endereco: Optional[str] = ""
    cidade: Optional[str] = ""


class ClienteOutput(ClienteInput):
    id: int
    criado_em: datetime

    model_config = {"from_attributes": True}


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
    uuid_publico: Optional[str] = None
    aceito_em: Optional[datetime] = None
    assinatura_nome: Optional[str] = None
    assinatura_cpf: Optional[str] = None
    assinatura_telefone: Optional[str] = None
    categorias: List[CategoriaOutput]

    model_config = {"from_attributes": True}


class OrcamentoListItem(BaseModel):
    id: int
    numero: str
    criado_em: datetime
    cliente_nome: str
    status: str = "Aguardando"
    valor_total: float = 0.0
    uuid_publico: Optional[str] = None
    assinatura_nome: Optional[str] = None

    model_config = {"from_attributes": True}


# ── Config Empresa ────────────────────────────────────────────────────────────

class ConfigEmpresaInput(BaseModel):
    empresa_nome: str
    empresa_cnpj: Optional[str] = None
    empresa_telefone: Optional[str] = None
    empresa_email: Optional[str] = None
    empresa_endereco: Optional[str] = None
    empresa_cidade: Optional[str] = None
    empresa_slogan: Optional[str] = None
    empresa_diferenciais: Optional[str] = None
    empresa_logo_b64: Optional[str] = None
    cor_primaria: str = "#0097b2"
    obs_padrao_json: Optional[str] = None
    prazo_equipamentos: Optional[str] = None
    prazo_instalacao: Optional[str] = None
    pagto_info: Optional[str] = None
    cond_pagto_opcao1: Optional[str] = None
    cond_pagto_opcao3_desconto: Optional[str] = None
    login_email: Optional[str] = None
    login_senha: Optional[str] = None
    numero_base: Optional[int] = None
    smtp_host: Optional[str] = None
    smtp_port: Optional[int] = None
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    notif_email_dest: Optional[str] = None
    consultor_nome: Optional[str] = None


# ── Catálogo ──────────────────────────────────────────────────────────────────

class CatalogoItemInput(BaseModel):
    categoria: str
    descricao: str
    preco: float
    garantia: str = "12 Meses"
    ativo: bool = True
    ordem: int = 0


class CatalogoItemOutput(BaseModel):
    id: int
    categoria: str
    descricao: str
    preco: float
    garantia: str
    ativo: bool
    ordem: int

    model_config = {"from_attributes": True}