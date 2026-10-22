(() => {
const { TIPOS, STATUS, ANDARES, CROP } = Core;
const KEY = 'fsbr_inv_v1';
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

// ---------- estado ----------
let S;
try { S = JSON.parse(localStorage.getItem(KEY)); } catch (e) { S = null; }
if (!S || !S.ativos) S = { ativos: JSON.parse(JSON.stringify(window.SEED_ATIVOS || [])), log: [] };
const save = () => { try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) { toast('Não foi possível salvar no navegador'); } };
const ui = { aba: 'painel', f: { tipo: '', status: '', setor: '', andar: '', zona: '', q: '' }, sort: 'id', dir: 1, andar: 0, zona: '', sel: null, imp: null };
const setores = () => [...new Set(S.ativos.map((a) => a.setor).filter(Boolean))].sort((a, b) => a.localeCompare(b, 'pt'));
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('on'); setTimeout(() => t.classList.remove('on'), 2600); }
const pill = (st) => `<span class="pill" style="background:${STATUS[st].cor}">${STATUS[st].nome}</span>`;
const tpill = (t) => `<span class="pill" style="background:${TIPOS[t].cor}">${TIPOS[t].nome}</span>`;
const count = (arr, fn) => { const m = new Map(); arr.forEach((a) => { const k = fn(a); m.set(k, (m.get(k) || 0) + 1); }); return m; };
const localTxt = (a) => a.andar == null ? '—' : `${ANDARES[a.andar].nome}${a.zona ? ' · Parte ' + a.zona : ''}`;

function filtrar(f = ui.f) {
  const q = Core.norm(f.q);
  return S.ativos.filter((a) => (!f.tipo || a.tipo === f.tipo) && (!f.status || a.status === f.status)
    && (!f.setor || (f.setor === '__none' ? !a.setor : a.setor === f.setor))
    && (f.andar === '' || (f.andar === '__none' ? a.andar == null : String(a.andar) === String(f.andar)))
    && (!f.zona || a.zona === f.zona)
    && (!q || Core.norm([a.id, a.serial, a.person, a.obs, a.setor, a.supplier].join(' ')).includes(q)));
}
function irLista(f) { ui.f = { tipo: '', status: '', setor: '', andar: '', zona: '', q: '', ...f }; ir('lista'); }

// ---------- painel ----------
function painel() {
  const A = S.ativos.filter((a) => !a.ausente), tot = A.length;
  const tipos = Object.keys(TIPOS).filter((t) => t !== 'outro' || A.some((a) => a.tipo === 'outro'));
  const kpi = (lbl, n, f, sub) => `<div class="card kpi" data-f='${JSON.stringify(f)}'><div class="n">${n}</div><div class="l">${lbl}</div>${sub ? `<small>${sub}</small>` : ''}</div>`;
  const por = (t) => { const l = A.filter((a) => a.tipo === t); const c = (s) => l.filter((a) => a.status === s).length; return `${c('operacional')} operac. · ${c('backup')} backup · ${c('instalar')} a instalar`; };
  const barra = (c, total) => `<div class="barra">${Object.keys(STATUS).map((s) => c[s] ? `<i style="width:${c[s] / total * 100}%;background:${STATUS[s].cor}" title="${STATUS[s].nome}: ${c[s]}"></i>` : '').join('')}</div>`;
  // matriz tipo × status
  const mat = `<table><thead><tr><th>Tipo</th>${Object.keys(STATUS).filter((s) => s !== 'outro').map((s) => `<th>${STATUS[s].nome}</th>`).join('')}<th>Total</th></tr></thead><tbody>${tipos.map((t) => {
    const l = A.filter((a) => a.tipo === t);
    return `<tr><td>${tpill(t)}</td>${['operacional', 'backup', 'instalar'].map((s) => `<td><a href="#" data-f='${JSON.stringify({ tipo: t, status: s })}'>${l.filter((a) => a.status === s).length}</a></td>`).join('')}<td><b>${l.length}</b></td></tr>`;
  }).join('')}</tbody></table>`;
  // por setor
  const sm = new Map();
  A.forEach((a) => { const k = a.setor || '__none'; (sm.get(k) || sm.set(k, []).get(k)).push(a); });
  const rows = [...sm].sort((a, b) => b[1].length - a[1].length), max = Math.max(1, ...rows.map((r) => r[1].length));
  const setorHtml = rows.map(([k, l]) => { const c = {}; l.forEach((a) => c[a.status] = (c[a.status] || 0) + 1);
    return `<div class="lin" data-f='${JSON.stringify({ setor: k })}'><span>${k === '__none' ? '<i class="mut">Sem setor definido</i>' : esc(k)}</span><div style="width:${l.length / max * 100}%">${barra(c, l.length)}</div><span>${l.length}</span></div>`; }).join('');
  // por andar / parte
  const loc = (a) => a.andar == null ? 'Sem localização' : `${ANDARES[a.andar].nome} · ${a.zona ? 'Parte ' + a.zona : 'sem parte'}`;
  const lm = [...count(A, loc)].sort((a, b) => b[1] - a[1]);
  const locHtml = lm.map(([k, n]) => `<div class="lin" style="cursor:default"><span>${esc(k)}</span><div style="width:${n / tot * 100}%"><div class="barra"><i style="width:100%;background:#1f6feb"></i></div></div><span>${n}</span></div>`).join('');
  const alertas = Core.qualidade(S.ativos).filter((x) => x.sev === 'alta').length;
  return `<div class="grid g4">
    ${kpi('Total de equipamentos', tot, {}, `${A.filter((a) => a.status === 'operacional').length} operacionais · ${A.filter((a) => a.status === 'backup').length} em backup`)}
    ${tipos.map((t) => kpi(TIPOS[t].plural, A.filter((a) => a.tipo === t).length, { tipo: t }, por(t))).join('')}
    ${kpi('Em backup', A.filter((a) => a.status === 'backup').length, { status: 'backup' }, 'Reserva disponível')}
    ${kpi('Alertas de qualidade', alertas, null, 'Ver histórico & qualidade')}
  </div>
  <div class="grid g2" style="margin-top:12px">
    <div class="card"><h3>Tipo × status</h3>${mat}</div>
    <div class="card"><h3>Equipamentos por andar / parte da planta</h3>${locHtml}</div>
    <div class="card" style="grid-column:1/-1"><h3>Equipamentos por setor <span class="mut">(clique para filtrar)</span></h3>${setorHtml}
      <div class="leg">${Object.keys(STATUS).map((s) => `<span><b style="background:${STATUS[s].cor}"></b>${STATUS[s].nome}</span>`).join('')}</div></div>
  </div>`;
}

// ---------- lista ----------
const COLS = [['id', 'Asset ID'], ['tipo', 'Tipo'], ['status', 'Status'], ['person', 'Responsável'], ['setor', 'Setor'], ['local', 'Local'], ['serial', 'Nº série'], ['obs', 'Obs']];
function lista() {
  const f = ui.f, l = filtrar().sort((a, b) => {
    const g = (x) => ui.sort === 'local' ? (x.andar ?? 9) * 100 + (x.zona || '').charCodeAt(0) || 0 : (x[ui.sort] ?? '');
    const A = g(a), B = g(b); return (typeof A === 'number' ? A - B : String(A).localeCompare(String(B), 'pt', { numeric: true })) * ui.dir; });
  const opt = (obj, v) => Object.keys(obj).filter((k) => k !== 'outro').map((k) => `<option value="${k}" ${v === k ? 'selected' : ''}>${obj[k].nome}</option>`).join('');
  return `<div class="tools">
    <input id="q" type="search" placeholder="Buscar ID, série, pessoa, setor…" value="${esc(f.q)}" style="min-width:240px">
    <select data-k="tipo"><option value="">Todos os tipos</option>${opt(TIPOS, f.tipo)}</select>
    <select data-k="status"><option value="">Todos os status</option>${opt(STATUS, f.status)}</select>
    <select data-k="setor"><option value="">Todos os setores</option><option value="__none" ${f.setor === '__none' ? 'selected' : ''}>Sem setor</option>${setores().map((s) => `<option ${f.setor === s ? 'selected' : ''}>${esc(s)}</option>`).join('')}</select>
    <select data-k="andar"><option value="">Todos os andares</option><option value="__none" ${f.andar === '__none' ? 'selected' : ''}>Sem localização</option>${ANDARES.map((a, i) => `<option value="${i}" ${String(f.andar) === String(i) ? 'selected' : ''}>${a.nome}</option>`).join('')}</select>
    <span class="mut">${l.length} de ${S.ativos.length}</span><span style="flex:1"></span>
    <button class="b" id="limpar">Limpar filtros</button><button class="b" id="novo">+ Equipamento</button>
    <button class="b" id="bulk">Atribuir filtrados…</button><button class="b p" id="exp">Exportar Excel</button></div>
  <div class="tw"><table><thead><tr>${COLS.map(([k, n]) => `<th data-s="${k}">${n}${ui.sort === k ? (ui.dir > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr></thead><tbody>
  ${l.map((a) => `<tr data-id="${a.id}" class="${a.ausente ? 'ausente' : ''}"><td><b>${a.id}</b>${a.ausente ? ' <span title="Ausente no último TopDesk">⚠️</span>' : ''}</td><td>${tpill(a.tipo)}</td><td>${pill(a.status)}</td><td>${esc(a.person) || '<span class="mut">—</span>'}</td><td>${esc(a.setor) || '<span class="mut">—</span>'}</td><td>${localTxt(a)}</td><td>${esc(a.serial)}</td><td class="mut">${esc(a.obs)}</td></tr>`).join('')}
  </tbody></table></div>`;
}
function dlgEditar(id) {
  const a = id ? S.ativos.find((x) => x.id === id) : { id: '', tipo: 'laptop', status: 'operacional', andar: null, zona: '' };
  const d = $('#dlg'), op = (o, v) => Object.keys(o).map((k) => `<option value="${k}" ${v === k ? 'selected' : ''}>${o[k].nome}</option>`).join('');
  d.innerHTML = `<form method="dialog"><h3>${id ? 'Editar ' + id : 'Novo equipamento'}</h3>
  ${id ? '' : '<label>Asset ID</label><input name="id" required>'}
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 10px"><div><label>Tipo</label><select name="tipo">${op(TIPOS, a.tipo)}</select></div><div><label>Status</label><select name="status">${op(STATUS, a.status)}</select></div>
  <div><label>Responsável</label><input name="person" value="${esc(a.person)}"></div><div><label>Nº série</label><input name="serial" value="${esc(a.serial)}"></div>
  <div><label>Setor</label><input name="setor" list="dl-setor" value="${esc(a.setor)}"><datalist id="dl-setor">${setores().map((s) => `<option>${esc(s)}</option>`).join('')}</datalist></div><div><label>Fornecedor</label><input name="supplier" value="${esc(a.supplier)}"></div>
  <div><label>Andar</label><select name="andar"><option value="">—</option>${ANDARES.map((x, i) => `<option value="${i}" ${a.andar === i ? 'selected' : ''}>${x.nome}</option>`).join('')}</select></div>
  <div><label>Parte</label><select name="zona"><option value="">—</option>${'ABCDEFGH'.split('').map((z) => `<option ${a.zona === z ? 'selected' : ''}>${z}</option>`).join('')}</select></div></div>
  <label>Obs</label><textarea name="obs" rows="2">${esc(a.obs)}</textarea>
  ${id ? '<p class="mut">Campos do TopDesk (tipo, status, responsável, série, fornecedor, obs) serão sobrescritos na próxima importação; setor, andar, parte e posição na planta são mantidos.</p>' : ''}
  <div style="display:flex;gap:8px;margin-top:12px"><button class="b p" value="ok">Salvar</button><button class="b" value="x" formnovalidate>Cancelar</button>${id ? '<button class="b" value="del" formnovalidate style="margin-left:auto">Excluir</button>' : ''}</div></form>`;
  d.onclose = () => {
    const v = d.returnValue; if (v === 'del' && confirm('Excluir ' + id + '?')) { S.ativos = S.ativos.filter((x) => x.id !== id); logar(id, 'alterado', 'Excluído manualmente'); save(); render(); return; }
    if (v !== 'ok') return;
    const fd = new FormData(d.querySelector('form')), o = Object.fromEntries(fd);
    const dados = { ...o, andar: o.andar === '' ? null : +o.andar }; delete dados.id;
    if (!id) { const nid = o.id.trim().toUpperCase(); if (S.ativos.some((x) => x.id === nid)) return toast('Asset ID já existe'); S.ativos.push({ id: nid, ...dados, x: null, y: null, ausente: false }); logar(nid, 'novo', 'Criado manualmente'); }
    else { const dif = Object.keys(dados).filter((k) => String(a[k] ?? '') !== String(dados[k] ?? '')); Object.assign(a, dados); if (dif.length) { if (dif.some((k) => k === 'andar' || k === 'zona')) { a.x = a.y = null; } logar(id, 'alterado', 'Edição manual: ' + dif.join(', ')); } }
    save(); render();
  };
  d.returnValue = ''; d.showModal();
}
function logar(id, tipo, det) { S.log.unshift({ t: new Date().toISOString(), id, tipo, det, arq: 'manual' }); S.log = S.log.slice(0, 2000); }
function dlgBulk() {
  const l = filtrar(), d = $('#dlg');
  d.innerHTML = `<form method="dialog"><h3>Atribuir a ${l.length} equipamento(s) filtrado(s)</h3><p class="mut">Deixe em branco o que não quiser alterar.</p>
  <label>Setor</label><input name="setor" list="dl-s2"><datalist id="dl-s2">${setores().map((s) => `<option>${esc(s)}</option>`).join('')}</datalist>
  <label>Andar</label><select name="andar"><option value="">(manter)</option>${ANDARES.map((x, i) => `<option value="${i}">${x.nome}</option>`).join('')}</select>
  <label>Parte</label><select name="zona"><option value="">(manter)</option>${'ABCDEFGH'.split('').map((z) => `<option>${z}</option>`).join('')}</select>
  <div style="display:flex;gap:8px;margin-top:12px"><button class="b p" value="ok">Aplicar</button><button class="b" value="x" formnovalidate>Cancelar</button></div></form>`;
  d.onclose = () => { if (d.returnValue !== 'ok') return; const o = Object.fromEntries(new FormData(d.querySelector('form')));
    l.forEach((a) => { if (o.setor) a.setor = o.setor.trim(); if (o.andar !== '') { a.andar = +o.andar; a.x = a.y = null; } if (o.zona) { a.zona = o.zona; a.x = a.y = null; } });
    logar(`${l.length} itens`, 'alterado', `Atribuição em lote: ${Object.entries(o).filter(([, v]) => v).map(([k, v]) => k + '=' + v).join(', ')}`); save(); render(); toast('Atribuído'); };
  d.returnValue = ''; d.showModal();
}
function exportar() {
  const rows = filtrar().map((a) => ({ 'Asset ID': a.id, Tipo: TIPOS[a.tipo].nome, Status: STATUS[a.status].nome, Responsável: a.person, Setor: a.setor, Andar: a.andar == null ? '' : ANDARES[a.andar].nome, Parte: a.zona, 'Nº série': a.serial, Fornecedor: a.supplier, Obs: a.obs, 'Ausente no TopDesk': a.ausente ? 'Sim' : '' }));
  const wb = XLSX.utils.book_new(); XLSX.utils.book_append_sheet(wb, XLSX.utils.json_to_sheet(rows), 'Inventário');
  XLSX.writeFile(wb, `inventario-fsbr-${new Date().toISOString().slice(0, 10)}.xlsx`);
}

// ---------- planta ----------
const zr = (andar, z) => { const [x1, y1, x2, y2] = ANDARES[andar].zonas[z]; return { l: (x1 - CROP.x) / CROP.w * 100, t: (y1 - CROP.y) / CROP.h * 100, w: (x2 - x1) / CROP.w * 100, h: (y2 - y1) / CROP.h * 100 }; };
const ZCOR = { A: '#f0a030', B: '#6a5acd', C: '#d6457a', D: '#4caf50', E: '#d4c020', F: '#2a9d8f', G: '#4aa3df', H: '#1f6feb' };
function planta() {
  const an = ui.andar, A = S.ativos.filter((a) => !a.ausente);
  const doAndar = A.filter((a) => a.andar === an), zonas = Object.keys(ANDARES[an].zonas);
  const sel = ui.sel && S.ativos.find((a) => a.id === ui.sel);
  const zhtml = zonas.map((z) => { const r = zr(an, z), n = doAndar.filter((a) => a.zona === z).length;
    return `<div class="zona ${ui.zona === z ? 'on' : ''}" data-z="${z}" style="left:${r.l}%;top:${r.t}%;width:${r.w}%;height:${r.h}%;border-color:${ZCOR[z]};background:${ZCOR[z]}22"><span class="rot">Parte ${z}</span><span class="qt">${n}</span></div>`; }).join('');
  const pins = doAndar.filter((a) => a.x != null).map((a) => `<div class="pin ${a.tipo === 'impressora' ? 'sq' : ''} ${a.id === ui.sel ? 'sel' : ''}" data-id="${a.id}" style="left:${a.x}%;top:${a.y}%;background:${TIPOS[a.tipo].cor}" title="${a.id} · ${esc(a.person || a.obs || a.setor)}"></div>`).join('');
  const naZona = ui.zona ? doAndar.filter((a) => a.zona === ui.zona) : [];
  const semPos = A.filter((a) => a.x == null && (a.andar == null || a.andar === an)).sort((a, b) => (b.zona === ui.zona && !!ui.zona) - (a.zona === ui.zona && !!ui.zona));
  const item = (a) => `<div class="item ${a.id === ui.sel ? 'sel' : ''}" data-pick="${a.id}"><span>${tpill(a.tipo)} <b>${a.id}</b> <span class="mut">${esc(a.person || a.obs || '')}</span></span>${pill(a.status)}</div>`;
  const porTipo = Object.keys(TIPOS).filter((t) => t !== 'outro').map((t) => `<span><b style="background:${TIPOS[t].cor}"></b>${TIPOS[t].nome} (${doAndar.filter((a) => a.tipo === t).length})</span>`).join('');
  return `<div class="tools">${ANDARES.map((x, i) => `<button class="b ${i === an ? 'p' : ''}" data-andar="${i}">${x.nome} <span style="opacity:.7">(${A.filter((a) => a.andar === i).length})</span></button>`).join('')}
    <span class="leg" style="margin:0 0 0 8px">${porTipo}</span></div>
  <div class="planta"><div>
    <div class="dica">${sel ? `<b>${sel.id}</b> selecionado — <b>clique no mapa</b> para posicionar (define andar e parte automaticamente) ou arraste o pino. <a href="#" id="desel">cancelar</a>` : 'Clique numa <b>parte</b> para ver seus equipamentos; escolha um equipamento à direita e clique no mapa para posicioná-lo. Pinos podem ser arrastados.'}</div>
    <div class="mapa"><div class="in" id="in"><img src="${ANDARES[an].img}" alt="Planta ${ANDARES[an].nome}" draggable="false">${zhtml}${pins}</div></div></div>
    <div class="lado">
      <div class="card"><h3>${ui.zona ? `Parte ${ui.zona} · ${ANDARES[an].nome}` : ANDARES[an].nome} <a href="#" id="ver" class="mut" style="float:right;font-weight:400">ver na lista</a></h3>
        ${ui.zona ? (naZona.length ? naZona.map(item).join('') : '<span class="mut">Nenhum equipamento nesta parte.</span>') : `<span class="mut">${doAndar.length} equipamento(s) neste andar. Selecione uma parte.</span>`}</div>
      <div class="card"><h3>Sem posição no mapa (${semPos.length})</h3>
        ${semPos.slice(0, 60).map(item).join('') || '<span class="mut">Tudo posicionado 🎉</span>'}${semPos.length > 60 ? `<p class="mut">+${semPos.length - 60}… use filtros na lista para atribuir em lote.</p>` : ''}</div>
    </div></div>`;
}
function bindPlanta() {
  const inn = $('#in'); if (!inn) return;
  const pos = (e) => { const r = inn.getBoundingClientRect(); return { x: (e.clientX - r.left) / r.width * 100, y: (e.clientY - r.top) / r.height * 100 }; };
  const zonaEm = (p) => { const px = p.x / 100 * CROP.w + CROP.x, py = p.y / 100 * CROP.h + CROP.y;
    for (const [z, [x1, y1, x2, y2]] of Object.entries(ANDARES[ui.andar].zonas)) if (px >= x1 && px <= x2 && py >= y1 && py <= y2) return z; return ''; };
  const colocar = (a, p) => { a.andar = ui.andar; a.x = +p.x.toFixed(2); a.y = +p.y.toFixed(2); a.zona = zonaEm(p) || a.zona; save(); };
  let drag = null, moved = false;
  inn.addEventListener('pointerdown', (e) => { const pin = e.target.closest('.pin'); if (pin) { drag = S.ativos.find((a) => a.id === pin.dataset.id); moved = false; ui.sel = drag.id; inn.setPointerCapture(e.pointerId); e.preventDefault(); } });
  inn.addEventListener('pointermove', (e) => { if (!drag) return; moved = true; const p = pos(e); const el = inn.querySelector(`.pin[data-id="${drag.id}"]`); el.style.left = p.x + '%'; el.style.top = p.y + '%'; });
  inn.addEventListener('pointerup', (e) => { if (!drag) return; const a = drag; drag = null; if (moved) { colocar(a, pos(e)); logar(a.id, 'alterado', `Movido na planta (${ANDARES[a.andar].nome}, Parte ${a.zona || '—'})`); save(); } render(); });
  inn.addEventListener('click', (e) => {
    if (e.target.closest('.pin')) return;
    const p = pos(e), sel = ui.sel && S.ativos.find((a) => a.id === ui.sel);
    if (sel) { colocar(sel, p); logar(sel.id, 'alterado', `Posicionado na planta (${ANDARES[sel.andar].nome}, Parte ${sel.zona || '—'})`); save(); toast(`${sel.id} → ${localTxt(sel)}`); ui.sel = null; render(); }
    else { const z = e.target.closest('.zona'); ui.zona = z ? z.dataset.z : ''; render(); }
  });
}

// ---------- importar ----------
function importar() {
  const p = ui.imp;
  return `<div class="grid g2"><div>
    <div class="drop" id="drop"><p style="font-size:18px;margin:0"><b>Solte aqui a exportação do TopDesk</b> (.xlsx)</p><p class="mut">ou clique para escolher. Cada aba vira um tipo: <b>Laptop</b>, <b>PC - Tiny PC</b>, <b>Impressora</b>…<br>A chave é o <b>Asset ID</b>: existentes são atualizados (status, responsável, série, obs, fornecedor), novos são criados, e quem sumiu é sinalizado — setor, andar e posição na planta nunca são apagados.</p><input type="file" id="arq" accept=".xlsx,.xls,.csv" hidden></div>
    ${p ? `<div class="card" style="margin-top:12px"><h3>Pré-visualização · ${esc(p.nome)}</h3>
      <div class="grid g4"><div><div class="kpi"><div class="n" style="color:var(--ok)">${p.res.novos}</div><div class="l">novos</div></div></div><div><div class="kpi"><div class="n" style="color:var(--info)">${p.res.alterados}</div><div class="l">alterados</div></div></div><div><div class="kpi"><div class="n">${p.res.iguais}</div><div class="l">sem mudança</div></div></div><div><div class="kpi"><div class="n" style="color:var(--warn)">${p.res.ausentes}</div><div class="l">ausentes</div></div></div></div>
      ${p.res.duplicados ? `<p class="sev media">${p.res.duplicados} linha(s) duplicada(s) no arquivo foram ignoradas.</p>` : ''}
      <p class="mut">Abas lidas: ${p.abas.map((a) => `${esc(a.nome)} (${a.n})`).join(', ')}</p>
      <div style="display:flex;gap:8px"><button class="b p" id="aplicar">Aplicar importação</button><button class="b" id="cancimp">Cancelar</button></div>
      <div class="tw" style="margin-top:10px;max-height:260px"><table><tbody>${p.log.slice(0, 200).map((l) => `<tr><td><b>${l.id}</b></td><td>${l.tipo}</td><td>${esc(l.det)}</td></tr>`).join('') || '<tr><td class="mut">Nada a alterar.</td></tr>'}</tbody></table></div></div>` : ''}
  </div><div class="card"><h3>Backup dos dados</h3><p class="mut">Os dados ficam salvos neste navegador. Exporte um backup para levar a outro computador ou restaurar.</p>
    <div class="tools"><button class="b" id="bkp">Baixar backup (.json)</button><button class="b" id="rst">Restaurar backup…</button><input type="file" id="rfile" accept=".json" hidden></div>
    <p class="mut">Última importação: ${esc((S.log.find((l) => l.arq && l.arq !== 'manual') || {}).arq || 'dados de exemplo')}</p></div></div>`;
}
async function lerArquivo(file) {
  const wb = XLSX.read(await file.arrayBuffer());
  let novos = [], abas = [];
  for (const n of wb.SheetNames) { const l = Core.linhasParaAtivos(XLSX.utils.sheet_to_json(wb.Sheets[n], { defval: '' }), n); if (l.length) { abas.push({ nome: n, n: l.length }); novos = novos.concat(l); } }
  if (!novos.length) return toast('Nenhuma linha com "Asset ID" encontrada');
  const copia = JSON.parse(JSON.stringify(S.ativos)), quando = new Date().toISOString();
  const { res, log } = Core.aplicarImportacao(copia, novos, quando, file.name);
  ui.imp = { nome: file.name, novos, abas, res, log, quando }; render();
}

// ---------- auditoria ----------
function auditoria() {
  const q = Core.qualidade(S.ativos), ord = { alta: 0, media: 1, baixa: 2 };
  q.sort((a, b) => ord[a.sev] - ord[b.sev]);
  const cnt = count(q, (x) => x.sev);
  return `<div class="grid g2"><div class="card"><h3>Qualidade dos dados · ${cnt.get('alta') || 0} alta · ${cnt.get('media') || 0} média · ${cnt.get('baixa') || 0} baixa</h3>
    <div class="tw" style="max-height:60vh"><table><tbody>${q.slice(0, 400).map((x) => `<tr><td class="sev ${x.sev}">${x.sev}</td><td><b>${esc(x.id)}</b></td><td>${esc(x.msg)}</td></tr>`).join('') || '<tr><td>Nenhum problema 🎉</td></tr>'}</tbody></table></div></div>
    <div class="card"><h3>Histórico de mudanças (trilha de auditoria)</h3><div class="tw" style="max-height:60vh"><table><tbody>${S.log.slice(0, 300).map((l) => `<tr><td class="mut" style="white-space:nowrap">${new Date(l.t).toLocaleString('pt-BR')}</td><td><b>${esc(l.id)}</b></td><td>${esc(l.det)}<div class="mut">${esc(l.arq)}</div></td></tr>`).join('') || '<tr><td class="mut">Sem registros ainda. Importe uma planilha ou edite equipamentos.</td></tr>'}</tbody></table></div></div></div>`;
}

// ---------- render / eventos ----------
const VIEWS = { painel, planta, lista, importar, auditoria };
function ir(aba) { ui.aba = aba; render(); }
function render() {
  document.querySelectorAll('#abas button').forEach((b) => b.classList.toggle('on', b.dataset.aba === ui.aba));
  $('#main').innerHTML = VIEWS[ui.aba](); bind();
}
function bind() {
  const m = $('#main');
  m.querySelectorAll('[data-f]').forEach((el) => el.onclick = (e) => { e.preventDefault(); irLista(JSON.parse(el.dataset.f)); });
  m.querySelectorAll('.kpi:not([data-f])').forEach((el) => { if (ui.aba === 'painel') el.onclick = () => ir('auditoria'); });
  if (ui.aba === 'lista') {
    const q = $('#q'); q.oninput = () => { ui.f.q = q.value; const pos = q.selectionStart; render(); const n = $('#q'); n.focus(); n.setSelectionRange(pos, pos); };
    m.querySelectorAll('select[data-k]').forEach((s) => s.onchange = () => { ui.f[s.dataset.k] = s.value; render(); });
    m.querySelectorAll('th[data-s]').forEach((th) => th.onclick = () => { ui.dir = ui.sort === th.dataset.s ? -ui.dir : 1; ui.sort = th.dataset.s; render(); });
    m.querySelectorAll('tbody tr').forEach((tr) => tr.onclick = () => dlgEditar(tr.dataset.id));
    $('#limpar').onclick = () => { ui.f = { tipo: '', status: '', setor: '', andar: '', zona: '', q: '' }; render(); };
    $('#novo').onclick = () => dlgEditar(null); $('#bulk').onclick = dlgBulk; $('#exp').onclick = exportar;
  }
  if (ui.aba === 'planta') {
    m.querySelectorAll('[data-andar]').forEach((b) => b.onclick = () => { ui.andar = +b.dataset.andar; ui.zona = ''; render(); });
    m.querySelectorAll('[data-pick]').forEach((b) => b.onclick = () => { ui.sel = ui.sel === b.dataset.pick ? null : b.dataset.pick; const a = S.ativos.find((x) => x.id === ui.sel); if (a && a.andar != null && a.andar !== ui.andar) ui.andar = a.andar; render(); });
    const d = $('#desel'); if (d) d.onclick = (e) => { e.preventDefault(); ui.sel = null; render(); };
    const v = $('#ver'); if (v) v.onclick = (e) => { e.preventDefault(); irLista({ andar: ui.andar, zona: ui.zona }); };
    bindPlanta();
  }
  if (ui.aba === 'importar') {
    const drop = $('#drop'), inp = $('#arq');
    drop.onclick = () => inp.click(); inp.onchange = () => inp.files[0] && lerArquivo(inp.files[0]);
    drop.ondragover = (e) => { e.preventDefault(); drop.classList.add('over'); }; drop.ondragleave = () => drop.classList.remove('over');
    drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove('over'); e.dataTransfer.files[0] && lerArquivo(e.dataTransfer.files[0]); };
    const ap = $('#aplicar'); if (ap) { ap.onclick = () => { const p = ui.imp, { res, log } = Core.aplicarImportacao(S.ativos, p.novos, p.quando, p.nome); S.log = log.reverse().concat(S.log).slice(0, 2000); save(); ui.imp = null; toast(`Importado: ${res.novos} novos, ${res.alterados} alterados, ${res.ausentes} ausentes`); ir('painel'); }; $('#cancimp').onclick = () => { ui.imp = null; render(); }; }
    $('#bkp').onclick = () => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(S)], { type: 'application/json' })); a.download = `backup-inventario-${new Date().toISOString().slice(0, 10)}.json`; a.click(); };
    $('#rst').onclick = () => $('#rfile').click();
    $('#rfile').onchange = async (e) => { try { const j = JSON.parse(await e.target.files[0].text()); if (!Array.isArray(j.ativos)) throw 0; if (!confirm('Substituir todos os dados atuais pelo backup?')) return; S = j; S.log = S.log || []; save(); toast('Backup restaurado'); ir('painel'); } catch (x) { toast('Arquivo de backup inválido'); } };
  }
}
$('#abas').onclick = (e) => { const b = e.target.closest('button'); if (b) ir(b.dataset.aba); };
render();
})();
