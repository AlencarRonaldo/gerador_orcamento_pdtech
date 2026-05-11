import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

BASE_DIR = Path(__file__).parent


def _formatar_data(dt, cidade=""):
    local = f"{cidade}, " if cidade else ""
    return f"{local}{dt.day:02d} de {MESES[dt.month - 1]} de {dt.year}"


def _formatar_moeda(valor):
    formatted = f"{valor:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_validade(criado_em, validade_dias=7):
    return (criado_em + timedelta(days=int(validade_dias))).strftime("%d/%m/%Y")


def _processar_categorias(categorias):
    resultado = []
    for cat in categorias:
        itens = cat.get("itens", [])
        subtotal = sum(item.get("valor_total", 0) for item in itens)
        resultado.append({
            **cat,
            "titulo_display": cat.get("titulo", ""),
            "subtotal": subtotal,
        })
    return resultado


def gerar_pdf(orcamento_dict, config) -> bytes:
    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
    env.filters["moeda"] = _formatar_moeda

    logo_b64 = config.get("empresa_logo_b64", "")

    empresa_nome = config.get("empresa_nome", "Minha Empresa")
    empresa_email = config.get("empresa_email", "")
    empresa_telefone = config.get("empresa_telefone", "")
    empresa_cnpj = config.get("empresa_cnpj", "")
    empresa_cidade = config.get("empresa_cidade", "")
    empresa_slogan = config.get("empresa_slogan", "")
    empresa_diferenciais = config.get("empresa_diferenciais", "")
    cor_primaria = config.get("cor_primaria", "#0097b2")
    cond_pagto_opcao1 = config.get("cond_pagto_opcao1", "50% de entrada + 50% em 30 dias")
    cond_pagto_opcao2 = config.get("cond_pagto_opcao2", "")
    cond_pagto_opcao3 = config.get("cond_pagto_opcao3", "")
    cond_pagto_opcao3_desconto = config.get("cond_pagto_opcao3_desconto", "5%")
    prazo_equipamentos = orcamento_dict.get("prazo_equipamentos") or config.get("prazo_equipamentos") or "5 a 10 dias úteis após confirmação do pedido"
    prazo_instalacao = orcamento_dict.get("prazo_instalacao") or config.get("prazo_instalacao") or "Mediante agendamento após entrega dos equipamentos"
    pagto_info = config.get("pagto_info") or "Emissão de NF: até 7 dias após aprovação &nbsp;|&nbsp; Pagamento via Boleto, TED ou PIX"
    obs_padrao = config.get("obs_padrao", [
        "Instalação: mediante orçamento adicional",
        "Garantia: fabricante (equipamentos) + 12 meses (mão de obra)",
        "Suporte pós-venda: 30 dias após a conclusão dos serviços",
    ])

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

    # Observações: validade sempre primeiro
    obs_custom = orcamento_dict.get("observacoes_custom")
    obs_resto = obs_custom if obs_custom else obs_padrao
    observacoes = [f"Validade da proposta: até {validade_formatada}"] + obs_resto

    html_content = env.get_template("orcamento.html").render(
        orcamento=orcamento_dict,
        config=config,
        empresa_nome=empresa_nome,
        empresa_slogan=empresa_slogan,
        empresa_diferenciais=empresa_diferenciais,
        empresa_cidade=empresa_cidade,
        empresa_email=empresa_email,
        empresa_telefone=empresa_telefone,
        empresa_cnpj=empresa_cnpj,
        cor_primaria=cor_primaria,
        cond_pagto_opcao1=cond_pagto_opcao1,
        cond_pagto_opcao2=cond_pagto_opcao2,
        cond_pagto_opcao3=cond_pagto_opcao3,
        cond_pagto_opcao3_desconto=cond_pagto_opcao3_desconto,
        data_formatada=_formatar_data(criado_em, empresa_cidade),
        valor_subtotal=valor_subtotal,
        valor_desconto=valor_desconto,
        valor_total_geral=valor_total_geral,
        desconto_percent=desconto_percent,
        logo_b64=logo_b64,
        categorias_processadas=categorias_processadas,
        observacoes=observacoes,
        multiplas_categorias=len(categorias_processadas) > 1,
        prazo_equipamentos=prazo_equipamentos,
        prazo_instalacao=prazo_instalacao,
        habilitar_instalacao=config.get("habilitar_instalacao", False),
        pagto_info=pagto_info,
    )

    # Header e footer dinâmicos
    if logo_b64:
        logo_src = logo_b64 if logo_b64.startswith("data:") else f"data:image/png;base64,{logo_b64}"
        logo_img = f'<img src="{logo_src}" style="height:48px;width:auto;max-width:180px;object-fit:contain;">'
    else:
        logo_img = f'<span style="font-weight:700;color:{cor_primaria};font-size:10pt;">{empresa_nome}</span>'

    contato_parts = []
    if empresa_email:
        contato_parts.append(empresa_email)
    if empresa_telefone:
        contato_parts.append(empresa_telefone)
    contato_str = " &nbsp;|&nbsp; ".join(contato_parts) if contato_parts else ""

    header_template = f"""<div style="
      width:100%;padding:4px 13mm 4px;
      display:flex;align-items:center;justify-content:space-between;
      font-family:Arial,sans-serif;border-bottom:2px solid {cor_primaria};
      box-sizing:border-box;
    ">{logo_img}
    <div style="text-align:right;font-size:7.5pt;color:#555;line-height:1.4;">
      <div style="font-weight:700;color:{cor_primaria};font-size:8.5pt;">{empresa_nome.upper()}</div>
      <div>{contato_str}</div>
    </div></div>"""

    footer_parts = [empresa_nome.upper()]
    if empresa_cnpj:
        footer_parts.append(f"CNPJ: {empresa_cnpj}")
    if empresa_cidade:
        footer_parts.append(empresa_cidade)
    if empresa_email:
        footer_parts.append(empresa_email)
    footer_info = " &nbsp;|&nbsp; ".join(footer_parts)

    footer_template = f"""<div style="
      width:100%;padding:4px 15mm;
      display:flex;align-items:center;justify-content:space-between;
      font-family:Arial,sans-serif;font-size:7pt;color:#777;
      border-top:1px solid {cor_primaria};box-sizing:border-box;
    "><span>{footer_info}</span>
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
            margin={"top": "26mm", "bottom": "16mm", "left": "13mm", "right": "13mm"},
        )
        browser.close()

    return pdf_bytes


if __name__ == "__main__":
    data = sys.stdin.read()
    payload = json.loads(data)
    # Suporta formato novo {orcamento, config} e legado (dict direto)
    if "orcamento" in payload and "config" in payload:
        orcamento_dict = payload["orcamento"]
        config = payload["config"]
    else:
        orcamento_dict = payload
        config = {}
    pdf_bytes = gerar_pdf(orcamento_dict, config)
    sys.stdout.buffer.write(pdf_bytes)
