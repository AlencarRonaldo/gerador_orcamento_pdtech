# Calculadora de Materiais por Tipo de Produto

**Data:** 2026-05-11
**Status:** Aprovado
**Segmento:** Impressao 3D, Corte Laser, Ploter/Adesivos, Banners

---

## Contexto

O sistema atual suporta tipos de medicao genericos (`unidade`, `metro_linear`, `metro_quadrado`), mas nao tem logica de precificacao especifica para os produtos principais do negocio. Cada produto tem sua propria formula de calculo e variaveis de material, o que hoje e feito manualmente fora do sistema.

---

## Objetivo

Permitir que o usuario cadastre produtos com suas variantes de material e precos no catalogo, e ao montar um orcamento, informe apenas as medidas/peso — com o valor calculado automaticamente.

---

## Tipos de Produto

### impressao_3d
- Precificacao por **peso em gramas**
- Variantes: lista de materiais com `preco_kg` (ex: PLA, PETG, ABS, TPU)
- Formula: `(peso_g / 1000) x preco_kg`
- No orcamento: usuario seleciona material + informa gramas → valor unitario calculado
- `quantidade` = numero de pecas; `valor_unitario` = custo calculado por peca

### laser
- Precificacao por **area (m2) + material/espessura**
- Variantes: lista de combinacoes material+espessura com `preco_m2` (ex: MDF 3mm, Acrilico 3mm)
- Formula: `(largura_cm / 100) x (altura_cm / 100) x preco_m2`
- No orcamento: usuario seleciona material, informa largura + altura → valor unitario calculado
- `quantidade` = numero de pecas identicas; `valor_unitario` = custo por peca

### ploter_adesivo
- Precificacao por **area (m2)**
- Variantes: lista de tipos de vinil com `preco_m2` (ex: Vinil Brilho, Fosco, Cromado)
- Formula: `(largura_cm / 100) x (altura_cm / 100) x preco_m2`
- No orcamento: usuario seleciona vinil, informa largura + altura → valor unitario calculado
- `quantidade` = numero de copias; `valor_unitario` = custo por copia

### banner
- Precificacao por **area (m2) + acabamentos opcionais**
- Variantes: objeto com dois arrays:
  - `materiais`: lista com `preco_m2` (ex: Lona Brilho, Tecido, Blackout)
  - `acabamentos`: lista com `preco_un` (ex: Ilhao, Haste, Suporte Tripe)
- Formula total do item: `[(largura_cm/100) x (altura_cm/100) x preco_m2] + soma(qtd_acabamento x preco_un)`
- **Modelo de armazenamento:** `valor_unitario` armazena o total composto calculado (area + acabamentos). `quantidade` e forcado a 1. `valor_total = valor_unitario`.
- A descricao enriquecida e o unico registro do detalhamento dos acabamentos.
- **Re-edicao nao e suportada na v1:** o usuario deve remover e readicionar o item.

### produto_simples (padrao atual)
- Comportamento existente sem alteracao
- Compativel com os tipos legados `unidade`, `metro_linear`, `metro_quadrado`

---

## Re-edicao de Itens (todos os tipos especiais)

Re-edicao nao e suportada na v1. Ao editar um orcamento existente, itens com `tipo_produto` especial aparecem como linhas normais (descricao + valor preenchidos). O usuario pode alterar a descricao e o valor manualmente, ou deletar o item e readicionar para usar a calculadora novamente. Isso sera revisado em versoes futuras.

---

## Validacao de Inputs

Todos os campos dimensionais e de peso devem ser > 0. O botao de confirmacao da calculadora fica desabilitado enquanto qualquer campo obrigatorio for zero, vazio ou negativo. Nao ha alerta — apenas o botao permanece inativo.

---

## Regra de Arredondamento

Todos os valores calculados sao arredondados para **2 casas decimais** usando arredondamento matematico padrao (round half up). Ex: R$18,036 → R$18,04.

---

## Estrutura de Dados

### Novos campos em `catalogo_itens`

```sql
ALTER TABLE catalogo_itens ADD COLUMN tipo_produto TEXT DEFAULT 'produto_simples';
ALTER TABLE catalogo_itens ADD COLUMN variantes_json TEXT;
```

### Tipo Pydantic para `variantes_json`

Armazenado como `Text` no banco (string JSON). Nos schemas Pydantic:
- `CatalogoItemInput.variantes_json: Optional[str] = None`
- `CatalogoItemOutput.variantes_json: Optional[str] = None`

O endpoint de criacao/edicao do catalogo valida que o JSON e valido e que a estrutura corresponde ao `tipo_produto`:
- `impressao_3d`, `laser`, `ploter_adesivo`: deve ser lista JSON `[...]` com campo `nome` e campo de preco
- `banner`: deve ser objeto JSON `{...}` com chaves `materiais` e `acabamentos`
- `produto_simples`: `variantes_json` pode ser null

### Formato de `variantes_json` por tipo

**impressao_3d:**
```json
[
  { "nome": "PLA", "preco_kg": 80.0 },
  { "nome": "PETG", "preco_kg": 120.0 },
  { "nome": "ABS", "preco_kg": 100.0 },
  { "nome": "TPU", "preco_kg": 200.0 }
]
```

**laser:**
```json
[
  { "nome": "MDF 3mm", "preco_m2": 150.0 },
  { "nome": "MDF 6mm", "preco_m2": 200.0 },
  { "nome": "Acrilico 3mm", "preco_m2": 300.0 },
  { "nome": "Acrilico 6mm", "preco_m2": 420.0 }
]
```

**ploter_adesivo:**
```json
[
  { "nome": "Vinil Brilho", "preco_m2": 80.0 },
  { "nome": "Vinil Fosco", "preco_m2": 100.0 },
  { "nome": "Vinil Transparente", "preco_m2": 110.0 },
  { "nome": "Cromado", "preco_m2": 180.0 }
]
```

**banner:**
```json
{
  "materiais": [
    { "nome": "Lona Brilho", "preco_m2": 45.0 },
    { "nome": "Lona Fosca", "preco_m2": 50.0 },
    { "nome": "Tecido", "preco_m2": 80.0 },
    { "nome": "Blackout", "preco_m2": 70.0 }
  ],
  "acabamentos": [
    { "nome": "Ilhao", "preco_un": 2.0 },
    { "nome": "Haste", "preco_un": 15.0 },
    { "nome": "Suporte Tripe", "preco_un": 40.0 }
  ]
}
```

---

## Descricao Gerada Automaticamente

Formato consistente sem acentos especiais para evitar problemas de encoding:

| Tipo | Exemplo de descricao gerada |
|---|---|
| impressao_3d | `Impressao 3D - PETG - 150g` |
| laser | `Corte Laser - Acrilico 3mm - 30x40cm (0.12m2)` |
| ploter_adesivo | `Adesivo Vinil Brilho - 60x90cm (0.54m2)` |
| banner | `Banner Lona Brilho - 100x200cm + 8x Ilhao + 1x Haste` |

---

## Interface do Catalogo — Editor de Variantes

Ao criar ou editar um item do catalogo, o campo `tipo_produto` e um select. Ao mudar para um tipo especial, aparece uma secao "Variantes" abaixo.

- Cada variante e uma linha com campos de texto/numero
- Um botao "+ Adicionar" insere uma nova linha em branco ao final
- Cada linha tem um botao de remocao (icone X)
- Reordenacao nao e necessaria na v1
- Para `banner`: duas subsecoes separadas — "Materiais" e "Acabamentos", cada uma com seu proprio botao de adicionar

---

## Arquivos Alterados

| Arquivo | Mudanca |
|---|---|
| `models.py` | +2 campos em `CatalogoItem` (`tipo_produto`, `variantes_json`); atualizar `CatalogoItemInput` e `CatalogoItemOutput` |
| `database.py` | +migration SQL com as 2 colunas novas |
| `main.py` | Endpoints de catalogo retornam `tipo_produto` e `variantes_json`; validacao de estrutura JSON no PUT/POST |
| `static/catalogo.html` | Editor dinamico de variantes por `tipo_produto` no modal de criacao/edicao |
| `static/novo_orcamento.html` | Painel calculadora inline ao selecionar item com `tipo_produto` especial |

---

## Nao Alterado

- Tabelas `orcamentos`, `categorias`, `itens` — sem mudancas
- Template PDF `templates/orcamento.html` — sem mudancas
- `pdf_worker.py` — sem mudancas
- Todos os orcamentos existentes continuam funcionando

---

## Compatibilidade

- Itens existentes no catalogo recebem `tipo_produto = 'produto_simples'` por padrao (valor DEFAULT do SQL)
- O campo `tipo` legado (`unidade`, `metro_linear`, `metro_quadrado`) continua presente e funcional
- Nenhuma migracao de dados necessaria alem do ALTER TABLE

---

## Criterios de Aceitacao

1. Usuario consegue cadastrar item de impressao 3D com multiplos materiais e precos/kg usando editor de variantes
2. Usuario consegue cadastrar item de laser com combinacoes material+espessura e precos/m2 usando editor de variantes
3. Usuario consegue cadastrar item de ploter/adesivo com tipos de vinil e precos/m2 usando editor de variantes
4. Usuario consegue cadastrar item de banner com materiais (preco/m2) e acabamentos (preco/un) em subsecoes separadas
5. No formulario de orcamento, ao selecionar item com `tipo_produto` especial, aparece painel calculadora inline
6. Calculadora bloqueia confirmacao enquanto qualquer campo obrigatorio for zero ou vazio
7. Calculadora preenche automaticamente o `valor_unitario` com valor arredondado a 2 casas decimais
8. Descricao do item e enriquecida automaticamente antes de salvar (formato sem acentos especiais)
9. Para banner: `valor_unitario` = total composto (area + acabamentos), `quantidade` forcada a 1
10. Itens de `produto_simples` continuam funcionando sem mudancas visiveis
11. Orcamentos existentes nao sao afetados
12. JSON invalido ou estrutura incompativel com `tipo_produto` retorna erro 422 no endpoint de catalogo
