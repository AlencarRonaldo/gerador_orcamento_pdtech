# Produto Configurável por Empresa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o gerador de orçamentos num produto vendável onde qualquer empresa configura seus próprios dados (nome, logo, catálogo, credenciais) via painel web, ativado por chave de licença HMAC.

**Architecture:** Toda configuração da empresa vive em `config.json` (criado automaticamente na 1ª execução). Um novo módulo `config.py` centraliza leitura/escrita/validação. O `pdf_worker.py` recebe os dados da empresa via stdin (`data["_config"]`) em vez de tê-los hardcoded. Dois middlewares Starlette controlam acesso: `LicencaMiddleware` (registrado depois, executa primeiro) e `SessaoMiddleware` (registrado antes, executa depois) — substituindo o `@app.middleware("http")` existente.

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Jinja2, Playwright, HTML+TailwindCSS (sem framework JS), `hmac` (stdlib)

---

## Mapa de Arquivos

| Arquivo | Ação | O que muda |
|---|---|---|
| `config.py` | **CRIAR** | Módulo central: carregar/salvar config, validar HMAC-SHA256 |
| `gerar_licenca.py` | **CRIAR** | Script CLI do vendedor para gerar chaves por cliente |
| `static/ativacao.html` | **CRIAR** | Tela de ativação de licença (pública, sem auth) |
| `static/configuracoes.html` | **CRIAR** | Painel de configurações — 4 abas |
| `tests/test_config.py` | **CRIAR** | Testes do módulo config |
| `main.py` | **MODIFICAR** | Remove `cookie_auth` decorado; adiciona dois middlewares via `add_middleware`; credenciais/BASE_NUMERO dinâmicos; rotas /api/config e /api/licenca; enriquece dict PDF com `_config` |
| `pdf_worker.py` | **MODIFICAR** | Remove hardcoded (empresa, cidade, OBS_DEFAULT, CATEGORIA_NOMES, header/footer strings); lê tudo de `data["_config"]` |
| `templates/orcamento.html` | **MODIFICAR** | Remove hardcoded RC Suporte; usa variáveis `{{ empresa.* }}` |
| `static/index.html` | **MODIFICAR** | Remove linhas 166-286 (CAT_DISPLAY + arrays hardcoded); catálogo via API; link Configurações no nav |
| `static/historico.html` | **MODIFICAR** | Link Configurações no nav |

---

## Task 1: Criar `config.py` — módulo central de configuração

**Files:**
- Create: `config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Escrever os testes**

```python
# tests/test_config.py
import json
import hmac
import hashlib
import pytest


@pytest.fixture(autouse=True)
def config_limpo(tmp_path, monkeypatch):
    """Aponta CONFIG_PATH para arquivo temporário em cada teste."""
    import config as cfg
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
    yield


def test_carregar_config_cria_arquivo_se_nao_existir():
    import config as cfg
    resultado = cfg.carregar_config()
    assert cfg.CONFIG_PATH.exists()
    assert resultado["empresa"]["nome"] == "Minha Empresa"


def test_carregar_config_preserva_valores_existentes():
    import config as cfg
    cfg.CONFIG_PATH.write_text(
        json.dumps({"empresa": {"nome": "Acme Corp"}, "licenca": {"chave": "", "ativada": False}}),
        encoding="utf-8",
    )
    resultado = cfg.carregar_config()
    assert resultado["empresa"]["nome"] == "Acme Corp"


def test_salvar_e_recarregar():
    import config as cfg
    c = cfg.carregar_config()
    c["empresa"]["nome"] = "Nova Empresa"
    cfg.salvar_config(c)
    recarregado = cfg.carregar_config()
    assert recarregado["empresa"]["nome"] == "Nova Empresa"


def test_validar_chave_correta():
    import config as cfg
    cnpj = "12345678000190"
    chave = hmac.new(cfg.SECRET_KEY.encode(), cnpj.encode(), hashlib.sha256).hexdigest()
    assert cfg.validar_chave(cnpj, chave) is True


def test_validar_chave_errada():
    import config as cfg
    assert cfg.validar_chave("12345678000190", "chave-invalida") is False


def test_validar_chave_aceita_cnpj_com_formatacao():
    import config as cfg
    cnpj_limpo = "12345678000190"
    chave = hmac.new(cfg.SECRET_KEY.encode(), cnpj_limpo.encode(), hashlib.sha256).hexdigest()
    assert cfg.validar_chave("12.345.678/0001-90", chave) is True


def test_licenca_ativa_false_por_padrao():
    import config as cfg
    cfg.carregar_config()
    assert cfg.licenca_ativa() is False


def test_licenca_ativa_true_quando_ativada():
    import config as cfg
    c = cfg.carregar_config()
    c["licenca"]["ativada"] = True
    cfg.salvar_config(c)
    assert cfg.licenca_ativa() is True
```

- [ ] **Step 2: Rodar testes para confirmar falha**

```bash
cd D:/gerador_orçamentos
python -m pytest tests/test_config.py -v
```
Esperado: `ModuleNotFoundError: No module named 'config'`

- [ ] **Step 3: Criar `config.py`**

```python
# config.py
import hmac
import hashlib
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).parent / "config.json"

# Altere esta chave antes de distribuir o produto.
SECRET_KEY = "orcamentos-saas-secret-2026-xyz"

CONFIG_DEFAULT = {
    "licenca": {"chave": "", "ativada": False},
    "empresa": {
        "nome": "Minha Empresa",
        "cnpj": "",
        "telefone": "",
        "email": "",
        "endereco": "",
        "cidade_estado": "Cidade - UF",
        "logo_path": "static/logo.png",
    },
    "acesso": {"email": "admin@empresa.com", "senha": "senha123"},
    "orcamento": {
        "numero_base": 0,
        "validade_padrao_dias": 7,
        "introducao_padrao": "Prezado cliente, segue proposta comercial conforme solicitado.",
        "condicoes_pagamento": [
            "À vista",
            "50% entrada + 50% na entrega",
            "Boleto 30 dias",
        ],
        "observacoes_padrao": [
            "Garantia de 90 dias nos serviços prestados.",
            "Proposta válida conforme prazo indicado acima.",
        ],
    },
    "catalogo_padrao": [
        {
            "categoria": "Exemplo de Categoria",
            "itens": [{"descricao": "Item exemplo", "preco": 0.0}],
        }
    ],
}


def _merge_defaults(defaults: dict, data: dict) -> dict:
    result = dict(defaults)
    for k, v in data.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _merge_defaults(result[k], v)
        else:
            result[k] = v
    return result


def carregar_config() -> dict:
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(
            json.dumps(CONFIG_DEFAULT, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    return _merge_defaults(CONFIG_DEFAULT, data)


def salvar_config(data: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def validar_chave(cnpj: str, chave: str) -> bool:
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())
    esperado = hmac.new(
        SECRET_KEY.encode(), cnpj_limpo.encode(), hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(esperado, chave.strip())


def licenca_ativa() -> bool:
    return carregar_config().get("licenca", {}).get("ativada", False)
```

- [ ] **Step 4: Rodar testes**

```bash
python -m pytest tests/test_config.py -v
```
Esperado: 8 testes PASSED.

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_config.py
git commit -m "feat: modulo config.py com leitura/escrita de config.json e validacao HMAC-SHA256"
```

---

## Task 2: Criar `gerar_licenca.py` — script do vendedor

**Files:**
- Create: `gerar_licenca.py`

- [ ] **Step 1: Criar o script**

```python
# gerar_licenca.py
"""
Script do VENDEDOR para gerar chaves de licença por cliente.
USO: python gerar_licenca.py --cnpj 12345678000190
NÃO distribua este script junto com o produto.
"""
import argparse
import hmac
import hashlib

from config import SECRET_KEY


def gerar_chave(cnpj: str) -> str:
    cnpj_limpo = "".join(c for c in cnpj if c.isdigit())
    if len(cnpj_limpo) != 14:
        raise ValueError(f"CNPJ inválido: '{cnpj}' — deve ter 14 dígitos numéricos")
    return hmac.new(SECRET_KEY.encode(), cnpj_limpo.encode(), hashlib.sha256).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gera chave de licença para um cliente")
    parser.add_argument("--cnpj", required=True, help="CNPJ do cliente (com ou sem formatação)")
    args = parser.parse_args()
    try:
        chave = gerar_chave(args.cnpj)
        print(f"\nCNPJ:  {args.cnpj}")
        print(f"Chave: {chave}\n")
    except ValueError as e:
        print(f"Erro: {e}")
        raise SystemExit(1)
```

- [ ] **Step 2: Testar manualmente**

```bash
python gerar_licenca.py --cnpj 12.345.678/0001-90
```
Esperado: imprime CNPJ e string hex de 64 caracteres.

- [ ] **Step 3: Commit**

```bash
git add gerar_licenca.py
git commit -m "feat: script gerar_licenca.py para vendedor gerar chaves HMAC por cliente"
```

---

## Task 3: Atualizar `main.py` — middleware de licença + rotas de config

**Files:**
- Modify: `main.py`

- [ ] **Step 1: Adicionar import e remover middleware decorado existente**

No topo de `main.py`, adicione o import:
```python
from starlette.middleware.base import BaseHTTPMiddleware
from config import carregar_config, salvar_config, validar_chave, licenca_ativa
```

**Remova completamente** o bloco `@app.middleware("http") async def cookie_auth` (linhas 57–69 do arquivo atual). Esse bloco será substituído pelos dois novos middlewares no Step 3.

- [ ] **Step 2: Substituir credenciais hardcoded e BASE_NUMERO por config**

Substitua o corpo de `login_api`:
```python
@app.post("/api/login")
def login_api(data: LoginData, response: Response):
    cfg = carregar_config()
    correct_username = secrets.compare_digest(data.email, cfg["acesso"]["email"])
    correct_password = secrets.compare_digest(data.password, cfg["acesso"]["senha"])
    if correct_username and correct_password:
        response.set_cookie(
            key="session_token", value=SESSION_TOKEN, httponly=True, max_age=86400 * 7
        )
        return {"ok": True}
    raise HTTPException(status_code=401, detail="Credenciais inválidas")
```

Remova a linha `BASE_NUMERO = 35` e substitua `_gerar_numero` por:
```python
def _gerar_numero(db: Session) -> str:
    cfg = carregar_config()
    ano = datetime.utcnow().year
    base = cfg["orcamento"].get("numero_base", 0)
    count = db.query(Orcamento).count() + 1 + base
    return f"ORC-{ano}-{count:03d}"
```

- [ ] **Step 3: Adicionar os dois novos middlewares**

Adicione após a criação do `app` (antes dos routes), **substituindo** o middleware removido no Step 1:

```python
ROTAS_PUBLICAS = {
    "/login.html", "/api/login", "/favicon.ico",
    "/ativacao.html", "/api/licenca/status", "/api/licenca/ativar",
}


class LicencaMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in ROTAS_PUBLICAS
            or path.startswith("/p/")
            or path.startswith("/api/p/")
        ):
            return await call_next(request)
        if not licenca_ativa():
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
        ):
            return await call_next(request)
        token = request.cookies.get("session_token")
        if not token or not secrets.compare_digest(token, SESSION_TOKEN):
            if path == "/" or path.endswith(".html"):
                return RedirectResponse(url="/login.html", status_code=303)
            return Response(content="Não autorizado", status_code=401)
        return await call_next(request)


# SessaoMiddleware registrado primeiro (executa por último).
# LicencaMiddleware registrado depois (executa primeiro).
app.add_middleware(SessaoMiddleware)
app.add_middleware(LicencaMiddleware)
```

- [ ] **Step 4: Adicionar rotas de config e licença**

Adicione antes do bloco `# ── Criar orçamento`:

```python
import shutil
from fastapi import UploadFile, File

# ── Config ───────────────────────────────────────────────────────────────────

@app.get("/api/config")
def obter_config():
    cfg = carregar_config()
    cfg_publico = {k: v for k, v in cfg.items() if k != "acesso"}
    cfg_publico["acesso"] = {"email": cfg["acesso"]["email"]}
    return cfg_publico


@app.post("/api/config")
def salvar_config_api(body: dict):
    cfg = carregar_config()
    for secao in ("empresa", "orcamento", "catalogo_padrao"):
        if secao in body:
            cfg[secao] = body[secao]
    if "acesso" in body:
        cfg["acesso"]["email"] = body["acesso"].get("email", cfg["acesso"]["email"])
        if body["acesso"].get("senha"):
            cfg["acesso"]["senha"] = body["acesso"]["senha"]
    salvar_config(cfg)
    return {"ok": True}


@app.post("/api/config/logo")
async def upload_logo(file: UploadFile = File(...)):
    logo_path = Path(__file__).parent / "static" / "logo.png"
    with logo_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    cfg = carregar_config()
    cfg["empresa"]["logo_path"] = "static/logo.png"
    salvar_config(cfg)
    return {"ok": True}


# ── Licença ──────────────────────────────────────────────────────────────────

class AtivarLicencaInput(BaseModel):
    cnpj: str
    chave: str


@app.get("/api/licenca/status")
def status_licenca():
    return {"ativada": licenca_ativa()}


@app.post("/api/licenca/ativar")
def ativar_licenca(data: AtivarLicencaInput):
    if not validar_chave(data.cnpj, data.chave):
        raise HTTPException(status_code=400, detail="Chave de licença inválida")
    cfg = carregar_config()
    cfg["licenca"]["chave"] = data.chave
    cfg["licenca"]["ativada"] = True
    salvar_config(cfg)
    return {"ok": True}
```

- [ ] **Step 5: Enriquecer dict do orçamento com `_config` ao gerar PDF**

No endpoint `baixar_pdf`, após `orc_dict = _orc_to_dict(orc)`, adicione:
```python
orc_dict["_config"] = carregar_config()
```

- [ ] **Step 6: Testar o servidor**

```bash
python main.py
```
Acesse `http://localhost:8000` — deve redirecionar para `/ativacao.html` (licença inativa).

- [ ] **Step 7: Commit**

```bash
git add main.py
git commit -m "feat: main.py usa config.json para credenciais, numero base, dois middlewares de licenca/sessao e rotas de config/licenca"
```

---

## Task 4: Atualizar `pdf_worker.py` — remover todos os hardcoded

**Files:**
- Modify: `pdf_worker.py`

> **Atenção:** Este task cobre todos os hardcoded do worker: `CATEGORIA_NOMES`, `OBS_DEFAULT`, `_formatar_data`, e as strings `header_template` / `footer_template`. Reescreva a função `gerar_pdf` completa conforme abaixo.

- [ ] **Step 1: Remover constantes hardcoded e atualizar `_formatar_data`**

Remova do topo do arquivo:
- O dict `CATEGORIA_NOMES` (linhas 15–21)
- A lista `OBS_DEFAULT` (linhas 23–27)

Substitua `_formatar_data`:
```python
def _formatar_data(dt, cidade_estado="Cidade - UF"):
    return f"{cidade_estado}, {dt.day:02d} de {MESES[dt.month - 1]} de {dt.year}"
```

- [ ] **Step 2: Atualizar `_processar_categorias` — remove lookup de CATEGORIA_NOMES**

```python
def _processar_categorias(categorias):
    resultado = []
    for cat in categorias:
        itens = cat.get("itens", [])
        subtotal = sum(item.get("valor_total", 0) for item in itens)
        resultado.append({
            **cat,
            "titulo_display": cat.get("titulo", ""),  # nome direto, sem mapeamento
            "subtotal": subtotal,
        })
    return resultado
```

- [ ] **Step 3: Reescrever `gerar_pdf` completa — usa `data["_config"]` para empresa, header e footer**

```python
def gerar_pdf(orcamento_dict) -> bytes:
    cfg = orcamento_dict.get("_config", {})
    empresa = cfg.get("empresa", {})
    obs_padrao = cfg.get("orcamento", {}).get("observacoes_padrao", [])
    cidade_estado = empresa.get("cidade_estado", "Cidade - UF")

    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
    env.filters["moeda"] = _formatar_moeda

    # Logo: tenta static/logo.png, fallback para assets/rcsuporte.png
    logo_path = BASE_DIR / empresa.get("logo_path", "static/logo.png")
    if not logo_path.exists():
        logo_path = BASE_DIR / "assets" / "rcsuporte.png"
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

    criado_em = orcamento_dict.get("criado_em")
    if isinstance(criado_em, str):
        criado_em = datetime.fromisoformat(criado_em.replace("Z", "+00:00"))

    valor_subtotal = sum(
        item["valor_total"]
        for cat in orcamento_dict.get("categorias", [])
        for item in cat.get("itens", [])
    )
    desconto_percent = float(orcamento_dict.get("desconto_percent") or 0)
    valor_desconto = valor_subtotal * desconto_percent / 100 if desconto_percent else 0
    valor_total_geral = valor_subtotal - valor_desconto

    validade_dias = orcamento_dict.get("validade_dias") or 7
    validade_formatada = _formatar_validade(criado_em, validade_dias)
    categorias_processadas = _processar_categorias(orcamento_dict.get("categorias", []))

    obs_custom = orcamento_dict.get("observacoes_custom")
    obs_resto = obs_custom if obs_custom else obs_padrao
    observacoes = [f"Validade da proposta: até {validade_formatada}"] + obs_resto

    html_content = env.get_template("orcamento.html").render(
        orcamento=orcamento_dict,
        empresa=empresa,
        data_formatada=_formatar_data(criado_em, cidade_estado),
        valor_subtotal=valor_subtotal,
        valor_desconto=valor_desconto,
        valor_total_geral=valor_total_geral,
        desconto_percent=desconto_percent,
        logo_b64=logo_b64,
        categorias_processadas=categorias_processadas,
        observacoes=observacoes,
        multiplas_categorias=len(categorias_processadas) > 1,
    )

    nome_empresa = empresa.get("nome", "Empresa").upper()
    email_empresa = empresa.get("email", "")
    tel_empresa = empresa.get("telefone", "")
    cnpj_empresa = empresa.get("cnpj", "")

    header_template = f"""<div style="
      width:100%;padding:7px 15mm 5px;
      display:flex;align-items:center;justify-content:space-between;
      font-family:Arial,sans-serif;border-bottom:2px solid #0097b2;
      box-sizing:border-box;
    "><img src="data:image/png;base64,{logo_b64}" style="height:30px;width:auto;">
    <div style="text-align:right;font-size:7.5pt;color:#555;line-height:1.4;">
      <div style="font-weight:700;color:#0097b2;font-size:8.5pt;">{nome_empresa}</div>
      <div>{email_empresa} &nbsp;|&nbsp; {tel_empresa}</div>
    </div></div>"""

    footer_template = f"""<div style="
      width:100%;padding:4px 15mm;
      display:flex;align-items:center;justify-content:space-between;
      font-family:Arial,sans-serif;font-size:7pt;color:#777;
      border-top:1px solid #0097b2;box-sizing:border-box;
    "><span>{nome_empresa} &nbsp;|&nbsp; CNPJ: {cnpj_empresa} &nbsp;|&nbsp; {cidade_estado} &nbsp;|&nbsp; {email_empresa}</span>
    <span>Página <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>"""

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            display_header_footer=True,
            header_template=header_template,
            footer_template=footer_template,
            margin={"top": "46mm", "bottom": "22mm", "left": "15mm", "right": "15mm"},
        )
        browser.close()

    return pdf_bytes
```

- [ ] **Step 4: Commit**

```bash
git add pdf_worker.py
git commit -m "feat: pdf_worker usa _config do orcamento — remove todos os hardcoded (empresa, cidade, header, footer, OBS_DEFAULT, CATEGORIA_NOMES)"
```

---

## Task 5: Atualizar `templates/orcamento.html` — dados dinâmicos da empresa

**Files:**
- Modify: `templates/orcamento.html`

A variável `empresa` já é passada pelo `pdf_worker.py` após a Task 4.

- [ ] **Step 1: Substituir carta de apresentação (linhas 51–57)**

```html
<!-- ANTES: -->
<p class="intro-text">
  A <strong>RC SUPORTE</strong> agradece a oportunidade de apresentar nossa proposta comercial.
</p>
<p class="intro-text">
  Nosso objetivo é oferecer a melhor solução em infraestrutura de redes, TI e segurança eletrônica, com qualidade e preço justo.
</p>

<!-- DEPOIS: -->
<p class="intro-text">
  A <strong>{{ empresa.nome | upper }}</strong> agradece a oportunidade de apresentar nossa proposta comercial.
</p>
<p class="intro-text">
  Nosso objetivo é oferecer a melhor solução com qualidade e preço justo.
</p>
```

- [ ] **Step 2: Substituir company-stamp (linha 66–68)**

```html
<!-- ANTES: -->
<div class="company-stamp">
  <strong>RC SUPORTE:</strong> Redes, TI e Segurança Eletrônica &nbsp;|&nbsp; ABC Paulista – Grande São Paulo
</div>

<!-- DEPOIS: -->
<div class="company-stamp">
  <strong>{{ empresa.nome }}:</strong> {{ empresa.endereco }}
</div>
```

- [ ] **Step 3: Substituir bloco de assinatura (linhas 163–167)**

```html
<!-- ANTES: -->
<div class="signature-name">RC SUPORTE INFORMÁTICA E TELECOM</div>
<div class="signature-label">contato@rcsuporte.tec.br &nbsp;|&nbsp; (11) 95653-4963</div>

<!-- DEPOIS: -->
<div class="signature-name">{{ empresa.nome | upper }}</div>
<div class="signature-label">{{ empresa.email }} &nbsp;|&nbsp; {{ empresa.telefone }}</div>
```

- [ ] **Step 4: Commit**

```bash
git add templates/orcamento.html
git commit -m "feat: template PDF usa variaveis dinamicas da empresa em vez de RC Suporte hardcoded"
```

---

## Task 6: Criar `static/ativacao.html` — tela de ativação de licença

**Files:**
- Create: `static/ativacao.html`

- [ ] **Step 1: Criar a página**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Ativação de Licença</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen flex items-center justify-center">

<div class="bg-white rounded-2xl shadow-xl p-10 max-w-md w-full mx-4">
  <div class="text-center mb-8">
    <div class="text-5xl mb-3">🔑</div>
    <h1 class="text-2xl font-bold text-gray-800">Ativação do Sistema</h1>
    <p class="text-gray-500 text-sm mt-2">Digite o CNPJ da sua empresa e a chave de licença fornecida pelo vendedor.</p>
  </div>

  <div class="space-y-4">
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">CNPJ da Empresa</label>
      <input id="cnpj" type="text" placeholder="00.000.000/0001-00"
        class="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-[#0097b2]">
    </div>
    <div>
      <label class="block text-sm font-medium text-gray-700 mb-1">Chave de Licença</label>
      <input id="chave" type="text" placeholder="Cole a chave recebida aqui"
        class="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-[#0097b2]">
    </div>

    <div id="erro" class="hidden text-red-500 text-sm text-center"></div>

    <button onclick="ativar()"
      class="w-full bg-[#0097b2] text-white font-semibold py-3 rounded-lg hover:bg-[#007d96] transition mt-2">
      Ativar Sistema
    </button>
  </div>
</div>

<script>
  async function ativar() {
    const cnpj = document.getElementById('cnpj').value.trim();
    const chave = document.getElementById('chave').value.trim();
    const erro = document.getElementById('erro');
    erro.classList.add('hidden');

    if (!cnpj || !chave) {
      erro.textContent = 'Preencha o CNPJ e a chave de licença.';
      erro.classList.remove('hidden');
      return;
    }

    try {
      const res = await fetch('/api/licenca/ativar', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({ cnpj, chave }),
      });
      if (!res.ok) {
        const d = await res.json();
        throw new Error(d.detail || 'Chave inválida');
      }
      window.location.href = '/login.html';
    } catch(e) {
      erro.textContent = e.message;
      erro.classList.remove('hidden');
    }
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') ativar();
  });
</script>
</body>
</html>
```

- [ ] **Step 2: Verificar que a rota é pública**

Com o servidor rodando (licença inativa), acesse `http://localhost:8000/ativacao.html` sem estar logado — deve abrir normalmente sem redirecionar para login.

- [ ] **Step 3: Commit**

```bash
git add static/ativacao.html
git commit -m "feat: tela de ativacao de licenca com campos CNPJ e chave"
```

---

## Task 7: Criar `static/configuracoes.html` — painel 4 abas

**Files:**
- Create: `static/configuracoes.html`

- [ ] **Step 1: Criar a página**

```html
<!DOCTYPE html>
<html lang="pt-BR">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Configurações do Sistema</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-50 min-h-screen">

<nav class="bg-[#0097b2] text-white px-6 py-3 flex items-center justify-between shadow">
  <span class="font-bold text-lg tracking-wide">Configurações do Sistema</span>
  <div class="flex gap-4 text-sm">
    <a href="/" class="underline hover:text-blue-100">Novo Orçamento</a>
    <a href="/historico.html" class="underline hover:text-blue-100">Histórico</a>
  </div>
</nav>

<main class="max-w-3xl mx-auto p-6">

  <!-- Abas -->
  <div class="flex gap-1 mb-6 bg-white rounded-xl shadow p-1">
    <button onclick="mostrarAba('empresa')" id="tab-empresa"
      class="tab-btn flex-1 py-2 rounded-lg text-sm font-semibold transition bg-[#0097b2] text-white">
      Empresa
    </button>
    <button onclick="mostrarAba('acesso')" id="tab-acesso"
      class="tab-btn flex-1 py-2 rounded-lg text-sm font-semibold transition text-gray-600 hover:bg-gray-100">
      Acesso
    </button>
    <button onclick="mostrarAba('orcamento')" id="tab-orcamento"
      class="tab-btn flex-1 py-2 rounded-lg text-sm font-semibold transition text-gray-600 hover:bg-gray-100">
      Orçamentos
    </button>
    <button onclick="mostrarAba('catalogo')" id="tab-catalogo"
      class="tab-btn flex-1 py-2 rounded-lg text-sm font-semibold transition text-gray-600 hover:bg-gray-100">
      Catálogo
    </button>
  </div>

  <!-- Aba: Empresa -->
  <div id="aba-empresa" class="aba bg-white rounded-xl shadow p-6 space-y-4">
    <h2 class="text-base font-semibold text-[#0097b2] uppercase mb-2">Dados da Empresa</h2>
    <div class="grid grid-cols-2 gap-4">
      <div class="col-span-2">
        <label class="label">Nome da Empresa</label>
        <input id="emp-nome" type="text" class="input">
      </div>
      <div>
        <label class="label">CNPJ</label>
        <input id="emp-cnpj" type="text" class="input" placeholder="00.000.000/0001-00">
      </div>
      <div>
        <label class="label">Telefone</label>
        <input id="emp-telefone" type="text" class="input" placeholder="(11) 99999-9999">
      </div>
      <div>
        <label class="label">E-mail</label>
        <input id="emp-email" type="email" class="input">
      </div>
      <div>
        <label class="label">Cidade / Estado (para o PDF)</label>
        <input id="emp-cidade" type="text" class="input" placeholder="São Paulo - SP">
      </div>
      <div class="col-span-2">
        <label class="label">Endereço completo</label>
        <input id="emp-endereco" type="text" class="input">
      </div>
    </div>
    <div>
      <label class="label">Logo da Empresa (PNG recomendado)</label>
      <input id="emp-logo" type="file" accept="image/*" class="block mt-1 text-sm text-gray-600">
      <img id="preview-logo" src="/static/logo.png" onerror="this.style.display='none'"
        class="mt-3 h-16 object-contain border rounded-lg p-2">
    </div>
    <button onclick="salvarEmpresa()" class="btn-salvar">Salvar Empresa</button>
  </div>

  <!-- Aba: Acesso -->
  <div id="aba-acesso" class="aba hidden bg-white rounded-xl shadow p-6 space-y-4">
    <h2 class="text-base font-semibold text-[#0097b2] uppercase mb-2">Credenciais de Acesso</h2>
    <div>
      <label class="label">E-mail de Login</label>
      <input id="ac-email" type="email" class="input">
    </div>
    <div>
      <label class="label">Nova Senha</label>
      <input id="ac-senha" type="password" class="input" placeholder="Deixe em branco para não alterar">
    </div>
    <div>
      <label class="label">Confirmar Nova Senha</label>
      <input id="ac-senha2" type="password" class="input">
    </div>
    <button onclick="salvarAcesso()" class="btn-salvar">Salvar Acesso</button>
  </div>

  <!-- Aba: Orçamentos -->
  <div id="aba-orcamento" class="aba hidden bg-white rounded-xl shadow p-6 space-y-4">
    <h2 class="text-base font-semibold text-[#0097b2] uppercase mb-2">Configurações de Orçamento</h2>
    <div class="grid grid-cols-2 gap-4">
      <div>
        <label class="label">Número base da sequência</label>
        <input id="orc-numero-base" type="number" min="0" class="input">
      </div>
      <div>
        <label class="label">Validade padrão (dias)</label>
        <input id="orc-validade" type="number" min="1" class="input">
      </div>
    </div>
    <div>
      <label class="label">Texto de introdução padrão</label>
      <textarea id="orc-intro" rows="3" class="input resize-none"></textarea>
    </div>
    <div>
      <label class="label">Condições de pagamento padrão</label>
      <div id="lista-condicoes" class="space-y-2 mb-2"></div>
      <button onclick="adicionarItem('lista-condicoes', '')" class="btn-add">+ Adicionar condição</button>
    </div>
    <div>
      <label class="label">Observações padrão</label>
      <div id="lista-obs" class="space-y-2 mb-2"></div>
      <button onclick="adicionarItem('lista-obs', '')" class="btn-add">+ Adicionar observação</button>
    </div>
    <button onclick="salvarOrcamento()" class="btn-salvar">Salvar Configurações</button>
  </div>

  <!-- Aba: Catálogo -->
  <div id="aba-catalogo" class="aba hidden bg-white rounded-xl shadow p-6 space-y-4">
    <h2 class="text-base font-semibold text-[#0097b2] uppercase mb-2">Catálogo Padrão de Produtos/Serviços</h2>
    <p class="text-xs text-gray-400">As categorias e itens aqui cadastrados aparecem como sugestões ao criar um orçamento.</p>
    <div id="lista-categorias" class="space-y-4"></div>
    <button onclick="adicionarCategoria()" class="btn-add mt-2">+ Adicionar categoria</button>
    <button onclick="salvarCatalogo()" class="btn-salvar mt-4">Salvar Catálogo</button>
  </div>

  <div id="msg-salvo" class="hidden fixed bottom-6 right-6 bg-green-500 text-white px-6 py-3 rounded-xl shadow-lg text-sm font-semibold">
    Configurações salvas!
  </div>
</main>

<style>
  .label { display: block; font-size: 0.875rem; font-weight: 500; color: #374151; margin-bottom: 0.25rem; }
  .input { width: 100%; border: 1px solid #d1d5db; border-radius: 0.5rem; padding: 0.5rem 0.75rem; font-size: 0.875rem; outline: none; }
  .input:focus { box-shadow: 0 0 0 2px #0097b2; }
  .btn-salvar { background: #0097b2; color: white; font-weight: 600; padding: 0.625rem 1.5rem; border-radius: 0.5rem; font-size: 0.875rem; cursor: pointer; }
  .btn-salvar:hover { background: #007d96; }
  .btn-add { color: #0097b2; font-size: 0.875rem; font-weight: 500; cursor: pointer; background: none; border: none; }
  .btn-add:hover { text-decoration: underline; }
</style>

<script>
  let cfg = {};

  async function carregar() {
    cfg = await (await fetch('/api/config')).json();
    document.getElementById('emp-nome').value = cfg.empresa?.nome || '';
    document.getElementById('emp-cnpj').value = cfg.empresa?.cnpj || '';
    document.getElementById('emp-telefone').value = cfg.empresa?.telefone || '';
    document.getElementById('emp-email').value = cfg.empresa?.email || '';
    document.getElementById('emp-cidade').value = cfg.empresa?.cidade_estado || '';
    document.getElementById('emp-endereco').value = cfg.empresa?.endereco || '';
    document.getElementById('ac-email').value = cfg.acesso?.email || '';
    document.getElementById('orc-numero-base').value = cfg.orcamento?.numero_base ?? 0;
    document.getElementById('orc-validade').value = cfg.orcamento?.validade_padrao_dias ?? 7;
    document.getElementById('orc-intro').value = cfg.orcamento?.introducao_padrao || '';
    renderLista('lista-condicoes', cfg.orcamento?.condicoes_pagamento || []);
    renderLista('lista-obs', cfg.orcamento?.observacoes_padrao || []);
    renderCatalogo(cfg.catalogo_padrao || []);
  }

  function renderLista(containerId, itens) {
    const el = document.getElementById(containerId);
    el.innerHTML = '';
    itens.forEach(v => adicionarItem(containerId, v));
  }

  function adicionarItem(containerId, valor = '') {
    const el = document.getElementById(containerId);
    const row = document.createElement('div');
    row.className = 'flex gap-2';
    row.innerHTML = `
      <input type="text" value="${(valor||'').replace(/"/g,'&quot;')}" class="input flex-1">
      <button onclick="this.parentElement.remove()" class="text-red-400 hover:text-red-600 text-lg px-2">×</button>`;
    el.appendChild(row);
  }

  function getLista(containerId) {
    return [...document.getElementById(containerId).querySelectorAll('input')]
      .map(i => i.value.trim()).filter(Boolean);
  }

  function renderCatalogo(categorias) {
    const el = document.getElementById('lista-categorias');
    el.innerHTML = '';
    categorias.forEach((cat, ci) => adicionarCategoriaComDados(cat, ci));
  }

  function adicionarCategoria() {
    const n = document.getElementById('lista-categorias').children.length;
    adicionarCategoriaComDados({ categoria: '', itens: [] }, n);
  }

  function adicionarCategoriaComDados(cat, ci) {
    const el = document.getElementById('lista-categorias');
    const div = document.createElement('div');
    div.className = 'border border-gray-200 rounded-xl p-4 space-y-3';
    div.dataset.ci = ci;
    div.innerHTML = `
      <div class="flex gap-2 items-center">
        <input type="text" placeholder="Nome da categoria" value="${(cat.categoria||'').replace(/"/g,'&quot;')}"
          class="input flex-1 font-semibold" data-campo="categoria">
        <button onclick="this.closest('[data-ci]').remove()" class="text-red-400 hover:text-red-600 text-xl px-2">×</button>
      </div>
      <div class="itens-container space-y-2 pl-2"></div>
      <button onclick="adicionarItemCatalogo(this.previousElementSibling)" class="btn-add text-xs">+ Adicionar item</button>`;
    el.appendChild(div);
    const itensEl = div.querySelector('.itens-container');
    (cat.itens || []).forEach(item => adicionarItemCatalogoComDados(itensEl, item));
  }

  function adicionarItemCatalogo(container) {
    adicionarItemCatalogoComDados(container, { descricao: '', preco: 0 });
  }

  function adicionarItemCatalogoComDados(container, item) {
    const row = document.createElement('div');
    row.className = 'flex gap-2';
    row.innerHTML = `
      <input type="text" placeholder="Descrição" value="${(item.descricao||'').replace(/"/g,'&quot;')}"
        class="input flex-1" data-campo="descricao">
      <input type="number" placeholder="Preço" step="0.01" min="0" value="${item.preco||0}"
        class="input w-28" data-campo="preco">
      <button onclick="this.parentElement.remove()" class="text-red-400 hover:text-red-600 text-lg px-1">×</button>`;
    container.appendChild(row);
  }

  function getCatalogo() {
    return [...document.getElementById('lista-categorias').querySelectorAll('[data-ci]')].map(div => ({
      categoria: div.querySelector('[data-campo="categoria"]').value.trim(),
      itens: [...div.querySelectorAll('.itens-container .flex')].map(row => ({
        descricao: row.querySelector('[data-campo="descricao"]').value.trim(),
        preco: parseFloat(row.querySelector('[data-campo="preco"]').value) || 0,
      })).filter(i => i.descricao),
    })).filter(c => c.categoria);
  }

  function mostrarAba(nome) {
    document.querySelectorAll('.aba').forEach(el => el.classList.add('hidden'));
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.remove('bg-[#0097b2]', 'text-white');
      btn.classList.add('text-gray-600');
    });
    document.getElementById('aba-' + nome).classList.remove('hidden');
    const tab = document.getElementById('tab-' + nome);
    tab.classList.add('bg-[#0097b2]', 'text-white');
    tab.classList.remove('text-gray-600');
  }

  async function _salvar(payload) {
    const res = await fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error('Erro ao salvar');
    mostrarMsgSalvo();
  }

  function mostrarMsgSalvo() {
    const msg = document.getElementById('msg-salvo');
    msg.classList.remove('hidden');
    setTimeout(() => msg.classList.add('hidden'), 2500);
  }

  async function salvarEmpresa() {
    const logoFile = document.getElementById('emp-logo').files[0];
    if (logoFile) {
      const form = new FormData();
      form.append('file', logoFile);
      await fetch('/api/config/logo', { method: 'POST', body: form });
    }
    await _salvar({ empresa: {
      nome: document.getElementById('emp-nome').value,
      cnpj: document.getElementById('emp-cnpj').value,
      telefone: document.getElementById('emp-telefone').value,
      email: document.getElementById('emp-email').value,
      cidade_estado: document.getElementById('emp-cidade').value,
      endereco: document.getElementById('emp-endereco').value,
    }});
  }

  async function salvarAcesso() {
    const senha = document.getElementById('ac-senha').value;
    const senha2 = document.getElementById('ac-senha2').value;
    if (senha && senha !== senha2) { alert('As senhas não coincidem.'); return; }
    const payload = { acesso: { email: document.getElementById('ac-email').value } };
    if (senha) payload.acesso.senha = senha;
    await _salvar(payload);
    document.getElementById('ac-senha').value = '';
    document.getElementById('ac-senha2').value = '';
  }

  async function salvarOrcamento() {
    await _salvar({ orcamento: {
      numero_base: parseInt(document.getElementById('orc-numero-base').value) || 0,
      validade_padrao_dias: parseInt(document.getElementById('orc-validade').value) || 7,
      introducao_padrao: document.getElementById('orc-intro').value,
      condicoes_pagamento: getLista('lista-condicoes'),
      observacoes_padrao: getLista('lista-obs'),
    }});
  }

  async function salvarCatalogo() {
    await _salvar({ catalogo_padrao: getCatalogo() });
  }

  carregar();
</script>
</body>
</html>
```

- [ ] **Step 2: Testar manualmente**

Com sistema ativado e logado, acesse `/configuracoes.html`. Verifique: 4 abas funcionam, dados carregam, salvar exibe mensagem verde, logo upload funciona.

- [ ] **Step 3: Commit**

```bash
git add static/configuracoes.html
git commit -m "feat: painel de configuracoes com 4 abas — empresa, acesso, orcamento, catalogo"
```

---

## Task 8: Atualizar `static/index.html` — nav + catálogo via API

**Files:**
- Modify: `static/index.html`

> **Atenção:** As linhas abaixo são referências ao arquivo atual. Verifique os números antes de editar.

- [ ] **Step 1: Adicionar link Configurações no nav (linhas 11–14)**

```html
<!-- SUBSTITUIR as linhas 11-14 por: -->
<nav class="bg-[#0097b2] text-white px-6 py-3 flex items-center justify-between shadow">
  <span class="font-bold text-lg tracking-wide" id="nav-titulo">Gerador de Orçamentos</span>
  <div class="flex gap-4 text-sm">
    <a href="/historico.html" class="underline hover:text-blue-100">Ver Histórico →</a>
    <a href="/configuracoes.html" class="underline hover:text-blue-100">Configurações</a>
  </div>
</nav>
```

- [ ] **Step 2: Remover CAT_DISPLAY e todos os arrays hardcoded (linhas 166–286)**

Remova completamente as linhas 166 a 286:
```javascript
// REMOVER TUDO ISSO (linha 166 a 286):
const CAT_DISPLAY = { ... };
const cameras = [ ... ];
const nvr = [ ... ];
const rede = [ ... ];
const cabecamento = [ ... ];
const maoDeObra = [ ... ];
```

Substitua por:
```javascript
let CATALOGO_PADRAO = [];

async function carregarCatalogo() {
  try {
    const cfg = await (await fetch('/api/config')).json();
    CATALOGO_PADRAO = cfg.catalogo_padrao || [];
    const titulo = document.getElementById('nav-titulo');
    if (titulo && cfg.empresa?.nome) {
      titulo.textContent = cfg.empresa.nome + ' — Orçamentos';
    }
    document.title = (cfg.empresa?.nome || 'Gerador') + ' — Novo Orçamento';
  } catch(e) {
    CATALOGO_PADRAO = [];
  }
}
```

- [ ] **Step 3: Atualizar o select de categorias na função `adicionarCategoria` (linhas ~426–435)**

O select atual tem opções hardcoded `CAMERAS`, `NVR`, etc. Substitua o `innerHTML` do select de tipo para popular dinamicamente do catálogo:

```javascript
// Dentro de adicionarCategoria(), substitua o innerHTML do select id="cat-tipo-${id}":
// ANTES: opções hardcoded CAMERAS, NVR, REDE, CABEAMENTO, MAO_DE_OBRA, PERSONALIZADO
// DEPOIS:
const opcoesCategoria = CATALOGO_PADRAO.map(c =>
  `<option value="${c.categoria.replace(/"/g,'&quot;')}">${c.categoria}</option>`
).join('');
// O select fica:
// <option value="">-- Selecione o Tipo --</option>
// + opcoesCategoria (dinâmico)
// + <option value="PERSONALIZADO">PERSONALIZADO</option>
```

- [ ] **Step 4: Atualizar `adicionarItem(catId)` (linha 516–519)**

```javascript
// ANTES (linha 519):
const lista = {CAMERAS:cameras,NVR:nvr,REDE:rede,CABEAMENTO:cabecamento,MAO_DE_OBRA:maoDeObra}[tipo] || [];

// DEPOIS:
const catObj = CATALOGO_PADRAO.find(c => c.categoria === tipo);
const lista = catObj ? catObj.itens : [];
```

- [ ] **Step 5: Chamar `carregarCatalogo()` na inicialização**

Localize onde `carregarClientes()` é chamado (dentro de `DOMContentLoaded` ou similar) e adicione `carregarCatalogo()` no mesmo bloco.

- [ ] **Step 6: Commit**

```bash
git add static/index.html
git commit -m "feat: index.html carrega catalogo e nome da empresa via API — remove arrays hardcoded (linhas 166-286)"
```

---

## Task 9: Atualizar `static/historico.html` — link Configurações no nav

**Files:**
- Modify: `static/historico.html`

- [ ] **Step 1: Adicionar link no nav (linhas 11–16)**

```html
<!-- SUBSTITUIR o nav existente por: -->
<nav class="bg-[#0097b2] text-white px-6 py-3 flex items-center justify-between shadow">
  <span class="font-bold text-lg tracking-wide">Histórico de Orçamentos</span>
  <div class="flex gap-3 items-center">
    <a href="/configuracoes.html" class="text-sm underline hover:text-blue-100">Configurações</a>
    <a href="/" class="text-sm bg-white text-[#0097b2] font-semibold px-4 py-1.5 rounded-lg hover:bg-blue-50">
      Novo Orçamento
    </a>
  </div>
</nav>
```

- [ ] **Step 2: Commit**

```bash
git add static/historico.html
git commit -m "feat: historico.html adiciona link para configuracoes no nav"
```

---

## Task 10: Testes de integração — middleware de licença e rotas de config/licença

**Files:**
- Modify: `tests/test_routes.py`

- [ ] **Step 1: Adicionar testes críticos de licença e config**

No `tests/conftest.py`, verifique como o `client` é criado. Adicione fixture com licença ativa se necessário:

```python
# Em conftest.py, adicionar fixture:
import pytest
from config import carregar_config, salvar_config

@pytest.fixture
def ativar_licenca(tmp_path, monkeypatch):
    """Ativa a licença temporariamente para testes autenticados."""
    import config as cfg
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
    c = cfg.carregar_config()
    c["licenca"]["ativada"] = True
    cfg.salvar_config(c)
    yield
```

Adicione ao final de `tests/test_routes.py`:

```python
# Testes de licença e config

def test_status_licenca_e_rota_publica(client):
    """GET /api/licenca/status é público — sem cookie, deve retornar 200."""
    res = client.get("/api/licenca/status", follow_redirects=False)
    assert res.status_code == 200
    assert "ativada" in res.json()


def test_ativar_licenca_chave_invalida_retorna_400(client):
    res = client.post(
        "/api/licenca/ativar",
        json={"cnpj": "12345678000190", "chave": "chave-errada"},
    )
    assert res.status_code == 400


def test_ativar_licenca_chave_valida(client, monkeypatch, tmp_path):
    import hmac, hashlib, config as cfg
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
    chave = hmac.new(cfg.SECRET_KEY.encode(), b"12345678000190", hashlib.sha256).hexdigest()
    res = client.post(
        "/api/licenca/ativar",
        json={"cnpj": "12.345.678/0001-90", "chave": chave},
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert cfg.licenca_ativa() is True


def test_licenca_inativa_bloqueia_rotas_html(client, monkeypatch, tmp_path):
    import config as cfg
    monkeypatch.setattr(cfg, "CONFIG_PATH", tmp_path / "config.json")
    cfg.carregar_config()  # cria com ativada=False
    res = client.get("/", follow_redirects=False)
    # Com licença inativa, deve redirecionar para /ativacao.html
    assert res.status_code == 303
    assert "/ativacao.html" in res.headers.get("location", "")


def test_config_requer_sessao(client):
    """GET /api/config sem cookie de sessão deve retornar 401."""
    res = client.get("/api/config", follow_redirects=False)
    assert res.status_code in (401, 303)
```

- [ ] **Step 2: Rodar todos os testes**

```bash
python -m pytest tests/ -v
```
Esperado: todos passando (ajuste conftest se necessário para isolar config.json nos testes).

- [ ] **Step 3: Commit**

```bash
git add tests/
git commit -m "test: testes de integracao para middleware de licenca e rotas de config/licenca"
```

---

## Verificação Final

- [ ] Subir o servidor: `python main.py`
- [ ] Sem `config.json`: acesse `/` → deve redirecionar para `/ativacao.html`
- [ ] Gerar chave: `python gerar_licenca.py --cnpj SEU_CNPJ`
- [ ] Ativar em `/ativacao.html` → deve ir para `/login.html`
- [ ] Login com credenciais padrão → acessar `/configuracoes.html`
- [ ] Preencher dados da empresa e salvar
- [ ] Criar orçamento e baixar PDF → verificar dados da empresa no cabeçalho, rodapé e assinatura
- [ ] Verificar que catálogo no formulário vem do `config.json` (não mais hardcoded)
- [ ] Testar troca de senha na Aba 2 e fazer novo login com a nova senha
