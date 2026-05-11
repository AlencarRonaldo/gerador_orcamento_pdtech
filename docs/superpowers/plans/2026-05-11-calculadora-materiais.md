# Calculadora de Materiais por Tipo de Produto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add product-type-aware pricing calculators (3D printing, laser, plotter/adhesive, banner) to the catalog and budget form, so material variants are configured once in the catalog and auto-calculate prices when creating quotes.

**Architecture:** Two new columns (`tipo_produto`, `variantes_json`) are added to `catalogo_itens` only. Budget item tables are untouched. The catalog drawer gets a dynamic variant editor. The budget form's `selectCatalogItem()` function is extended to show an inline calculator panel when a special item type is selected. Each calculator panel has an "Aplicar" button that is disabled until all required fields are > 0.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / SQLite (or PostgreSQL) / Vanilla JS / Jinja2

**Spec:** `docs/superpowers/specs/2026-05-11-calculadora-materiais-design.md`

---

## File Map

| File | Change |
|---|---|
| `models.py` | Add `tipo_produto` + `variantes_json` to `CatalogoItem` ORM; add all missing fields to `CatalogoItemInput` + `CatalogoItemOutput` |
| `database.py` | Append 2 migration entries to the `migrations` list |
| `main.py` | Add `_validate_variantes_json` helper; update 4 catalog endpoints to expose/save new fields |
| `static/catalogo.html` | Add `tipo_produto` select + dynamic variant editor to the existing drawer |
| `static/novo_orcamento.html` | Extend `selectCatalogItem()` + add inline calculator panel with Aplicar button |
| `tests/test_routes.py` | Add tests for new catalog fields and validation |

---

## Task 1: Backend — Model Fields and Migration

**Files:**
- Modify: `models.py`
- Modify: `database.py`

- [ ] **Step 1: Add columns to CatalogoItem ORM model**

In `models.py`, find `class CatalogoItem` (lines 69-83). Add two columns after `ordem`:

```python
tipo_produto = Column(String, default="produto_simples", nullable=True)
variantes_json = Column(Text, nullable=True)
```

- [ ] **Step 2: Fix CatalogoItemInput — add ALL missing fields**

In `models.py`, find `class CatalogoItemInput` (around line 305). The existing class is missing `largura`, `altura`, `tipo_produto`, and `variantes_json`. Replace the entire class with:

```python
class CatalogoItemInput(BaseModel):
    categoria: str
    descricao: str
    preco: float
    garantia: str = "12 Meses"
    tipo: str = "unidade"
    ativo: bool = True
    ordem: int = 0
    largura: Optional[float] = None
    altura: Optional[float] = None
    tipo_produto: str = "produto_simples"
    variantes_json: Optional[str] = None
```

Note: `largura` and `altura` were missing from `CatalogoItemInput` before — this is a pre-existing bug that caused those fields to be silently dropped when saving m² catalog items. This step fixes that bug as well.

- [ ] **Step 3: Add fields to CatalogoItemOutput**

In `models.py`, find `class CatalogoItemOutput` (around line 315). Add to the class:

```python
tipo_produto: str = "produto_simples"
variantes_json: Optional[str] = None
```

- [ ] **Step 4: Add migration entries to database.py**

In `database.py`, find the `migrations` list (lines 66-108). Append two entries at the end of the list, before the closing `]`:

```python
"ALTER TABLE catalogo_itens ADD COLUMN tipo_produto TEXT DEFAULT 'produto_simples'",
"ALTER TABLE catalogo_itens ADD COLUMN variantes_json TEXT",
```

- [ ] **Step 5: Write failing tests**

In `tests/test_routes.py`, add after existing tests:

```python
def test_catalogo_item_tipo_produto_field(client):
    """New catalog item should accept and return tipo_produto and variantes_json."""
    variantes = '[{"nome": "PLA", "preco_kg": 80.0}, {"nome": "PETG", "preco_kg": 120.0}]'
    resp = client.post("/api/catalogo", json={
        "categoria": "Impressao 3D",
        "descricao": "Impressao 3D Personalizada",
        "preco": 0.0,
        "garantia": "Sem garantia",
        "tipo_produto": "impressao_3d",
        "variantes_json": variantes,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["tipo_produto"] == "impressao_3d"
    assert data["variantes_json"] == variantes


def test_catalogo_listar_returns_tipo_produto(client):
    """GET /api/catalogo should return tipo_produto and variantes_json."""
    client.post("/api/catalogo", json={
        "categoria": "Laser",
        "descricao": "Corte Laser",
        "preco": 0.0,
        "garantia": "Sem garantia",
        "tipo_produto": "laser",
        "variantes_json": '[{"nome": "MDF 3mm", "preco_m2": 150.0}]',
    })
    resp = client.get("/api/catalogo")
    assert resp.status_code == 200
    grupos = resp.json()
    laser_items = grupos.get("Laser", [])
    assert any(i.get("tipo_produto") == "laser" for i in laser_items)


def test_catalogo_buscar_returns_tipo_produto(client):
    """GET /api/catalogo/buscar should return tipo_produto and variantes_json."""
    client.post("/api/catalogo", json={
        "categoria": "Ploter",
        "descricao": "Adesivo Vinil",
        "preco": 0.0,
        "garantia": "Sem garantia",
        "tipo_produto": "ploter_adesivo",
        "variantes_json": '[{"nome": "Vinil Brilho", "preco_m2": 80.0}]',
    })
    resp = client.get("/api/catalogo/buscar?q=Adesivo")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) >= 1
    assert items[0]["tipo_produto"] == "ploter_adesivo"
    assert items[0]["variantes_json"] is not None


def test_catalogo_variantes_json_validation(client):
    """Invalid variantes_json structure should return 422."""
    # Array for banner (should be object)
    resp = client.post("/api/catalogo", json={
        "categoria": "Banner",
        "descricao": "Banner Teste",
        "preco": 0.0,
        "garantia": "Sem garantia",
        "tipo_produto": "banner",
        "variantes_json": '[{"nome": "Lona"}]',
    })
    assert resp.status_code == 422

    # Object for impressao_3d (should be array)
    resp = client.post("/api/catalogo", json={
        "categoria": "3D",
        "descricao": "Impressao",
        "preco": 0.0,
        "garantia": "Sem garantia",
        "tipo_produto": "impressao_3d",
        "variantes_json": '{"nome": "PLA"}',
    })
    assert resp.status_code == 422

    # Invalid JSON string
    resp = client.post("/api/catalogo", json={
        "categoria": "3D",
        "descricao": "Impressao",
        "preco": 0.0,
        "garantia": "Sem garantia",
        "tipo_produto": "impressao_3d",
        "variantes_json": 'not-json',
    })
    assert resp.status_code == 422
```

- [ ] **Step 6: Run failing tests to confirm they fail**

```bash
cd F:/gerador_orçamentos && python -m pytest tests/test_routes.py::test_catalogo_item_tipo_produto_field tests/test_routes.py::test_catalogo_listar_returns_tipo_produto tests/test_routes.py::test_catalogo_buscar_returns_tipo_produto tests/test_routes.py::test_catalogo_variantes_json_validation -v
```

Expected: FAIL

- [ ] **Step 7: Verify full existing test suite still passes**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all existing tests pass

- [ ] **Step 8: Commit model + migration**

```bash
git add models.py database.py
git commit -m "feat: add tipo_produto and variantes_json to CatalogoItem; fix CatalogoItemInput missing largura/altura"
```

---

## Task 2: Backend — API Endpoints

**Files:**
- Modify: `main.py` (lines 1197-1285)

- [ ] **Step 1: Add JSON validation helper**

In `main.py`, check the imports at the top of the file — `json` is already imported (line 4). Do NOT add another import.

Find the comment line `# ── Catálogo de Itens` (around line 1197) and insert the helper function immediately after that comment block, before the first `@app.get("/api/catalogo")` decorator:

```python
def _validate_variantes_json(tipo_produto: str, variantes_json):
    """Raises HTTPException 422 if variantes_json structure is invalid for tipo_produto."""
    if tipo_produto == "produto_simples" or not variantes_json:
        return
    try:
        parsed = json.loads(variantes_json)
    except Exception:
        raise HTTPException(status_code=422, detail="variantes_json must be valid JSON")

    if tipo_produto in ("impressao_3d", "laser", "ploter_adesivo"):
        if not isinstance(parsed, list):
            raise HTTPException(
                status_code=422,
                detail=f"variantes_json for {tipo_produto} must be a JSON array"
            )
    elif tipo_produto == "banner":
        if not isinstance(parsed, dict) or "materiais" not in parsed or "acabamentos" not in parsed:
            raise HTTPException(
                status_code=422,
                detail="variantes_json for banner must be object with 'materiais' and 'acabamentos'"
            )
```

- [ ] **Step 2: Update listar_catalogo to expose new fields**

In `main.py`, find `def listar_catalogo` (line 1199). Replace the dict built inside the loop (the one appended to `grupos[cat]`) with:

```python
grupos[cat].append({
    "id": item.id, "categoria": item.categoria,
    "descricao": item.descricao, "preco": item.preco,
    "garantia": item.garantia, "tipo": item.tipo or "unidade",
    "largura": item.largura, "altura": item.altura,
    "ativo": item.ativo, "ordem": item.ordem,
    "tipo_produto": item.tipo_produto or "produto_simples",
    "variantes_json": item.variantes_json,
})
```

- [ ] **Step 3: Update buscar_catalogo to expose new fields**

In `main.py`, find `def buscar_catalogo` (line 1217). Replace the list comprehension dict with:

```python
return [
    {"id": i.id, "categoria": i.categoria, "descricao": i.descricao,
     "preco": i.preco, "garantia": i.garantia, "tipo": i.tipo or "unidade",
     "largura": i.largura, "altura": i.altura,
     "tipo_produto": i.tipo_produto or "produto_simples",
     "variantes_json": i.variantes_json}
    for i in itens
]
```

- [ ] **Step 4: Update criar_item_catalogo with validation**

In `main.py`, find `def criar_item_catalogo` (line 1231). Replace the function body:

```python
@app.post("/api/catalogo")
def criar_item_catalogo(data: CatalogoItemInput, db: Session = Depends(get_db)):
    _validate_variantes_json(data.tipo_produto, data.variantes_json)
    item = CatalogoItem(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, **data.model_dump()}
```

- [ ] **Step 5: Update editar_item_catalogo with validation**

In `main.py`, find `def editar_item_catalogo` (line 1239). Replace the function body:

```python
@app.put("/api/catalogo/{item_id}")
def editar_item_catalogo(item_id: int, data: CatalogoItemInput, db: Session = Depends(get_db)):
    item = db.query(CatalogoItem).filter(CatalogoItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Item nao encontrado")
    _validate_variantes_json(data.tipo_produto, data.variantes_json)
    for field, value in data.model_dump().items():
        setattr(item, field, value)
    db.commit()
    return {"ok": True}
```

- [ ] **Step 6: Run all new tests — should pass now**

```bash
python -m pytest tests/test_routes.py::test_catalogo_item_tipo_produto_field tests/test_routes.py::test_catalogo_listar_returns_tipo_produto tests/test_routes.py::test_catalogo_buscar_returns_tipo_produto tests/test_routes.py::test_catalogo_variantes_json_validation -v
```

Expected: all 4 PASS

- [ ] **Step 7: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass

- [ ] **Step 8: Commit API changes**

```bash
git add main.py tests/test_routes.py
git commit -m "feat: expose tipo_produto/variantes_json in catalog API with JSON structure validation"
```

---

## Task 3: Frontend — Catalog Drawer Variant Editor

**Files:**
- Modify: `static/catalogo.html`

The existing drawer (lines 243-307) has: descricao, categoria, garantia, tipo select, dimensoes grid (hidden), preco. We add a `tipo_produto` select and a dynamic `#variantes-section` div.

- [ ] **Step 1: Add CSS for variant editor**

In `static/catalogo.html`, find the closing `</style>` tag. Insert before it:

```css
.variante-row {
    display: flex; align-items: center; gap: 10px;
    padding: 8px 0; border-bottom: 1px solid var(--glass-border);
}
.variante-row:last-child { border-bottom: none; }
.variante-row input {
    flex: 1; padding: 8px 12px; background: rgba(255,255,255,0.03);
    border: 1px solid var(--glass-border); border-radius: 8px;
    color: var(--text-main); font-size: 13px; outline: none;
}
.variante-row input:focus { border-color: var(--primary); }
.variante-row .btn-del-v {
    width: 28px; height: 28px; border-radius: 8px; border: none;
    background: rgba(239,68,68,0.1); color: #ef4444; cursor: pointer;
    display: flex; align-items: center; justify-content: center;
    flex-shrink: 0; font-size: 12px; transition: background 0.2s;
}
.variante-row .btn-del-v:hover { background: #ef4444; color: #fff; }
.v-subsection { margin-top: 12px; }
.v-subsection-title {
    font-size: 12px; font-weight: 700; color: var(--text-muted);
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 8px;
}
.btn-add-v {
    margin-top: 10px; padding: 7px 14px; font-size: 12px; border-radius: 8px;
    border: 1px dashed var(--glass-border); background: transparent;
    color: var(--primary); cursor: pointer; transition: all 0.2s; width: 100%;
}
.btn-add-v:hover { background: rgba(58,123,213,0.1); border-color: var(--primary); }
```

- [ ] **Step 2: Add tipo_produto select and variantes-section to drawer HTML**

In `static/catalogo.html`, find the closing `</div>` of the grid that contains `item-garantia` and `item-tipo` (around line 291). The full grid ends with `</div>` before the price section. Insert after that closing `</div>`:

```html
<div>
    <label class="dform-label">Tipo de Produto (Calculadora)</label>
    <select class="dform-input" id="item-tipo-produto" onchange="onTipoProdutoChange()">
        <option value="produto_simples">Produto / Servico Simples</option>
        <option value="impressao_3d">Impressao 3D (por grama)</option>
        <option value="laser">Corte / Gravacao Laser (por m²)</option>
        <option value="ploter_adesivo">Ploter / Adesivo (por m²)</option>
        <option value="banner">Banner / Lona (m² + acabamentos)</option>
    </select>
</div>

<div id="variantes-section" style="display:none;"></div>
```

- [ ] **Step 3: Add variant editor JS functions**

In `static/catalogo.html`, find the `<script>` tag. Add these functions after `showToast`:

```javascript
function onTipoProdutoChange() {
    const tipo = document.getElementById('item-tipo-produto').value;
    const section = document.getElementById('variantes-section');
    if (tipo === 'produto_simples') {
        section.style.display = 'none';
        section.innerHTML = '';
        return;
    }
    section.style.display = 'block';
    renderVariantesEditor(tipo, null);
}

function renderVariantesEditor(tipo, variantesJson) {
    const section = document.getElementById('variantes-section');
    let existing = null;
    if (variantesJson) { try { existing = JSON.parse(variantesJson); } catch(e) {} }

    if (tipo === 'impressao_3d') {
        const rows = (Array.isArray(existing) ? existing : []).map(v => vRow3D(v)).join('') || vRow3D();
        section.innerHTML = `<div class="v-subsection">
            <div class="v-subsection-title"><i class="fas fa-cube"></i> Materiais e Preco/kg</div>
            <div id="v-list">${rows}</div>
            <button type="button" class="btn-add-v" onclick="addVRow3D()">+ Adicionar Material</button>
        </div>`;
    } else if (tipo === 'laser') {
        const rows = (Array.isArray(existing) ? existing : []).map(v => vRowLaser(v)).join('') || vRowLaser();
        section.innerHTML = `<div class="v-subsection">
            <div class="v-subsection-title"><i class="fas fa-fire"></i> Material + Espessura e Preco/m²</div>
            <div id="v-list">${rows}</div>
            <button type="button" class="btn-add-v" onclick="addVRowLaser()">+ Adicionar Material</button>
        </div>`;
    } else if (tipo === 'ploter_adesivo') {
        const rows = (Array.isArray(existing) ? existing : []).map(v => vRowPloter(v)).join('') || vRowPloter();
        section.innerHTML = `<div class="v-subsection">
            <div class="v-subsection-title"><i class="fas fa-paint-roller"></i> Tipo de Vinil e Preco/m²</div>
            <div id="v-list">${rows}</div>
            <button type="button" class="btn-add-v" onclick="addVRowPloter()">+ Adicionar Vinil</button>
        </div>`;
    } else if (tipo === 'banner') {
        const mat = (existing && existing.materiais) ? existing.materiais : [];
        const acab = (existing && existing.acabamentos) ? existing.acabamentos : [];
        const matRows = mat.map(v => vRowBannerMat(v)).join('') || vRowBannerMat();
        const acabRows = acab.map(v => vRowBannerAcab(v)).join('') || vRowBannerAcab();
        section.innerHTML = `
        <div class="v-subsection">
            <div class="v-subsection-title"><i class="fas fa-flag"></i> Materiais (Preco/m²)</div>
            <div id="v-materiais">${matRows}</div>
            <button type="button" class="btn-add-v" onclick="addVRowBannerMat()">+ Adicionar Material</button>
        </div>
        <div class="v-subsection" style="margin-top:16px;">
            <div class="v-subsection-title"><i class="fas fa-tools"></i> Acabamentos Opcionais (Preco/un)</div>
            <div id="v-acabamentos">${acabRows}</div>
            <button type="button" class="btn-add-v" onclick="addVRowBannerAcab()">+ Adicionar Acabamento</button>
        </div>`;
    }
}

function vRow3D(v) {
    return `<div class="variante-row">
        <input type="text" class="v-nome" placeholder="Material (ex: PLA)" value="${v ? v.nome||'' : ''}">
        <input type="number" class="v-preco-kg" placeholder="R$/kg" step="0.01" min="0" style="max-width:90px;" value="${v ? v.preco_kg||'' : ''}">
        <button type="button" class="btn-del-v" onclick="this.closest('.variante-row').remove()"><i class="fas fa-times"></i></button>
    </div>`;
}
function addVRow3D() { document.getElementById('v-list').insertAdjacentHTML('beforeend', vRow3D()); }

function vRowLaser(v) {
    return `<div class="variante-row">
        <input type="text" class="v-nome" placeholder="Ex: MDF 3mm" value="${v ? v.nome||'' : ''}">
        <input type="number" class="v-preco-m2" placeholder="R$/m²" step="0.01" min="0" style="max-width:90px;" value="${v ? v.preco_m2||'' : ''}">
        <button type="button" class="btn-del-v" onclick="this.closest('.variante-row').remove()"><i class="fas fa-times"></i></button>
    </div>`;
}
function addVRowLaser() { document.getElementById('v-list').insertAdjacentHTML('beforeend', vRowLaser()); }

function vRowPloter(v) {
    return `<div class="variante-row">
        <input type="text" class="v-nome" placeholder="Ex: Vinil Brilho" value="${v ? v.nome||'' : ''}">
        <input type="number" class="v-preco-m2" placeholder="R$/m²" step="0.01" min="0" style="max-width:90px;" value="${v ? v.preco_m2||'' : ''}">
        <button type="button" class="btn-del-v" onclick="this.closest('.variante-row').remove()"><i class="fas fa-times"></i></button>
    </div>`;
}
function addVRowPloter() { document.getElementById('v-list').insertAdjacentHTML('beforeend', vRowPloter()); }

function vRowBannerMat(v) {
    return `<div class="variante-row">
        <input type="text" class="v-nome" placeholder="Ex: Lona Brilho" value="${v ? v.nome||'' : ''}">
        <input type="number" class="v-preco-m2" placeholder="R$/m²" step="0.01" min="0" style="max-width:90px;" value="${v ? v.preco_m2||'' : ''}">
        <button type="button" class="btn-del-v" onclick="this.closest('.variante-row').remove()"><i class="fas fa-times"></i></button>
    </div>`;
}
function addVRowBannerMat() { document.getElementById('v-materiais').insertAdjacentHTML('beforeend', vRowBannerMat()); }

function vRowBannerAcab(v) {
    return `<div class="variante-row">
        <input type="text" class="v-nome" placeholder="Ex: Ilhao" value="${v ? v.nome||'' : ''}">
        <input type="number" class="v-preco-un" placeholder="R$/un" step="0.01" min="0" style="max-width:90px;" value="${v ? v.preco_un||'' : ''}">
        <button type="button" class="btn-del-v" onclick="this.closest('.variante-row').remove()"><i class="fas fa-times"></i></button>
    </div>`;
}
function addVRowBannerAcab() { document.getElementById('v-acabamentos').insertAdjacentHTML('beforeend', vRowBannerAcab()); }

function collectVariantesJson(tipo) {
    if (tipo === 'produto_simples') return null;
    if (tipo === 'impressao_3d') {
        const rows = document.querySelectorAll('#v-list .variante-row');
        return JSON.stringify([...rows].map(r => ({
            nome: r.querySelector('.v-nome').value.trim(),
            preco_kg: parseFloat(r.querySelector('.v-preco-kg').value) || 0
        })).filter(v => v.nome));
    }
    if (tipo === 'laser') {
        const rows = document.querySelectorAll('#v-list .variante-row');
        return JSON.stringify([...rows].map(r => ({
            nome: r.querySelector('.v-nome').value.trim(),
            preco_m2: parseFloat(r.querySelector('.v-preco-m2').value) || 0
        })).filter(v => v.nome));
    }
    if (tipo === 'ploter_adesivo') {
        const rows = document.querySelectorAll('#v-list .variante-row');
        return JSON.stringify([...rows].map(r => ({
            nome: r.querySelector('.v-nome').value.trim(),
            preco_m2: parseFloat(r.querySelector('.v-preco-m2').value) || 0
        })).filter(v => v.nome));
    }
    if (tipo === 'banner') {
        const matRows = document.querySelectorAll('#v-materiais .variante-row');
        const acabRows = document.querySelectorAll('#v-acabamentos .variante-row');
        return JSON.stringify({
            materiais: [...matRows].map(r => ({
                nome: r.querySelector('.v-nome').value.trim(),
                preco_m2: parseFloat(r.querySelector('.v-preco-m2').value) || 0
            })).filter(v => v.nome),
            acabamentos: [...acabRows].map(r => ({
                nome: r.querySelector('.v-nome').value.trim(),
                preco_un: parseFloat(r.querySelector('.v-preco-un').value) || 0
            })).filter(v => v.nome)
        });
    }
    return null;
}
```

- [ ] **Step 4: Replace openDrawer with updated version**

In `static/catalogo.html`, find `function openDrawer(editData = null)` (line 468). Replace the entire function with:

```javascript
function openDrawer(editData = null) {
    const dr = document.getElementById('drawer');
    const ov = document.getElementById('drawer-overlay');
    if (editData) {
        document.getElementById('drawer-title').textContent = 'Editar Item';
        document.getElementById('item-id').value = editData.id;
        document.getElementById('item-descricao').value = editData.descricao;
        document.getElementById('item-garantia').value = editData.garantia || '';
        document.getElementById('item-preco').value = editData.preco;
        document.getElementById('item-categoria').value = editData.categoria || '';
        document.getElementById('item-tipo').value = editData.tipo || 'unidade';
        document.getElementById('item-largura').value = editData.largura || '';
        document.getElementById('item-altura').value = editData.altura || '';
        // New fields
        const tipoProd = editData.tipo_produto || 'produto_simples';
        document.getElementById('item-tipo-produto').value = tipoProd;
        const section = document.getElementById('variantes-section');
        if (tipoProd !== 'produto_simples') {
            section.style.display = 'block';
            renderVariantesEditor(tipoProd, editData.variantes_json || null);
        } else {
            section.style.display = 'none';
            section.innerHTML = '';
        }
    } else {
        document.getElementById('drawer-title').textContent = 'Novo Item';
        ['item-id','item-descricao','item-garantia','item-preco','item-categoria','item-largura','item-altura'].forEach(id => document.getElementById(id).value = '');
        document.getElementById('item-tipo').value = 'unidade';
        // Reset new fields
        document.getElementById('item-tipo-produto').value = 'produto_simples';
        document.getElementById('variantes-section').style.display = 'none';
        document.getElementById('variantes-section').innerHTML = '';
    }
    toggleDimensoes();
    dr.classList.add('active');
    ov.classList.add('active');
    setTimeout(() => document.getElementById('item-descricao').focus(), 400);
}
```

- [ ] **Step 5: Update saveItem to include new fields**

In `static/catalogo.html`, find `async function saveItem()` (line 497). Replace the `payload` object definition with:

```javascript
const tipoProd = document.getElementById('item-tipo-produto').value;
const payload = {
    descricao: document.getElementById('item-descricao').value.trim(),
    categoria: document.getElementById('item-categoria').value.trim(),
    garantia: document.getElementById('item-garantia').value.trim(),
    tipo: document.getElementById('item-tipo').value,
    preco: parseFloat(document.getElementById('item-preco').value) || 0,
    largura: parseFloat(document.getElementById('item-largura').value) || null,
    altura: parseFloat(document.getElementById('item-altura').value) || null,
    ativo: true,
    ordem: 0,
    tipo_produto: tipoProd,
    variantes_json: collectVariantesJson(tipoProd),
};
```

- [ ] **Step 6: Manual smoke test — catalog drawer**

1. Open `/catalogo.html`
2. Click "Novo Item" → `item-tipo-produto` select is visible with "Produto / Servico Simples"
3. Change to "Impressao 3D" → variant editor appears with one blank row
4. Add "PLA" at 80.0 and "PETG" at 120.0 → click "+ Adicionar Material" → new row
5. Click X on a row → row is removed
6. Save → no error, item appears in catalog list
7. Click edit on that item → `item-tipo-produto` is "Impressao 3D", PLA and PETG are pre-filled
8. Change to "Banner" → two subsections appear (Materiais + Acabamentos)
9. Save a banner item → no error
10. Edit it → both subsections pre-filled correctly

- [ ] **Step 7: Commit catalog frontend**

```bash
git add static/catalogo.html
git commit -m "feat: dynamic variant editor in catalog drawer for impressao_3d, laser, ploter_adesivo, banner"
```

---

## Task 4: Frontend — Budget Form Inline Calculator

**Files:**
- Modify: `static/novo_orcamento.html`

When a catalog item with `tipo_produto != 'produto_simples'` is selected via `selectCatalogItem()`, an inline calculator panel appears below the item row. The panel has an "Aplicar" button that is disabled until all required fields are > 0. Clicking "Aplicar" writes the computed price to the item row.

- [ ] **Step 1: Add CSS for the calculator panel**

In `static/novo_orcamento.html`, find the closing `</style>` tag. Insert before it:

```css
.calc-panel {
    background: rgba(58,123,213,0.06); border: 1px solid rgba(58,123,213,0.2);
    border-radius: 12px; padding: 14px 16px; margin-top: 4px; margin-bottom: 8px;
}
.calc-panel-title {
    font-size: 11px; font-weight: 700; color: var(--primary);
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 10px;
}
.calc-grid { display: flex; flex-wrap: wrap; gap: 10px; align-items: flex-end; }
.calc-field { display: flex; flex-direction: column; gap: 4px; min-width: 120px; }
.calc-field label { font-size: 11px; color: var(--text-muted); }
.calc-field select, .calc-field input[type="number"] {
    padding: 7px 10px; background: rgba(255,255,255,0.03);
    border: 1px solid var(--glass-border); border-radius: 8px;
    color: var(--text-main); font-size: 13px; outline: none; width: 100%;
}
.calc-field select:focus, .calc-field input:focus { border-color: var(--primary); }
.calc-footer {
    display: flex; align-items: center; justify-content: space-between;
    margin-top: 10px; flex-wrap: wrap; gap: 8px;
}
.calc-preview { font-size: 12px; color: var(--text-muted); }
.calc-preview strong { color: #10b981; font-size: 15px; }
.btn-aplicar {
    padding: 7px 18px; border-radius: 8px; border: none; font-size: 12px;
    font-weight: 700; cursor: pointer; transition: all 0.2s;
    background: #10b981; color: #fff;
}
.btn-aplicar:disabled { background: rgba(255,255,255,0.1); color: var(--text-muted); cursor: not-allowed; }
.btn-aplicar:not(:disabled):hover { background: #059669; }
.acab-list { margin-top: 8px; display: flex; flex-direction: column; gap: 5px; }
.acab-row { display: flex; align-items: center; gap: 8px; font-size: 12px; }
.acab-row label { flex: 1; cursor: pointer; color: var(--text-main); }
.acab-row input[type="checkbox"] { width: 14px; height: 14px; cursor: pointer; flex-shrink: 0; }
.acab-row input[type="number"] {
    width: 56px; padding: 4px 6px; background: rgba(255,255,255,0.03);
    border: 1px solid var(--glass-border); border-radius: 6px;
    color: var(--text-main); font-size: 12px; outline: none;
}
```

- [ ] **Step 2: Add buildCalcPanel() and recalcPanel() functions**

In `static/novo_orcamento.html`, find the `<script>` block. Add these two functions after the `selectCatalogItem` function:

```javascript
function buildCalcPanel(rowId, item) {
    const existing = document.getElementById('calc-' + rowId);
    if (existing) existing.remove();

    const tipo = item.tipo_produto;
    if (!tipo || tipo === 'produto_simples') return;

    let variantes = null;
    try { variantes = JSON.parse(item.variantes_json || 'null'); } catch(e) {}

    const row = document.getElementById(rowId);
    let html = '';

    if (tipo === 'impressao_3d') {
        const opts = Array.isArray(variantes)
            ? variantes.map(v => `<option value="${v.preco_kg}">${v.nome} (R$${v.preco_kg}/kg)</option>`).join('')
            : '<option value="">Sem materiais cadastrados</option>';
        html = `<div id="calc-${rowId}" class="calc-panel">
            <div class="calc-panel-title"><i class="fas fa-cube"></i> Calculadora — Impressao 3D</div>
            <div class="calc-grid">
                <div class="calc-field"><label>Material</label>
                    <select class="cp-mat" onchange="recalcPanel('${rowId}','${tipo}')">${opts}</select></div>
                <div class="calc-field"><label>Peso (g)</label>
                    <input type="number" class="cp-peso" min="1" step="1" placeholder="Ex: 150"
                        oninput="recalcPanel('${rowId}','${tipo}')"></div>
            </div>
            <div class="calc-footer">
                <div class="calc-preview">Preco/peca: <strong id="cp-res-${rowId}">R$ 0,00</strong></div>
                <button type="button" class="btn-aplicar" id="cp-btn-${rowId}" disabled
                    onclick="aplicarCalc('${rowId}','${tipo}')">Aplicar</button>
            </div>
        </div>`;

    } else if (tipo === 'laser' || tipo === 'ploter_adesivo') {
        const label = tipo === 'laser' ? 'Material + Espessura' : 'Tipo de Vinil';
        const icon  = tipo === 'laser' ? 'fa-fire' : 'fa-paint-roller';
        const title = tipo === 'laser' ? 'Corte Laser' : 'Ploter / Adesivo';
        const opts = Array.isArray(variantes)
            ? variantes.map(v => `<option value="${v.preco_m2}">${v.nome} (R$${v.preco_m2}/m2)</option>`).join('')
            : '<option value="">Sem materiais cadastrados</option>';
        html = `<div id="calc-${rowId}" class="calc-panel">
            <div class="calc-panel-title"><i class="fas ${icon}"></i> Calculadora — ${title}</div>
            <div class="calc-grid">
                <div class="calc-field"><label>${label}</label>
                    <select class="cp-mat" onchange="recalcPanel('${rowId}','${tipo}')">${opts}</select></div>
                <div class="calc-field"><label>Largura (cm)</label>
                    <input type="number" class="cp-larg" min="1" step="0.1" placeholder="Ex: 60"
                        oninput="recalcPanel('${rowId}','${tipo}')"></div>
                <div class="calc-field"><label>Altura (cm)</label>
                    <input type="number" class="cp-alt" min="1" step="0.1" placeholder="Ex: 90"
                        oninput="recalcPanel('${rowId}','${tipo}')"></div>
            </div>
            <div class="calc-footer">
                <div class="calc-preview">Preco/un: <strong id="cp-res-${rowId}">R$ 0,00</strong></div>
                <button type="button" class="btn-aplicar" id="cp-btn-${rowId}" disabled
                    onclick="aplicarCalc('${rowId}','${tipo}')">Aplicar</button>
            </div>
        </div>`;

    } else if (tipo === 'banner') {
        const mats  = (variantes && variantes.materiais)   ? variantes.materiais   : [];
        const acabs = (variantes && variantes.acabamentos) ? variantes.acabamentos : [];
        const matOpts = mats.map(v => `<option value="${v.preco_m2}">${v.nome} (R$${v.preco_m2}/m2)</option>`).join('')
            || '<option value="">Sem materiais cadastrados</option>';
        const acabRows = acabs.map((v, i) => `
            <div class="acab-row">
                <input type="checkbox" id="acb-${rowId}-${i}" class="cp-acab-chk"
                    data-preco="${v.preco_un}" onchange="recalcPanel('${rowId}','banner')">
                <label for="acb-${rowId}-${i}">${v.nome} (R$${v.preco_un}/un)</label>
                <input type="number" class="cp-acab-qtd" value="1" min="1" step="1"
                    oninput="recalcPanel('${rowId}','banner')">
            </div>`).join('');
        html = `<div id="calc-${rowId}" class="calc-panel">
            <div class="calc-panel-title"><i class="fas fa-flag"></i> Calculadora — Banner / Lona</div>
            <div class="calc-grid">
                <div class="calc-field"><label>Material</label>
                    <select class="cp-mat" onchange="recalcPanel('${rowId}','banner')">${matOpts}</select></div>
                <div class="calc-field"><label>Largura (cm)</label>
                    <input type="number" class="cp-larg" min="1" step="0.1" placeholder="Ex: 100"
                        oninput="recalcPanel('${rowId}','banner')"></div>
                <div class="calc-field"><label>Altura (cm)</label>
                    <input type="number" class="cp-alt" min="1" step="0.1" placeholder="Ex: 200"
                        oninput="recalcPanel('${rowId}','banner')"></div>
            </div>
            ${acabRows ? `<div class="acab-list">${acabRows}</div>` : ''}
            <div class="calc-footer">
                <div class="calc-preview">Total do item: <strong id="cp-res-${rowId}">R$ 0,00</strong></div>
                <button type="button" class="btn-aplicar" id="cp-btn-${rowId}" disabled
                    onclick="aplicarCalc('${rowId}','banner')">Aplicar</button>
            </div>
        </div>`;
    }

    if (html) row.insertAdjacentHTML('afterend', html);
}

function recalcPanel(rowId, tipo) {
    const panel = document.getElementById('calc-' + rowId);
    if (!panel) return;

    let valor = 0;
    let isValid = false;
    let descGerada = null;

    if (tipo === 'impressao_3d') {
        const precoKg = parseFloat(panel.querySelector('.cp-mat').value) || 0;
        const pesoG   = parseFloat(panel.querySelector('.cp-peso').value) || 0;
        isValid = precoKg > 0 && pesoG > 0;
        if (isValid) {
            valor = Math.round((pesoG / 1000) * precoKg * 100) / 100;
            const matNome = panel.querySelector('.cp-mat').selectedOptions[0]?.text.split(' (')[0] || '';
            descGerada = `Impressao 3D - ${matNome} - ${pesoG}g`;
        }

    } else if (tipo === 'laser' || tipo === 'ploter_adesivo') {
        const precoM2 = parseFloat(panel.querySelector('.cp-mat').value) || 0;
        const larg    = parseFloat(panel.querySelector('.cp-larg').value) || 0;
        const alt     = parseFloat(panel.querySelector('.cp-alt').value) || 0;
        const area    = (larg / 100) * (alt / 100);
        isValid = precoM2 > 0 && area > 0;
        if (isValid) {
            valor = Math.round(area * precoM2 * 100) / 100;
            const matNome  = panel.querySelector('.cp-mat').selectedOptions[0]?.text.split(' (')[0] || '';
            const tipoLabel = tipo === 'laser' ? 'Corte Laser' : 'Adesivo';
            descGerada = `${tipoLabel} - ${matNome} - ${larg}x${alt}cm (${area.toFixed(2)}m2)`;
        }

    } else if (tipo === 'banner') {
        const precoM2 = parseFloat(panel.querySelector('.cp-mat').value) || 0;
        const larg    = parseFloat(panel.querySelector('.cp-larg').value) || 0;
        const alt     = parseFloat(panel.querySelector('.cp-alt').value) || 0;
        const area    = (larg / 100) * (alt / 100);
        let acabTotal = 0;
        const acabDesc = [];
        panel.querySelectorAll('.acab-row').forEach(ar => {
            const chk = ar.querySelector('.cp-acab-chk');
            if (chk && chk.checked) {
                const preco = parseFloat(chk.dataset.preco) || 0;
                const qtd   = parseInt(ar.querySelector('.cp-acab-qtd').value) || 1;
                acabTotal += preco * qtd;
                acabDesc.push(`${qtd}x ${ar.querySelector('label')?.textContent.split(' (')[0] || ''}`);
            }
        });
        isValid = precoM2 > 0 && area > 0;
        if (isValid) {
            valor = Math.round((area * precoM2 + acabTotal) * 100) / 100;
            const matNome = panel.querySelector('.cp-mat').selectedOptions[0]?.text.split(' (')[0] || '';
            const acabStr = acabDesc.length ? ' + ' + acabDesc.join(' + ') : '';
            descGerada = `Banner ${matNome} - ${larg}x${alt}cm${acabStr}`;
        }
    }

    const resEl = document.getElementById('cp-res-' + rowId);
    if (resEl) resEl.textContent = valor.toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });

    const btn = document.getElementById('cp-btn-' + rowId);
    if (btn) btn.disabled = !isValid;

    // Store computed values on panel for aplicarCalc to use
    panel.dataset.valor = valor;
    panel.dataset.desc  = descGerada || '';
}

function aplicarCalc(rowId, tipo) {
    const panel = document.getElementById('calc-' + rowId);
    const row   = document.getElementById(rowId);
    if (!panel || !row) return;

    const valor = parseFloat(panel.dataset.valor) || 0;
    const desc  = panel.dataset.desc || '';
    if (valor <= 0) return;

    row.querySelector('.item-preco').value = valor;
    if (desc) row.querySelector('.item-desc').value = desc;
    if (tipo === 'banner') row.querySelector('.item-qtd').value = 1;

    calculateTotal();
}
```

- [ ] **Step 3: Update selectCatalogItem to call buildCalcPanel**

In `static/novo_orcamento.html`, find `function selectCatalogItem(rowId, item)` (around line 533). At the very end of the function, just before the closing `}`, add:

```javascript
// Remove any existing calc panel first
const oldPanel = document.getElementById('calc-' + rowId);
if (oldPanel) oldPanel.remove();

// Show inline calculator for special product types
if (item.tipo_produto && item.tipo_produto !== 'produto_simples') {
    // Hide metro groups (calculator controls the price directly)
    row.querySelector('.item-qtd-group').style.display = tipo === 'banner' ? 'none' : 'block';
    row.querySelector('.item-metro-group').style.display = 'none';
    row.querySelector('.item-m2-group').style.display = 'none';
    row.querySelector('.item-tipo').value = 'unidade';
    row.setAttribute('data-tipo', 'unidade');
    buildCalcPanel(rowId, item);
}
```

Note: the variable `tipo` is already defined earlier in `selectCatalogItem` as `const tipo = item.tipo || 'unidade'`. The existing show/hide logic (lines 548-563) runs before this addition, so no conflict.

- [ ] **Step 4: Manual smoke test — budget form calculators**

First create one item of each special type in `/catalogo.html` if not already done.

Then open `/novo_orcamento.html`:

**Impressao 3D test:**
1. Add a category, click item search, select the 3D item
2. Calculator panel appears with Material select and Peso field
3. "Aplicar" button is disabled (grey)
4. Fill in 150g → "Aplicar" remains disabled (precoKg from first option > 0, peso > 0 now → should enable)
5. Verify "Aplicar" becomes green/enabled
6. Click "Aplicar" → `item-preco` fills with calculated value (e.g., 12.00 for PLA 80/kg)
7. Description updates to "Impressao 3D - PLA - 150g"

**Laser test:**
1. Select laser item → panel shows Material, Largura, Altura
2. Fill in 30 and 40 cm → Aplicar enables
3. Click Aplicar → price and description fill correctly

**Ploter test:** Same as Laser but description says "Adesivo - ..."

**Banner test:**
1. Select banner item → panel shows Material, dimensions, acabamento checkboxes
2. Fill in 100x200cm → Aplicar enables
3. Check "Ilhao" checkbox, set qty=8 → total updates
4. Click Aplicar → price = area cost + ilhao cost, description updated
5. Item quantity is forced to 1

**Regression test:**
6. Select a regular catalog item (produto_simples) → no panel appears, works as before
7. Submit form → proposal generates successfully

- [ ] **Step 5: Run full test suite**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -20
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add static/novo_orcamento.html
git commit -m "feat: inline material calculator panel with Aplicar button for 3D/laser/ploter/banner items"
```

---

## Final Verification

- [ ] **Run full test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -30
```

Expected: all existing tests pass + 4 new catalog tests pass

- [ ] **Verify no regressions on existing catalog items**

1. Open `/catalogo.html` — existing items display correctly
2. Open existing simple item → `item-tipo-produto = "produto_simples"`, no variant section
3. Open `/novo_orcamento.html`, select a simple catalog item → no calculator panel, works as before

- [ ] **Check commit log**

```bash
git log --oneline -6
```

Expected (approximate):
```
feat: inline material calculator panel with Aplicar button for 3D/laser/ploter/banner items
feat: dynamic variant editor in catalog drawer for impressao_3d, laser, ploter_adesivo, banner
feat: expose tipo_produto/variantes_json in catalog API with JSON structure validation
feat: add tipo_produto and variantes_json to CatalogoItem; fix CatalogoItemInput missing largura/altura
```
