/* Planta: ver, filtrar e posicionar equipamentos no ponto exato (clique ou arraste; setas ajustam). */
(() => {
  const D = JSON.parse($('#dados').textContent);
  const eqs = D.equipamentos, porId = new Map(eqs.map((e) => [e.id, e]));
  const setorPor = new Map(D.setores.map((s) => [s.id, s]));
  const P = new URLSearchParams(location.search);
  let pav = +P.get('pav') || lsGet('pav', 0);
  if (!D.pavimentos.some((p) => p.id === pav)) pav = D.pavimentos[0].id;
  let zoom = lsGet('zoom', 1), sel = null, setorSel = null, q = '';
  const filtro = { tipo: new Set(), status: new Set() };      // vazio = mostra tudo
  let mapa = null;

  const esconde = (e) => (filtro.tipo.size && !filtro.tipo.has(e.tipo)) || (filtro.status.size && !filtro.status.has(e.status));
  const doAndar = () => eqs.filter((e) => e.pavimento === pav && e.x !== null);
  const rotuloEq = (e) => `<span class="pill tp-${e.tipo}">${esc(D.tipos[e.tipo])}</span> <b>${esc(e.asset_id)}</b> <span class="mut">${esc(e.responsavel || e.obs || '')}</span>`;

  function barra() {
    const b = $('#barra'); b.innerHTML = '';
    D.pavimentos.forEach((p) => {
      const n = eqs.filter((e) => e.pavimento === p.id && e.x !== null).length;
      const x = document.createElement('button'); x.className = 'b' + (p.id === pav ? ' p' : ''); x.textContent = `${p.nome} (${n})`;
      x.onclick = () => { pav = p.id; lsSet('pav', pav); setorSel = null; construir(); }; b.append(x);
    });
    const chip = (grupo, chave, texto, cls, n) => {
      const x = document.createElement('button'); x.className = 'b' + (filtro[grupo].has(chave) ? ' on' : '');
      x.innerHTML = `<span class="pill ${cls}">${esc(texto)}</span> ${n}`;
      x.onclick = () => { filtro[grupo].has(chave) ? filtro[grupo].delete(chave) : filtro[grupo].add(chave); barra(); overlay(); }; b.append(x);
    };
    const sep = () => { const s = document.createElement('span'); s.className = 'mut'; s.textContent = '│'; b.append(s); };
    sep(); Object.keys(D.tipos).forEach((t) => { const n = eqs.filter((e) => e.tipo === t).length; if (n) chip('tipo', t, D.tipos[t], 'tp-' + t, n); });
    sep(); Object.keys(D.status).forEach((s) => { const n = eqs.filter((e) => e.status === s).length; if (n) chip('status', s, D.status[s], 'st-' + s, n); });
    b.append(controlesZoom(zoom, (z) => { zoom = z; lsSet('zoom', z); construir(); }));
  }

  function construir() {
    const p = D.pavimentos.find((x) => x.id === pav);
    mapa = montarMapa($('#mapa'), p.imagem, zoom);
    mapa.stage.addEventListener('pointerdown', apertou); mapa.stage.addEventListener('pointermove', moveu);
    mapa.stage.addEventListener('pointerup', soltou); mapa.stage.addEventListener('click', clicou);
    barra(); overlay(); lateral();
  }

  function overlay() {
    const { svg, layer } = mapa; svg.innerHTML = ''; layer.innerHTML = '';
    const sets = new Set();
    D.areas.filter((a) => a.pavimento === pav).forEach((a) => {
      const s = setorPor.get(a.setor); if (!s) return;
      const pg = document.createElementNS(NS, 'polygon'); pg.setAttribute('points', pts2str(a.pontos)); pg.dataset.setor = s.id;
      const ativo = setorSel === s.id;
      pg.setAttribute('fill', s.cor); pg.setAttribute('fill-opacity', ativo ? .4 : .16); pg.setAttribute('stroke', s.cor);
      if (ativo) pg.classList.add('sel');
      svg.append(pg);
      const [cx, cy] = centroide(a.pontos); const n = eqs.filter((e) => e.setor === s.id && e.pavimento === pav && e.x !== null).length;
      const l = document.createElement('div'); l.className = 'rotulo'; l.style.left = cx + '%'; l.style.top = cy + '%'; l.textContent = `${s.nome} · ${n}`; layer.append(l);
    });
    doAndar().forEach((e) => {
      const d = document.createElement('div');
      d.className = `pin tp-${e.tipo} s-${e.status}` + (e.tipo === 'impressora' ? ' sq' : '') + (e.id === sel ? ' sel' : '') + (esconde(e) ? ' dim' : '');
      d.dataset.id = e.id; d.style.left = e.x + '%'; d.style.top = e.y + '%'; d.style.pointerEvents = 'auto';
      d.title = `${e.asset_id} · ${e.responsavel || e.obs || ''}`; layer.append(d);
    });
    dica();
  }

  function dica() {
    const e = sel && porId.get(sel);
    $('#dica').innerHTML = !e ? 'Clique num <b>setor</b> para filtrar, ou escolha um equipamento à direita. Para posicionar: selecione o equipamento e <b>clique no ponto exato</b> da planta. Arraste os pinos para ajustar; use o zoom para precisão.'
      : e.x === null || e.pavimento !== pav ? `<b>${esc(e.asset_id)}</b> selecionado — <b>clique no mapa</b> para colocá-lo em <b>${esc(D.pavimentos.find((p) => p.id === pav).nome)}</b>. <a href="#" id="desel">cancelar</a>`
        : `<b>${esc(e.asset_id)}</b> posicionado — arraste o pino ou use as <b>setas</b> (Shift = passo maior) para ajuste fino. <a href="#" id="desel">soltar</a>`;
    const d = $('#desel'); if (d) d.onclick = (ev) => { ev.preventDefault(); selecionar(null); };
  }

  function selecionar(id) {
    sel = id === sel ? null : id;
    const e = sel && porId.get(sel); if (e && e.pavimento && e.x !== null && e.pavimento !== pav) { pav = e.pavimento; lsSet('pav', pav); construir(); return; }
    overlay(); lateral();
  }

  function lateral() {
    const l = $('#lado'), e = sel && porId.get(sel), set = setorSel && setorPor.get(setorSel);
    l.innerHTML = '';
    if (e) {
      const s = setorPor.get(e.setor), c = document.createElement('div'); c.className = 'card';
      c.innerHTML = `<h3>${rotuloEq(e)}</h3><p class="mut" style="margin:0 0 8px"><span class="pill st-${e.status}">${esc(D.status[e.status])}</span> · Setor: ${s ? `<span class="sw" style="background:${s.cor}"></span>${esc(s.nome)}` : '—'}${e.x !== null ? `<br>Posição: ${e.x.toFixed(2)}% , ${e.y.toFixed(2)}%` : '<br>Sem posição na planta'}</p>
        <div class="tools" style="margin:0"><a class="b" href="${urlId(D.urls.editar, e.id)}">Editar</a>${e.x !== null ? '<button class="b danger" id="rem">Remover do mapa</button>' : ''}</div>`;
      l.append(c); const r = $('#rem', c); if (r) r.onclick = () => salvar(e, null, null, null);
    }
    const f = document.createElement('div'); f.className = 'card';
    f.innerHTML = `<h3>Equipamentos</h3><div class="tools" style="margin-bottom:8px"><input type="search" id="busca" placeholder="Buscar…" value="${esc(q)}" style="flex:1;min-width:0">
      <select id="fset"><option value="">Todos os setores</option>${D.setores.map((s) => `<option value="${s.id}" ${setorSel === s.id ? 'selected' : ''}>${esc(s.nome)}</option>`).join('')}</select></div><div id="listas"></div>`;
    l.append(f);
    $('#busca').oninput = (ev) => { q = ev.target.value; listas(); };
    $('#fset').onchange = (ev) => { setorSel = ev.target.value ? +ev.target.value : null; overlay(); listas(); };
    listas();
  }

  function listas() {
    const box = $('#listas'); if (!box) return;
    const nq = q.trim().toLowerCase(), casa = (e) => (!setorSel || e.setor === setorSel) && (!nq || (e.asset_id + ' ' + e.responsavel + ' ' + e.obs).toLowerCase().includes(nq));
    const item = (e) => `<div class="item ${e.id === sel ? 'sel' : ''}" data-id="${e.id}"><span>${rotuloEq(e)}</span><span class="pill st-${e.status}">${esc(D.status[e.status])}</span></div>`;
    const aqui = eqs.filter((e) => e.pavimento === pav && e.x !== null && casa(e));
    const sem = eqs.filter((e) => (e.x === null || e.pavimento === null) && casa(e));
    box.innerHTML = `<h3 style="margin-top:4px">Neste andar (${aqui.length})</h3>${aqui.slice(0, 80).map(item).join('') || '<span class="mut">Nenhum.</span>'}${aqui.length > 80 ? `<p class="mut">+${aqui.length - 80} — use a busca.</p>` : ''}
      <h3 style="margin-top:14px">Sem posição na planta (${sem.length})</h3>${sem.slice(0, 80).map(item).join('') || '<span class="mut">Tudo posicionado 🎉</span>'}${sem.length > 80 ? `<p class="mut">+${sem.length - 80} — use busca ou filtro de setor.</p>` : ''}`;
    box.querySelectorAll('.item').forEach((el) => el.onclick = () => selecionar(+el.dataset.id));
  }

  // ---- gravação ----
  async function salvar(e, pavimento, x, y) {
    const antes = { pavimento: e.pavimento, x: e.x, y: e.y, setor: e.setor };
    if (x === null) { e.x = e.y = null; } else { e.pavimento = pavimento; e.x = +x.toFixed(3); e.y = +y.toFixed(3); }
    overlay(); lateral();
    try {
      const r = await api(urlId(D.urls.posicao, e.id), { pavimento, x: e.x, y: e.y });
      if (r.setor !== e.setor) toast(`${e.asset_id} → ${r.setor ? setorPor.get(r.setor).nome : 'sem setor'}`);
      e.setor = r.setor; overlay(); lateral(); barra();
    } catch (err) { Object.assign(e, antes); overlay(); lateral(); toast('Não salvou: ' + err.message); }
  }

  // ---- interação no mapa ----
  let arrasto = null;
  function apertou(ev) {
    const pin = ev.target.closest('.pin'); if (!pin) return;
    const e = porId.get(+pin.dataset.id); arrasto = { e, moveu: false, ini: [ev.clientX, ev.clientY], pavAntes: e.pavimento };
    if (sel !== e.id) { sel = e.id; dica(); } mapa.stage.setPointerCapture(ev.pointerId); ev.preventDefault();
  }
  function moveu(ev) {
    if (!arrasto) return;
    if (!arrasto.moveu && Math.hypot(ev.clientX - arrasto.ini[0], ev.clientY - arrasto.ini[1]) < 3) return;
    arrasto.moveu = true; const [x, y] = coordsNoMapa(ev, mapa.stage), el = mapa.layer.querySelector(`.pin[data-id="${arrasto.e.id}"]`);
    el.style.left = x + '%'; el.style.top = y + '%'; arrasto.pos = [x, y];
  }
  function soltou(ev) {
    if (!arrasto) return; const a = arrasto; arrasto = null; mapa.stage.suppressClick = true; setTimeout(() => { mapa.stage.suppressClick = false; });
    if (a.moveu) salvar(a.e, pav, ...a.pos); else { overlay(); lateral(); }
  }
  function clicou(ev) {
    if (mapa.stage.suppressClick || ev.target.closest('.pin')) return;
    const e = sel && porId.get(sel);
    if (e && (e.x === null || e.pavimento !== pav)) { const [x, y] = coordsNoMapa(ev, mapa.stage); salvar(e, pav, x, y); return; }
    const pg = ev.target.closest('polygon');
    if (pg) { const id = +pg.dataset.setor; setorSel = setorSel === id ? null : id; sel = null; lateral(); overlay(); return; }
    if (sel) selecionar(null); else if (setorSel) { setorSel = null; lateral(); overlay(); }
  }
  document.addEventListener('keydown', (ev) => {
    const e = sel && porId.get(sel);
    if (!e || e.x === null || e.pavimento !== pav || /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
    const passo = ev.shiftKey ? 0.5 : 0.05, d = { ArrowLeft: [-passo, 0], ArrowRight: [passo, 0], ArrowUp: [0, -passo], ArrowDown: [0, passo] }[ev.key];
    if (ev.key === 'Escape') return selecionar(null);
    if (!d) return; ev.preventDefault();
    e.x = clamp(e.x + d[0]); e.y = clamp(e.y + d[1]); overlay();
    clearTimeout(salvar.h); salvar.h = setTimeout(() => salvar(e, pav, e.x, e.y), 350);
  });

  construir();
})();
