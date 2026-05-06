import asyncio
import base64
import concurrent.futures
from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

MESES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]

BASE_DIR = Path(__file__).parent


def _formatar_data(dt: datetime) -> str:
    return f"São Bernardo do Campo - SP, {dt.day:02d}, {MESES[dt.month - 1]} de {dt.year}"


def _formatar_moeda(valor: float) -> str:
    formatted = f"{valor:,.2f}"
    return "R$ " + formatted.replace(",", "X").replace(".", ",").replace("X", ".")


def _gerar_pdf_sync(orcamento) -> bytes:
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

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html_content)
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "28mm", "bottom": "28mm", "left": "15mm", "right": "15mm"}
        )
        browser.close()

    return pdf_bytes


def gerar_pdf(orcamento) -> bytes:
    loop = asyncio.new_event_loop()
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(_gerar_pdf_sync, orcamento)
        pdf_bytes = future.result()
    return pdf_bytes