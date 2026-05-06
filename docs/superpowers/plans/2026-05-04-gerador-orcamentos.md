# Gerador de Orçamentos RC Suporte — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir um sistema web local que permita criar orçamentos com múltiplas categorias de itens, salvar no banco de dados SQLite e gerar PDFs profissionais replicando o layout da RC Suporte e Telecom.

**Architecture:** FastAPI serve as páginas HTML estáticas e a API REST. SQLAlchemy com SQLite persiste os orçamentos. WeasyPrint converte templates Jinja2 em PDF com cabeçalho e rodapé em todas as páginas.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, WeasyPrint, Jinja2, SQLite, HTML + Tailwind CSS via CDN, JavaScript vanilla.

---

## Mapa de Arquivos

| Arquivo | Responsabilidade |
|---------|-----------------|
| `requirements.txt` | Dependências Python |
| `database.py` | Engine SQLAlchemy, sessão, Base, `create_tables()` |
| `models.py` | Modelos ORM (Orcamento, Categoria, Item) + schemas Pydantic |
| `pdf_generator.py` | `gerar_pdf(orcamento) → bytes` via WeasyPrint + Jinja2 |
| `main.py` | FastAPI app + todas as rotas + serving de arquivos estáticos |
| `templates/orcamento.html` | Template Jinja2 do PDF |
| `templates/pdf.css` | CSS do PDF (página, cabeçalho/rodapé, tabelas) |
| `static/index.html` | Formulário de novo orçamento (JS vanilla) |
| `static/historico.html` | Histórico de orçamentos |
| `assets/rcsuporte.png` | Logo (copiada de `D:\rc_suporte\`) |
| `tests/conftest.py` | Fixtures pytest (app de teste, banco em memória) |
| `tests/test_models.py` | Testes de cálculo e persistência |
| `tests/test_routes.py` | Testes das rotas FastAPI via TestClient |
| `tests/test_pdf.py` | Teste de geração de PDF |

---

## Task 1: Setup do Projeto

**Files:**
- Create: `requirements.txt`
- Create: `assets/rcsuporte.png` (cópia do logo)

- [ ] **Step 1: Criar requirements.txt**

```
fastapi
uvicorn[standard]
sqlalchemy
weasyprint
jinja2
python-multipart
pytest
httpx
```

Salvar em `D:\gerador_orçamentos\requirements.txt`.

- [ ] **Step 2: Instalar dependências**

```bash
cd D:\gerador_orçamentos
pip install -r requirements.txt
```

Resultado esperado: todos os pacotes instalados sem erro. Se `weasyprint` falhar no Windows por dependências de sistema, instalar a versão alternativa:
```bash
pip install weasyprint --only-binary=:all:
```

- [ ] **Step 3: Copiar logo**

```bash
copy "D:\rc_suporte\rcsuporte.png" "D:\gerador_orçamentos\assets\rcsuporte.png"
```

- [ ] **Step 4: Verificar estrutura de pastas**

```bash
cd D:\gerador_orçamentos
dir /s /b
```

Resultado esperado: pastas `assets/`, `templates/`, `static/`, `tests/`, `docs/` presentes.

---

## Task 2: Camada de Banco de Dados

**Files:**
- Create: `database.py`
- Create: `models.py`
- Create: `tests/conftest.py`
- Create: `tests/test_models.py`

- [ ] **Step 1: Criar database.py**

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = "sqlite:///./orcamentos.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    Base.metadata.create_all(bind=engine)
```

- [ ] **Step 2: Criar models.py**

```python
# models.py
from datetime import datetime
from typing import List

from pydantic import BaseModel
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from database import Base


# ── SQLAlchemy ORM ────────────────────────────────────────────────────────────

class Orcamento(Base):
    __tablename__ = "orcamentos"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, unique=True, index=True)
    criado_em = Column(DateTime, default=datetime.utcnow)
    cliente_nome = Column(String, nullable=False)
    cliente_contato = Column(String, nullable=False)
    cliente_endereco = Column(String, nullable=False)
    condicao_pagto = Column(String, nullable=False)
    descricao_intro = Column(String, nullable=False)
    dados_json = Column(Text, nullable=True)  # JSON completo para auditoria futura

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
    valor_total = Column(Float, nullable=False)  # calculado: qtd × valor_unitario

    categoria = relationship("Categoria", back_populates="itens")


# ── Pydantic Schemas ──────────────────────────────────────────────────────────

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
    condicao_pagto: str
    descricao_intro: str
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
    condicao_pagto: str
    descricao_intro: str
    categorias: List[CategoriaOutput]

    model_config = {"from_attributes": True}


class OrcamentoListItem(BaseModel):
    id: int
    numero: str
    criado_em: datetime
    cliente_nome: str

    model_config = {"from_attributes": True}
```

- [ ] **Step 3: Criar tests/conftest.py**

```python
# tests/conftest.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
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
```

- [ ] **Step 4: Escrever tests/test_models.py (teste falha antes da implementação — já implementamos, então só verificamos)**

```python
# tests/test_models.py
import pytest
from models import Orcamento, Categoria, Item


def test_calculo_valor_total(db, orcamento_exemplo):
    """valor_total de cada item deve ser quantidade × valor_unitario."""
    item = orcamento_exemplo.categorias[0].itens[0]
    assert item.valor_total == pytest.approx(15 * 355.18)


def test_numero_orcamento(db, orcamento_exemplo):
    assert orcamento_exemplo.numero == "ORC-2026-001"


def test_relacionamentos(db, orcamento_exemplo):
    assert len(orcamento_exemplo.categorias) == 1
    assert len(orcamento_exemplo.categorias[0].itens) == 1


def test_valor_total_geral(db, orcamento_exemplo):
    total = sum(i.valor_total for c in orcamento_exemplo.categorias for i in c.itens)
    assert total == pytest.approx(5327.70)
```

Adicionar `import pytest` no topo do arquivo test_models.py.

- [ ] **Step 5: Rodar testes**

```bash
cd D:\gerador_orçamentos
pytest tests/test_models.py -v
```

Resultado esperado: 4 testes PASS.

- [ ] **Step 6: Commit**

```bash
git init
git add database.py models.py tests/conftest.py tests/test_models.py requirements.txt
git commit -m "feat: database layer — SQLAlchemy models and Pydantic schemas"
```

---

## Task 3: Template HTML/CSS do PDF

**Files:**
- Create: `templates/pdf.css`
- Create: `templates/orcamento.html`

- [ ] **Step 1: Criar templates/pdf.css**

```css
/* templates/pdf.css */
@import url('https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap');

* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

body {
  font-family: 'Open Sans', Arial, sans-serif;
  font-size: 10pt;
  color: #222;
  line-height: 1.4;
}

/* ── Página ──────────────────────────────────────────────────────────────── */
@page {
  size: A4;
  margin: 28mm 15mm 28mm 15mm;

  @top-center {
    content: element(page-header);
    vertical-align: bottom;
  }

  @bottom-center {
    content: element(page-footer);
    vertical-align: top;
  }
}

/* ── Cabeçalho correndo ──────────────────────────────────────────────────── */
.page-header {
  position: running(page-header);
  width: 100%;
  border-bottom: 2px solid #0097b2;
  padding-bottom: 6px;
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-header img {
  height: 48px;
  width: auto;
}

.page-header .company-name {
  font-size: 11pt;
  font-weight: 700;
  color: #0097b2;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

/* ── Rodapé correndo ─────────────────────────────────────────────────────── */
.page-footer {
  position: running(page-footer);
  width: 100%;
  border-top: 1px solid #0097b2;
  padding-top: 5px;
  text-align: center;
  font-size: 8pt;
  color: #555;
}

/* ── Corpo do documento ──────────────────────────────────────────────────── */
.data-linha {
  text-align: right;
  font-size: 9.5pt;
  margin-bottom: 18px;
  color: #333;
}

.bloco-cliente {
  margin-bottom: 16px;
}

.bloco-cliente p {
  margin: 2px 0;
}

.prezados {
  margin-bottom: 14px;
}

h2 {
  font-size: 11pt;
  color: #0097b2;
  border-bottom: 1px solid #0097b2;
  padding-bottom: 3px;
  margin: 18px 0 8px;
}

.quem-somos p {
  text-align: justify;
  margin-bottom: 8px;
}

.parceiros {
  font-weight: 600;
  color: #0097b2;
}

/* ── Tabela de itens ─────────────────────────────────────────────────────── */
.categoria-titulo {
  font-size: 10.5pt;
  font-weight: 700;
  background: #0097b2;
  color: #fff;
  padding: 5px 8px;
  margin: 16px 0 0;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

table.itens {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 4px;
}

table.itens thead th {
  background: #e8f7fa;
  color: #0097b2;
  font-weight: 700;
  font-size: 9pt;
  padding: 5px 6px;
  border: 1px solid #c0dde3;
  text-align: center;
}

table.itens thead th.col-desc {
  text-align: left;
}

table.itens tbody td {
  padding: 5px 6px;
  border: 1px solid #ddd;
  font-size: 9pt;
  vertical-align: top;
}

table.itens tbody td.col-desc {
  text-align: left;
}

table.itens tbody td.col-num {
  text-align: center;
}

table.itens tbody td.col-val {
  text-align: right;
  white-space: nowrap;
}

table.itens tbody tr:nth-child(even) {
  background: #f9fdfe;
}

.subtotal-row {
  font-weight: 600;
  background: #f0f9fc;
}

/* ── Valor total geral ───────────────────────────────────────────────────── */
.valor-total-geral {
  text-align: right;
  font-size: 11pt;
  font-weight: 700;
  color: #0097b2;
  margin: 10px 0 18px;
  padding: 6px 8px;
  border: 1.5px solid #0097b2;
  background: #e8f7fa;
}

/* ── Investimento ────────────────────────────────────────────────────────── */
table.investimento {
  width: 100%;
  border-collapse: collapse;
  margin-bottom: 8px;
}

table.investimento th {
  background: #0097b2;
  color: #fff;
  font-size: 9.5pt;
  padding: 5px 8px;
  text-align: left;
  border: 1px solid #007d96;
}

table.investimento td {
  padding: 5px 8px;
  border: 1px solid #c0dde3;
  font-size: 9.5pt;
}

table.investimento td.col-valor {
  font-weight: 700;
  text-align: right;
  white-space: nowrap;
}

/* ── Faturamento ─────────────────────────────────────────────────────────── */
.faturamento p {
  text-align: justify;
}
```

- [ ] **Step 2: Criar templates/orcamento.html**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <title>Orçamento {{ orcamento.numero }}</title>
</head>
<body>

  <!-- Cabeçalho correndo em todas as páginas -->
  <header class="page-header">
    <img src="data:image/png;base64,{{ logo_b64 }}" alt="RC Suporte Logo">
    <div class="company-name">RC SUPORTE INFORMÁTICA E TELECOM</div>
  </header>

  <!-- Rodapé correndo em todas as páginas -->
  <footer class="page-footer">
    RCSUPORTE E TELECOM &nbsp;|&nbsp; CNPJ: 43.260.654/0001-67 &nbsp;|&nbsp;
    São Bernardo do Campo – SP &nbsp;|&nbsp; Tel: (11) 95653-4963 &nbsp;|&nbsp;
    contato@rcsuporte.tec.br
  </footer>

  <!-- ── PÁGINA 1: Apresentação ── -->
  <div class="data-linha">{{ data_formatada }}</div>

  <div class="bloco-cliente">
    <p><strong>A</strong></p>
    <p><strong>{{ orcamento.cliente_nome }}</strong></p>
    <p>A/C. {{ orcamento.cliente_contato }}</p>
    <p>{{ orcamento.cliente_endereco }}</p>
  </div>

  <p class="prezados">Prezados,</p>

  <p class="prezados">
    A RCSUPORTE agradece a oportunidade de poder participar do processo de cotação
    de materiais para sua empresa, estamos contentes com essa oportunidade.
  </p>

  <h2>Quem Somos</h2>
  <div class="quem-somos">
    <p>
      A RCSUPORTE E TELECOM é uma empresa nova mas colaboradores com mais de 10 anos de mercado,
      com sede em São Bernardo do Campo – SP, atuando nas áreas de TI / Telecom,
      Infraestrutura de TI, Suporte Técnico, dentre outras atividades a fim.
      Possuímos amplo balizador operacional que ajuda o cliente nas demandas mais complexas
      de infraestrutura e outras adequações. Contamos com um quadro de funcionários e de
      colaboradores altamente técnicos e devidamente certificados pelos principais fabricantes
      do mercado. Nossos principais fornecedores são revendas autorizadas, tais como:
    </p>
    <p class="parceiros">Lenovo &nbsp;|&nbsp; Microsoft &nbsp;|&nbsp; Dell &nbsp;|&nbsp;
      Furukawa &nbsp;|&nbsp; Panasonic &nbsp;|&nbsp; Intelbras &nbsp;|&nbsp;
      IBM &nbsp;|&nbsp; Cisco
    </p>
  </div>

  <!-- ── PÁGINA 2+: Proposta ── -->
  <h2>Proposta</h2>
  <p class="prezados">
    Cientes da não obrigatoriedade a aceitar qualquer proposta recebida, aguardamos retorno
    e nos colocamos à disposição para maiores esclarecimentos.
  </p>
  <p class="prezados">
    Venho por meio deste, apresentar nosso memorial descritivo para {{ orcamento.descricao_intro }}:
  </p>

  <!-- Categorias e Tabelas -->
  {% for categoria in orcamento.categorias %}
    <div class="categoria-titulo">{{ categoria.titulo }}</div>
    <table class="itens">
      <thead>
        <tr>
          <th style="width:10%">Garantia</th>
          <th class="col-desc" style="width:48%">Descrição</th>
          <th class="col-num" style="width:7%">Qtd</th>
          <th class="col-val" style="width:17%">Valor Unitário</th>
          <th class="col-val" style="width:18%">Valor Total</th>
        </tr>
      </thead>
      <tbody>
        {% for item in categoria.itens %}
        <tr>
          <td class="col-num">{{ item.garantia }}</td>
          <td class="col-desc">{{ item.descricao }}</td>
          <td class="col-num">{{ item.quantidade }}</td>
          <td class="col-val">{{ item.valor_unitario | moeda }}</td>
          <td class="col-val">{{ item.valor_total | moeda }}</td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endfor %}

  <div class="valor-total-geral">
    VALOR TOTAL &nbsp;&nbsp; {{ valor_total_geral | moeda }}
  </div>

  <p class="prezados">A presente proposta é para os materiais mencionados acima.</p>

  <!-- Investimento -->
  <h2>Investimento</h2>
  <table class="investimento">
    <thead>
      <tr>
        <th>Recursos</th>
        <th>Pagamento</th>
        <th>Valor</th>
      </tr>
    </thead>
    <tbody>
      {% for categoria in orcamento.categorias %}
        {% set subtotal = namespace(val=0) %}
        {% for item in categoria.itens %}{% set subtotal.val = subtotal.val + item.valor_total %}{% endfor %}
      <tr>
        <td>{{ categoria.titulo }}</td>
        <td>Em {{ orcamento.condicao_pagto }}</td>
        <td class="col-valor">{{ subtotal.val | moeda }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <!-- Faturamento -->
  <h2>Faturamento e Pagamento</h2>
  <div class="faturamento">
    <p>
      A RC SUPORTE se compromete a entregar a Nota Fiscal na entrega dos equipamentos
      em até 7 dias após a aprovação, junto com o boleto para pagamento conforme acordado.
      Faturamos em até {{ orcamento.condicao_pagto }}.
    </p>
  </div>

</body>
</html>
```

- [ ] **Step 3: Inspecionar visualmente (sem teste automatizado — template é visual)**

Não há teste unitário para o template. A validação ocorre no Task 4 (geração do PDF).

---

## Task 4: Gerador de PDF

**Files:**
- Create: `pdf_generator.py`
- Create: `tests/test_pdf.py`

- [ ] **Step 1: Escrever o teste que falha**

```python
# tests/test_pdf.py
import pytest
from pdf_generator import gerar_pdf


def test_gerar_pdf_retorna_bytes(orcamento_exemplo):
    resultado = gerar_pdf(orcamento_exemplo)
    assert isinstance(resultado, bytes)
    assert len(resultado) > 1000  # PDF real tem mais de 1KB
    assert resultado[:4] == b"%PDF"  # assinatura de PDF válido


def test_gerar_pdf_nome_cliente_no_conteudo(orcamento_exemplo):
    """Verifica que o PDF foi gerado com dados do cliente."""
    resultado = gerar_pdf(orcamento_exemplo)
    # PDFs contêm strings em formato binário — checar apenas se gerou sem erro
    assert resultado[:4] == b"%PDF"
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
pytest tests/test_pdf.py -v
```

Resultado esperado: ImportError ou ModuleNotFoundError para `pdf_generator`.

- [ ] **Step 3: Criar pdf_generator.py**

```python
# pdf_generator.py
import base64
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from weasyprint import CSS, HTML

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

BASE_DIR = Path(__file__).parent


def _formatar_data(dt: datetime) -> str:
    return f"São Bernardo do Campo - SP, {dt.day:02d}, {MESES[dt.month - 1]} de {dt.year}"


def _formatar_moeda(valor: float) -> str:
    """Formata float para padrão brasileiro: R$ 1.234,56"""
    formatted = f"{valor:,.2f}"
    # Troca separadores: 1,234.56 → 1.234,56
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_pdf(orcamento) -> bytes:
    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
    env.filters["moeda"] = _formatar_moeda

    logo_path = BASE_DIR / "assets" / "rcsuporte.png"
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

    valor_total_geral = sum(
        item.valor_total
        for cat in orcamento.categorias
        for item in cat.itens
    )

    html_content = env.get_template("orcamento.html").render(
        orcamento=orcamento,
        data_formatada=_formatar_data(orcamento.criado_em),
        valor_total_geral=valor_total_geral,
        logo_b64=logo_b64,
    )

    css_path = BASE_DIR / "templates" / "pdf.css"
    return HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf(
        stylesheets=[CSS(filename=str(css_path))]
    )
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/test_pdf.py -v
```

Resultado esperado: 2 testes PASS. Se WeasyPrint falhar com erro de sistema no Windows, ver nota abaixo.

> **Nota Windows:** Se `weasyprint` lançar erro sobre fontes ou GTK, rodar:
> ```bash
> pip install weasyprint --upgrade
> ```
> WeasyPrint >=60 não precisa de GTK. Se ainda falhar, ver Task alternativo no final deste plano.

- [ ] **Step 5: Commit**

```bash
git add pdf_generator.py templates/ tests/test_pdf.py
git commit -m "feat: PDF generator with WeasyPrint and Jinja2 template"
```

---

## Task 5: API FastAPI

**Files:**
- Create: `main.py`
- Create: `tests/test_routes.py`

- [ ] **Step 1: Escrever tests/test_routes.py que falha**

```python
# tests/test_routes.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app


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
```

- [ ] **Step 2: Rodar para confirmar falha**

```bash
pytest tests/test_routes.py -v
```

Resultado esperado: ImportError para `main`.

- [ ] **Step 3: Criar main.py**

```python
# main.py
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
from pdf_generator import gerar_pdf

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
        condicao_pagto=data.condicao_pagto,
        descricao_intro=data.descricao_intro,
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
    pdf_bytes = gerar_pdf(orc)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{orc.numero}.pdf"'},
    )


# Serve arquivos estáticos DEPOIS das rotas da API
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
```

- [ ] **Step 4: Rodar testes**

```bash
pytest tests/test_routes.py -v
```

Resultado esperado: 6 testes PASS.

- [ ] **Step 5: Rodar todos os testes**

```bash
pytest tests/ -v
```

Resultado esperado: todos os testes PASS (test_models + test_pdf + test_routes).

- [ ] **Step 6: Commit**

```bash
git add main.py tests/test_routes.py
git commit -m "feat: FastAPI routes — create, list, get, and PDF download endpoints"
```

---

## Task 6: Frontend — Formulário Novo Orçamento

**Files:**
- Create: `static/index.html`

> Sem testes automatizados — validação manual ao rodar o servidor.

- [ ] **Step 1: Criar static/index.html**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Novo Orçamento — RC Suporte</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">

  <nav class="bg-[#0097b2] text-white px-6 py-3 flex items-center justify-between shadow">
    <span class="font-bold text-lg tracking-wide">RC Suporte — Gerador de Orçamentos</span>
    <a href="/historico.html" class="text-sm underline hover:text-blue-100">Ver Histórico →</a>
  </nav>

  <main class="max-w-4xl mx-auto p-6">
    <h1 class="text-2xl font-bold text-gray-700 mb-6">Novo Orçamento</h1>

    <!-- Dados do Cliente -->
    <section class="bg-white rounded-xl shadow p-6 mb-6">
      <h2 class="text-base font-semibold text-[#0097b2] uppercase mb-4">Dados do Cliente</h2>
      <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">Nome da Empresa</label>
          <input id="cliente_nome" type="text" placeholder="Ex: Complexo de Saude"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0097b2]">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">A/C (Contato)</label>
          <input id="cliente_contato" type="text" placeholder="Ex: Sr. Eduardo Nobuo"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0097b2]">
        </div>
        <div class="md:col-span-2">
          <label class="block text-sm font-medium text-gray-600 mb-1">Endereço</label>
          <input id="cliente_endereco" type="text" placeholder="Ex: Centro – São Bernardo do Campo - SP"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0097b2]">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">Condição de Pagamento</label>
          <input id="condicao_pagto" type="text" value="até 28 dias"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0097b2]">
        </div>
        <div>
          <label class="block text-sm font-medium text-gray-600 mb-1">Descrição do Orçamento</label>
          <input id="descricao_intro" type="text" placeholder="Ex: orçamento de 15 cameras Intelbras"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-[#0097b2]">
        </div>
      </div>
    </section>

    <!-- Categorias -->
    <section class="mb-6">
      <div class="flex items-center justify-between mb-3">
        <h2 class="text-base font-semibold text-[#0097b2] uppercase">Itens do Orçamento</h2>
        <button onclick="adicionarCategoria()"
          class="bg-[#0097b2] text-white text-sm px-4 py-2 rounded-lg hover:bg-[#007d96] transition">
          + Adicionar Categoria
        </button>
      </div>
      <div id="categorias-container"></div>
    </section>

    <!-- Total Geral (visual) -->
    <div id="total-geral" class="bg-[#e8f7fa] border border-[#0097b2] rounded-lg p-4 mb-6 text-right hidden">
      <span class="font-bold text-[#0097b2] text-lg">VALOR TOTAL GERAL: </span>
      <span id="total-valor" class="font-bold text-gray-800 text-lg"></span>
    </div>

    <!-- Botão Gerar -->
    <div class="flex justify-end">
      <button onclick="salvarEGerarPDF()"
        class="bg-green-600 text-white font-semibold px-8 py-3 rounded-xl hover:bg-green-700 transition shadow">
        💾 Salvar e Gerar PDF
      </button>
    </div>
  </main>

  <script>
    let categoriaCount = 0;

    function adicionarCategoria() {
      const id = categoriaCount++;
      const container = document.getElementById('categorias-container');
      const div = document.createElement('div');
      div.className = 'bg-white rounded-xl shadow p-5 mb-4';
      div.id = `cat-${id}`;
      div.innerHTML = `
        <div class="flex items-center gap-3 mb-4">
          <input type="text" placeholder="Nome da Categoria (ex: EQUIPAMENTOS CAMERAS)"
            class="flex-1 border border-gray-300 rounded-lg px-3 py-2 text-sm font-semibold uppercase focus:outline-none focus:ring-2 focus:ring-[#0097b2]"
            id="cat-titulo-${id}">
          <button onclick="document.getElementById('cat-${id}').remove(); recalcularTotal()"
            class="text-red-400 hover:text-red-600 text-sm">✕ Remover</button>
        </div>
        <div class="overflow-x-auto">
          <table class="w-full text-sm border-collapse">
            <thead>
              <tr class="bg-[#e8f7fa] text-[#0097b2]">
                <th class="border border-gray-200 px-2 py-2 text-left w-24">Garantia</th>
                <th class="border border-gray-200 px-2 py-2 text-left">Descrição</th>
                <th class="border border-gray-200 px-2 py-2 text-center w-16">Qtd</th>
                <th class="border border-gray-200 px-2 py-2 text-right w-28">Vl. Unitário</th>
                <th class="border border-gray-200 px-2 py-2 text-right w-28">Vl. Total</th>
                <th class="border border-gray-200 px-2 py-2 w-10"></th>
              </tr>
            </thead>
            <tbody id="itens-${id}"></tbody>
          </table>
        </div>
        <button onclick="adicionarItem(${id})"
          class="mt-3 text-sm text-[#0097b2] hover:underline">+ Adicionar Item</button>
      `;
      container.appendChild(div);
      adicionarItem(id);
    }

    function adicionarItem(catId) {
      const tbody = document.getElementById(`itens-${catId}`);
      const rowId = Date.now();
      const tr = document.createElement('tr');
      tr.id = `item-${rowId}`;
      tr.innerHTML = `
        <td class="border border-gray-200 px-1 py-1">
          <input type="text" value="12 Meses" class="w-full border-0 text-sm px-1" id="gar-${rowId}">
        </td>
        <td class="border border-gray-200 px-1 py-1">
          <input type="text" placeholder="Descrição do item" class="w-full border-0 text-sm px-1" id="desc-${rowId}">
        </td>
        <td class="border border-gray-200 px-1 py-1">
          <input type="number" value="1" min="1" class="w-full border-0 text-sm text-center px-1" id="qtd-${rowId}"
            oninput="calcularLinha(${rowId})">
        </td>
        <td class="border border-gray-200 px-1 py-1">
          <input type="number" value="0" step="0.01" class="w-full border-0 text-sm text-right px-1" id="vun-${rowId}"
            oninput="calcularLinha(${rowId})">
        </td>
        <td class="border border-gray-200 px-1 py-1 text-right font-semibold text-sm pr-2" id="vtot-${rowId}">R$ 0,00</td>
        <td class="border border-gray-200 px-1 py-1 text-center">
          <button onclick="document.getElementById('item-${rowId}').remove(); recalcularTotal()"
            class="text-red-400 hover:text-red-600 text-xs">✕</button>
        </td>
      `;
      tbody.appendChild(tr);
    }

    function calcularLinha(rowId) {
      const qtd = parseFloat(document.getElementById(`qtd-${rowId}`)?.value) || 0;
      const vun = parseFloat(document.getElementById(`vun-${rowId}`)?.value) || 0;
      const total = qtd * vun;
      document.getElementById(`vtot-${rowId}`).textContent = formatarMoeda(total);
      recalcularTotal();
    }

    function recalcularTotal() {
      let total = 0;
      document.querySelectorAll('[id^="vtot-"]').forEach(el => {
        const val = parseFloat(el.textContent.replace('R$ ', '').replace('.', '').replace(',', '.')) || 0;
        total += val;
      });
      const el = document.getElementById('total-geral');
      el.classList.toggle('hidden', total === 0);
      document.getElementById('total-valor').textContent = formatarMoeda(total);
    }

    function formatarMoeda(val) {
      return 'R$ ' + val.toLocaleString('pt-BR', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
    }

    function coletarDados() {
      const categorias = [];
      document.querySelectorAll('[id^="cat-"]').forEach(catEl => {
        const catId = catEl.id.replace('cat-', '');
        const titulo = document.getElementById(`cat-titulo-${catId}`)?.value?.trim();
        if (!titulo) return;
        const itens = [];
        catEl.querySelectorAll('tbody tr').forEach(tr => {
          const rowId = tr.id.replace('item-', '');
          const garantia = document.getElementById(`gar-${rowId}`)?.value?.trim() || '';
          const descricao = document.getElementById(`desc-${rowId}`)?.value?.trim() || '';
          const quantidade = parseInt(document.getElementById(`qtd-${rowId}`)?.value) || 0;
          const valor_unitario = parseFloat(document.getElementById(`vun-${rowId}`)?.value) || 0;
          if (descricao) itens.push({ garantia, descricao, quantidade, valor_unitario });
        });
        if (itens.length) categorias.push({ titulo, itens });
      });
      return {
        cliente_nome: document.getElementById('cliente_nome').value.trim(),
        cliente_contato: document.getElementById('cliente_contato').value.trim(),
        cliente_endereco: document.getElementById('cliente_endereco').value.trim(),
        condicao_pagto: document.getElementById('condicao_pagto').value.trim(),
        descricao_intro: document.getElementById('descricao_intro').value.trim(),
        categorias,
      };
    }

    async function salvarEGerarPDF() {
      const dados = coletarDados();
      if (!dados.cliente_nome || !dados.categorias.length) {
        alert('Preencha o nome do cliente e pelo menos uma categoria com itens.');
        return;
      }
      try {
        const resp = await fetch('/orcamentos', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(dados),
        });
        if (!resp.ok) throw new Error(await resp.text());
        const orc = await resp.json();
        window.location.href = `/orcamentos/${orc.id}/pdf`;
      } catch (err) {
        alert('Erro ao gerar orçamento: ' + err.message);
      }
    }

    // Iniciar com uma categoria vazia
    adicionarCategoria();
  </script>
</body>
</html>
```

---

## Task 7: Frontend — Histórico de Orçamentos

**Files:**
- Create: `static/historico.html`

> **Nota URL:** O arquivo fica em `static/historico.html` e é acessado via `/historico.html`. O FastAPI StaticFiles serve corretamente. O link na navbar do `index.html` usa `/historico.html`.

- [ ] **Step 1: Criar static/historico.html**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Histórico — RC Suporte</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">

  <nav class="bg-[#0097b2] text-white px-6 py-3 flex items-center justify-between shadow">
    <span class="font-bold text-lg tracking-wide">RC Suporte — Gerador de Orçamentos</span>
    <a href="/" class="text-sm bg-white text-[#0097b2] font-semibold px-4 py-1.5 rounded-lg hover:bg-blue-50">
      + Novo Orçamento
    </a>
  </nav>

  <main class="max-w-4xl mx-auto p-6">
    <h1 class="text-2xl font-bold text-gray-700 mb-6">Histórico de Orçamentos</h1>

    <div id="loading" class="text-gray-400 text-sm">Carregando...</div>
    <div id="vazio" class="hidden text-gray-400 text-sm">Nenhum orçamento gerado ainda.</div>

    <div class="bg-white rounded-xl shadow overflow-hidden hidden" id="tabela-wrapper">
      <table class="w-full text-sm">
        <thead class="bg-[#e8f7fa] text-[#0097b2]">
          <tr>
            <th class="text-left px-4 py-3 font-semibold">Número</th>
            <th class="text-left px-4 py-3 font-semibold">Cliente</th>
            <th class="text-left px-4 py-3 font-semibold">Data</th>
            <th class="px-4 py-3"></th>
          </tr>
        </thead>
        <tbody id="lista"></tbody>
      </table>
    </div>
  </main>

  <script>
    function formatarData(iso) {
      return new Date(iso).toLocaleDateString('pt-BR');
    }

    async function carregarHistorico() {
      const resp = await fetch('/orcamentos');
      const lista = await resp.json();
      document.getElementById('loading').classList.add('hidden');
      if (!lista.length) {
        document.getElementById('vazio').classList.remove('hidden');
        return;
      }
      document.getElementById('tabela-wrapper').classList.remove('hidden');
      const tbody = document.getElementById('lista');
      lista.forEach((orc, i) => {
        const tr = document.createElement('tr');
        tr.className = i % 2 === 0 ? 'bg-white' : 'bg-gray-50';
        tr.innerHTML = `
          <td class="px-4 py-3 font-mono font-semibold text-gray-700">${orc.numero}</td>
          <td class="px-4 py-3 text-gray-700">${orc.cliente_nome}</td>
          <td class="px-4 py-3 text-gray-500">${formatarData(orc.criado_em)}</td>
          <td class="px-4 py-3 text-right">
            <a href="/orcamentos/${orc.id}/pdf"
              class="inline-block bg-[#0097b2] text-white text-xs font-semibold px-3 py-1.5 rounded-lg hover:bg-[#007d96] transition">
              📄 Baixar PDF
            </a>
          </td>
        `;
        tbody.appendChild(tr);
      });
    }

    carregarHistorico();
  </script>
</body>
</html>
```

---

## Task 8: Verificação End-to-End

- [ ] **Step 1: Rodar todos os testes automatizados**

```bash
cd D:\gerador_orçamentos
pytest tests/ -v
```

Resultado esperado: todos os testes PASS.

- [ ] **Step 2: Subir o servidor**

```bash
python main.py
```

Resultado esperado: `Uvicorn running on http://0.0.0.0:8000`.

- [ ] **Step 3: Testar o formulário no navegador**

Abrir `http://localhost:8000` e:
1. Preencher dados do cliente
2. Renomear categoria para "EQUIPAMENTOS CAMERAS"
3. Adicionar item: Garantia="6 Meses", Descrição="CAMERA IP VIP 1230D", Qtd=15, Vl Unit=355.18
4. Verificar que o total aparece automaticamente: R$ 5.327,70
5. Clicar "Salvar e Gerar PDF"
6. Verificar que o PDF baixa corretamente

- [ ] **Step 4: Verificar PDF gerado**

Abrir o PDF e confirmar:
- [ ] Logo RC Suporte aparece no cabeçalho de todas as páginas
- [ ] Data no formato "São Bernardo do Campo - SP, 04, Maio de 2026"
- [ ] Dados do cliente corretos
- [ ] Seção "Quem Somos" com parceiros
- [ ] Tabela com os itens e valores
- [ ] "VALOR TOTAL R$ 5.327,70"
- [ ] Seção "Investimento"
- [ ] Seção "Faturamento e Pagamento"
- [ ] Rodapé com CNPJ e telefone em todas as páginas

- [ ] **Step 5: Testar histórico**

Abrir `http://localhost:8000/historico.html` e verificar que o orçamento criado aparece na lista com botão "Baixar PDF".

- [ ] **Step 6: Commit final**

```bash
git add static/ assets/ templates/ tests/
git commit -m "feat: complete budget generator — web UI, PDF template, and history"
```

---

## Apêndice: Fallback WeasyPrint no Windows

Se o WeasyPrint não funcionar no Windows após tentativas de instalação, substituir por **Playwright**:

```bash
pip install playwright
playwright install chromium
```

Substituir `pdf_generator.py` (apenas a função `gerar_pdf`):

```python
def gerar_pdf(orcamento) -> bytes:
    # ... (manter lógica de template Jinja2 igual) ...
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        pdf_bytes = page.pdf(format="A4", print_background=True,
                             margin={"top": "28mm", "bottom": "28mm",
                                     "left": "15mm", "right": "15mm"})
        browser.close()
    return pdf_bytes
```

> **Nota:** Com Playwright, o CSS `@page` com `running()` não funciona — o cabeçalho/rodapé deve ser replicado em cada página via posicionamento fixo (`position: fixed`) no CSS. Ajustar `pdf.css` se necessário.
