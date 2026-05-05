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