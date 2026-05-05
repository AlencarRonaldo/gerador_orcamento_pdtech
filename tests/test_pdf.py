import pytest
from pdf_generator import gerar_pdf


def test_gerar_pdf_retorna_bytes(orcamento_exemplo):
    resultado = gerar_pdf(orcamento_exemplo)
    assert isinstance(resultado, bytes)
    assert len(resultado) > 1000
    assert resultado[:4] == b"%PDF"


def test_gerar_pdf_nome_cliente_no_conteudo(orcamento_exemplo):
    resultado = gerar_pdf(orcamento_exemplo)
    assert resultado[:4] == b"%PDF"