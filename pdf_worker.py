import base64
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

CATEGORIA_NOMES = {
    "CAMERAS": "Câmeras",
    "NVR": "Gravadores NVR",
    "REDE": "Equipamentos de Rede",
    "CABEAMENTO": "Cabeamento Estruturado",
    "MAO_DE_OBRA": "Mão de Obra",
}

BASE_DIR = Path(__file__).parent


def _formatar_data(dt):
    return f"São Bernardo do Campo - SP, {dt.day:02d} de {MESES[dt.month - 1]} de {dt.year}"


def _formatar_moeda(valor):
    formatted = f"{valor:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _formatar_validade(criado_em, validade_dias=7):
    validade = criado_em + timedelta(days=int(validade_dias))
    return validade.strftime("%d/%m/%Y")


def _processar_categorias(categorias):
    resultado = []
    for cat in categorias:
        itens = cat.get("itens", [])
        subtotal = sum(item.get("valor_total", 0) for item in itens)
        resultado.append({
            **cat,
            "titulo_display": CATEGORIA_NOMES.get(cat.get("titulo", ""), cat.get("titulo", "")),
            "subtotal": subtotal,
        })
    return resultado


def gerar_pdf(orcamento_dict) -> bytes:
    env = Environment(loader=FileSystemLoader(str(BASE_DIR / "templates")))
    env.filters["moeda"] = _formatar_moeda

    logo_path = BASE_DIR / "assets" / "rcsuporte.png"
    logo_b64 = base64.b64encode(logo_path.read_bytes()).decode()

    criado_em = orcamento_dict.get("criado_em")
    if isinstance(criado_em, str):
        criado_em = datetime.fromisoformat(criado_em.replace("Z", "+00:00"))

    valor_total_geral = sum(
        item["valor_total"]
        for cat in orcamento_dict.get("categorias", [])
        for item in cat.get("itens", [])
    )

    validade_dias = orcamento_dict.get("validade_dias") or 7
    categorias_processadas = _processar_categorias(orcamento_dict.get("categorias", []))

    html_content = env.get_template("orcamento.html").render(
        orcamento=orcamento_dict,
        data_formatada=_formatar_data(criado_em),
        valor_total_geral=valor_total_geral,
        logo_b64=logo_b64,
        categorias_processadas=categorias_processadas,
        validade_formatada=_formatar_validade(criado_em, validade_dias),
        multiplas_categorias=len(categorias_processadas) > 1,
    )

    header_template = f"""<div style="
      width:100%;padding:7px 15mm 5px;
      display:flex;align-items:center;justify-content:space-between;
      font-family:Arial,sans-serif;border-bottom:2px solid #0097b2;
      box-sizing:border-box;
    "><img src="data:image/png;base64,{logo_b64}" style="height:30px;width:auto;">
    <div style="text-align:right;font-size:7.5pt;color:#555;line-height:1.4;">
      <div style="font-weight:700;color:#0097b2;font-size:8.5pt;">RC SUPORTE INFORMÁTICA E TELECOM</div>
      <div>contato@rcsuporte.tec.br &nbsp;|&nbsp; (11) 95653-4963</div>
    </div></div>"""

    footer_template = """<div style="
      width:100%;padding:4px 15mm;
      display:flex;align-items:center;justify-content:space-between;
      font-family:Arial,sans-serif;font-size:7pt;color:#777;
      border-top:1px solid #0097b2;box-sizing:border-box;
    "><span>RC SUPORTE INFORMÁTICA E TELECOM &nbsp;|&nbsp; CNPJ: 43.260.654/0001-67 &nbsp;|&nbsp; São Bernardo do Campo – SP &nbsp;|&nbsp; contato@rcsuporte.tec.br</span>
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


if __name__ == "__main__":
    data = sys.stdin.read()
    orcamento_dict = json.loads(data)
    pdf_bytes = gerar_pdf(orcamento_dict)
    sys.stdout.buffer.write(pdf_bytes)
