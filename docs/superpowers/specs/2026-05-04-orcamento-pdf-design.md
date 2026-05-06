# Design Spec: Sistema de Geração de Orçamentos — RC Suporte e Telecom

**Data:** 2026-05-04
**Status:** Aprovado
**Stack:** Python + FastAPI + WeasyPrint + Jinja2 + SQLite

---

## 1. Contexto e Objetivo

Criar um sistema web local (migrável para servidor) que permita à RC Suporte e Telecom preencher dados de um orçamento via formulário, salvar no banco de dados, e gerar um PDF profissional seguindo rigorosamente o layout do arquivo `Orçamento atualizado SBC.pdf`.

**Empresa:** RC SUPORTE INFORMÁTICA E TELECOM
**CNPJ:** 43.260.654/0001-67
**Endereço:** São Bernardo do Campo – SP
**Telefone:** (11) 95653-4963
**E-mail:** contato@rcsuporte.tec.br
**Logo:** `assets/rcsuporte.png`

---

## 2. Arquitetura

```
Navegador (HTML/CSS/JS vanilla)
        │
        │ HTTP (JSON)
        ▼
FastAPI (main.py)
        │
        ├── SQLite (database.py + models.py)   — persistência
        └── WeasyPrint + Jinja2 (pdf_generator.py) — geração PDF
```

### Rotas da API

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Serve formulário de novo orçamento |
| GET | `/historico` | Serve página de histórico |
| POST | `/orcamentos` | Cria orçamento, salva no BD, retorna `{id, numero}` |
| GET | `/orcamentos` | Lista todos os orçamentos (histórico) |
| GET | `/orcamentos/{id}` | Retorna dados JSON de um orçamento |
| GET | `/orcamentos/{id}/pdf` | Gera e serve o PDF do orçamento |

---

## 3. Modelo de Dados

### Tabela `orcamentos`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| numero | TEXT | Gerado: "ORC-2026-001" |
| criado_em | DATETIME | Auto: datetime.utcnow() |
| cliente_nome | TEXT | Nome da empresa cliente |
| cliente_contato | TEXT | "A/C. Sr. Nome" |
| cliente_endereco | TEXT | Endereço do cliente |
| condicao_pagto | TEXT | Ex: "até 28 dias" |
| descricao_intro | TEXT | Texto antes da tabela |
| dados_json | TEXT | JSON completo serializado |

### Tabela `categorias`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| orcamento_id | FK → orcamentos.id | |
| titulo | TEXT | Ex: "EQUIPAMENTOS CAMERAS" |
| ordem | INTEGER | Ordem de exibição |

### Tabela `itens`
| Campo | Tipo | Descrição |
|---|---|---|
| id | INTEGER PK AUTOINCREMENT | |
| categoria_id | FK → categorias.id | |
| garantia | TEXT | Ex: "6 Meses" |
| descricao | TEXT | Descrição do item |
| quantidade | INTEGER | |
| valor_unitario | REAL | |
| valor_total | REAL | Calculado: qtd × valor_unitario |

---

## 4. Schema JSON de Entrada

```json
{
  "cliente_nome": "Complexo de Saude",
  "cliente_contato": "Sr. Eduardo Nobuo",
  "cliente_endereco": "Centro – São Bernardo do Campo - SP",
  "condicao_pagto": "até 28 dias",
  "descricao_intro": "orçamento de 15 cameras Intelbras",
  "categorias": [
    {
      "titulo": "EQUIPAMENTOS CAMERAS",
      "itens": [
        {
          "garantia": "6 Meses",
          "descricao": "CAMERA IP VIP 1230D 2.8MM ITB",
          "quantidade": 15,
          "valor_unitario": 355.18
        }
      ]
    }
  ]
}
```

**Regras de negócio:**
- `valor_total` de cada item = `quantidade × valor_unitario` (calculado pelo backend, nunca pelo frontend)
- `valor_total_geral` = soma de todos os `valor_total` de todos os itens
- `numero` do orçamento = `ORC-{ANO}-{sequencial com 3 dígitos}`
- Data no PDF = formato "São Bernardo do Campo - SP, {Dia}, {Mês por extenso} de {Ano}"

---

## 5. Layout do PDF

### Estrutura por página

**Cabeçalho (todas as páginas):**
- Logo RC Suporte à esquerda
- Texto "RC SUPORTE INFORMÁTICA E TELECOM" à direita do logo

**Rodapé (todas as páginas):**
- `RCSUPORTE E TELECOM`
- `CNPJ: 43.260.654/0001-67`
- `São Bernardo do Campo – SP | Tel: (11) 95653-4963 | E-mail: contato@rcsuporte.tec.br`

**Página 1 — Apresentação:**
1. Data dinâmica: "São Bernardo do Campo - SP, {DD}, {Mês} de {AAAA}"
2. Bloco cliente: nome, A/C, endereço
3. Parágrafo de abertura ("A RCSUPORTE agradece a oportunidade...")
4. Seção **Quem Somos**: texto institucional + lista de parceiros (Lenovo, Microsoft, Dell, Furukawa, Panasonic, Intelbras, IBM, Cisco)

**Página 2+ — Proposta:**
1. Texto introdutório da proposta + `descricao_intro`
2. Para cada categoria:
   - Título da categoria em destaque
   - Tabela com colunas: Garantia | Descrição | Quantidade | Valor Unitário | Valor Total
   - Linha de subtotal por categoria
3. **VALOR TOTAL GERAL** (soma de todas as categorias)
4. Seção **Investimento**: tabela com Recursos | Pagto | Valor
5. Seção **Faturamento e Pagamento**: texto padrão fixo

### Textos Fixos

**Parágrafo de abertura:**
> "A RCSUPORTE agradece a oportunidade de poder participar do processo de cotação de materiais para sua empresa, estamos contentes com essa oportunidade."

**Quem Somos:**
> "A RCSUPORTE E TELECOM é uma empresa nova mas colaboradores com mais de 10 anos de mercado, com sede em São Bernardo do Campo – SP, atuando nas áreas de TI / Telecom, Infraestrutura de TI, Suporte Técnico, dentre outras atividades a fim. Possuímos amplo balizador operacional que ajuda o cliente nas demandas mais complexas de infraestrutura e outras adequações. Contamos com um quadro de funcionários e de colaboradores altamente técnicos e devidamente certificados pelos principais fabricantes do mercado. Nossos principais fornecedores são revendas autorizadas, tais como: **Lenovo, Microsoft, Dell, Furukawa, Panasonic, Intelbras, IBM, Cisco**."

**Faturamento e Pagamento:**
> "A RC SUPORTE se compromete a entregar a Nota Fiscal na entrega dos equipamentos em até 7 dias após a aprovação, junto com o boleto para pagamento conforme acordado. Faturamos em para até {condicao_pagto}."

---

## 6. Interface Web

### Tela 1 — Novo Orçamento (`/`)
- Campos: cliente_nome, cliente_contato, cliente_endereco, condicao_pagto, descricao_intro
- Seção dinâmica de categorias:
  - Botão "Adicionar Categoria" — adiciona bloco com título e tabela de itens
  - Dentro de cada categoria: botão "Adicionar Item" — adiciona linha com garantia, descrição, quantidade, valor_unitario
  - Valor total de cada item calculado em tempo real no frontend (apenas visualização)
- Botão "Salvar e Gerar PDF" — envia POST, redireciona para download do PDF

### Tela 2 — Histórico (`/historico`)
- Tabela com: Número, Cliente, Data, botão "📄 PDF"
- Botão "Novo Orçamento" no topo

---

## 7. Estrutura de Arquivos

```
D:\gerador_orçamentos\
├── main.py                  # FastAPI app + todas as rotas
├── database.py              # SQLAlchemy + criação das tabelas SQLite
├── models.py                # Modelos SQLAlchemy + schemas Pydantic
├── pdf_generator.py         # Função gerar_pdf(orcamento) → bytes
├── requirements.txt         # Dependências Python
├── orcamentos.db            # SQLite (gerado automaticamente)
├── assets/
│   └── rcsuporte.png        # Logo (copiada de D:\rc_suporte\)
├── templates/
│   ├── orcamento.html       # Template Jinja2 do PDF
│   └── pdf.css              # CSS do PDF (fontes, tabelas, rodapé)
└── static/
    ├── index.html           # Formulário novo orçamento
    └── historico.html       # Histórico de orçamentos
```

---

## 8. Dependências (requirements.txt)

```
fastapi
uvicorn[standard]
sqlalchemy
weasyprint
jinja2
python-multipart
```

---

## 9. Como Executar

```bash
pip install -r requirements.txt
python main.py
# Abre http://localhost:8000
```

Para migrar para servidor: copiar pasta completa + rodar com `uvicorn main:app --host 0.0.0.0 --port 8000`.

---

## 10. Fora do Escopo (v1)

- Autenticação/login
- Edição de orçamentos já salvos
- Envio por e-mail
- Múltiplos usuários/empresas
