/* Setores na planta: crie setores, desenhe suas áreas (retângulo/polígono), mova e remodele. */
(() => {
  const D = JSON.parse($('#dados').textContent), U = D.urls;
  let pav = lsGet('pav', 0); if (!D.pavimentos.some((p) => p.id === pav)) pav = D.pavimentos[0].id;
  let zoom = lsGet('zoom', 1), setorId = null, areaId = null, modo = 'sel', rascunho = [], ctx = lsGet('ctx', true), novo = false, mapa = null;
  const setor = (id) => D.setores.find((s) => s.id === id), area = (id) => D.areas.find((a) => a.id === id);
  const areasDe = (sid) => D.areas.filter((a) => a.setor === sid);
  const pavNome = (id) => (D.pavimentos.find((p) => p.id === id) || {}).nome;

  // ---------- barra / lateral ----------
  function barra() {
    const b = $('#barra'); b.innerHTML = '';
    D.pavimentos.forEach((p) => { const x = document.createElement('button'); x.className = 'b' + (p.id === pav ? ' p' : ''); x.textContent = `${p.nome} (${D.areas.filter((a) => a.pavimento === p.id).length} áreas)`; x.onclick = () => { pav = p.id; lsSet('pav', pav); areaId = null; cancelar(); construir(); }; b.append(x); });
    const l = document.createElement('label'); l.className = 'chk'; l.innerHTML = `<input type="checkbox" ${ctx ? 'checked' : ''}> mostrar equipamentos`;
    l.firstChild.onchange = (e) => { ctx = e.target.checked; lsSet('ctx', ctx); overlay(); }; b.append(l);
    b.append(controlesZoom(zoom, (z) => { zoom = z; lsSet('zoom', z); construir(); }));
  }

  function lateral() {
    const l = $('#lado'), s = setor(setorId); l.innerHTML = '';
    const c1 = document.createElement('div'); c1.className = 'card';
    c1.innerHTML = `<h3>Setores (${D.setores.length}) <button class="b" id="novo" style="float:right;padding:2px 8px">+ Novo setor</button></h3>
      <p class="mut" style="margin:0 0 8px">Para renomear, mesclar ou excluir vários setores use <a href="/setores/gerenciar/">Gerenciar setores</a>.</p>
      ${novo ? `<form id="fnovo" class="tools"><input name="nome" placeholder="Nome do setor" required style="flex:1;min-width:0" autofocus><input type="color" name="cor" value="${corAleatoria()}" style="padding:0;width:38px"><button class="b p">Criar</button></form>` : ''}
      <div id="lista">${D.setores.map((x) => { const n = areasDe(x.id).length; return `<div class="item ${x.id === setorId ? 'sel' : ''}" data-id="${x.id}"><span><span class="sw" style="background:${x.cor}"></span>${esc(x.nome)}</span><span class="mut">${n ? n + ' área' + (n > 1 ? 's' : '') : 'sem área'}</span></div>`; }).join('') || '<span class="mut">Nenhum setor. Crie o primeiro.</span>'}</div>`;
    l.append(c1);
    $('#novo', c1).onclick = () => { novo = !novo; lateral(); };
    const fn = $('#fnovo', c1); if (fn) fn.onsubmit = async (e) => { e.preventDefault(); const f = new FormData(fn); try { const s2 = await api(U.setor_criar, { nome: f.get('nome'), cor: f.get('cor') }); D.setores.push(s2); D.setores.sort((a, b) => a.nome.localeCompare(b.nome, 'pt')); setorId = s2.id; areaId = null; novo = false; toast('Setor criado — agora desenhe a área dele na planta.'); modo = 'rect'; lateral(); overlay(); dica(); } catch (er) { toast(er.message); } };
    c1.querySelectorAll('.item').forEach((el) => el.onclick = () => { setorId = +el.dataset.id; const a = areasDe(setorId); areaId = (a.find((x) => x.pavimento === pav) || a[0] || {}).id || null; if (areaId && area(areaId).pavimento !== pav) { pav = area(areaId).pavimento; lsSet('pav', pav); } cancelar(); construir(); });
    if (s) {
      const c2 = document.createElement('div'); c2.className = 'card';
      c2.innerHTML = `<h3>${esc(s.nome)}</h3>
        <form id="fset" class="tools"><input name="nome" value="${esc(s.nome)}" style="flex:1;min-width:0"><input type="color" name="cor" value="${s.cor}" style="padding:0;width:38px"><button class="b">Salvar</button></form>
        <div class="tools"><button class="b ${modo === 'rect' ? 'on' : ''}" data-m="rect">▭ Desenhar retângulo</button><button class="b ${modo === 'poly' ? 'on' : ''}" data-m="poly">⬠ Desenhar polígono</button></div>
        <div id="areas">${areasDe(s.id).map((a, i) => `<div class="item ${a.id === areaId ? 'sel' : ''}" data-a="${a.id}"><span>Área ${i + 1} · ${esc(pavNome(a.pavimento))}</span><span class="mut">${a.pontos.length} pontos</span></div>`).join('') || '<span class="mut">Este setor ainda não tem área desenhada.</span>'}</div>
        <div class="tools" style="margin-top:10px"><button class="b danger" id="delarea" ${areaId ? '' : 'disabled'}>Excluir área selecionada</button><button class="b danger" id="delsetor">Excluir setor</button></div>`;
      l.append(c2);
      $('#fset', c2).onsubmit = async (e) => { e.preventDefault(); const f = new FormData(e.target); try { Object.assign(s, await api(urlId(U.setor, s.id), { nome: f.get('nome'), cor: f.get('cor') })); D.setores.sort((a, b) => a.nome.localeCompare(b.nome, 'pt')); toast('Setor salvo'); lateral(); overlay(); } catch (er) { toast(er.message); } };
      c2.querySelectorAll('[data-m]').forEach((b) => b.onclick = () => { modo = modo === b.dataset.m ? 'sel' : b.dataset.m; rascunho = []; lateral(); overlay(); dica(); });
      c2.querySelectorAll('[data-a]').forEach((el) => el.onclick = () => { areaId = +el.dataset.a; const a = area(areaId); if (a.pavimento !== pav) { pav = a.pavimento; lsSet('pav', pav); construir(); } else { lateral(); overlay(); } });
      $('#delarea', c2).onclick = excluirArea; $('#delsetor', c2).onclick = excluirSetor;
    }
    const c3 = document.createElement('div'); c3.className = 'card';
    c3.innerHTML = `<h3>Equipamentos × setores</h3><p class="mut" style="margin-top:0">Ao posicionar um equipamento dentro de uma área, ele recebe o setor dela. Depois de mover/redesenhar áreas, recalcule:</p><button class="b" id="reat">Reatribuir setor pela posição</button>`;
    l.append(c3);
    $('#reat', c3).onclick = async () => { try { const r = await api(U.reatribuir); toast(`${r.alterados} equipamento(s) mudaram de setor`); } catch (er) { toast(er.message); } };
  }
  const corAleatoria = () => ['#e63329', '#1f6feb', '#8957e5', '#1a7f37', '#bf8700', '#d6457a', '#2a9d8f', '#fb8500'][D.setores.length % 8];

  function dica() {
    const s = setor(setorId);
    const t = !D.setores.length ? 'Comece criando um setor (botão <b>+ Novo setor</b>).'
      : !s ? 'Selecione um setor à esquerda para desenhar ou editar a área dele, ou clique numa área do mapa.'
        : modo === 'rect' ? `Desenhando <b>retângulo</b> de <b>${esc(s.nome)}</b>: arraste sobre a planta. <a href="#" id="x">cancelar</a>`
          : modo === 'poly' ? `Desenhando <b>polígono</b> de <b>${esc(s.nome)}</b>: clique nos cantos (${rascunho.length} pontos). <b>Duplo clique</b>, <b>Enter</b> ou clique no 1º ponto para fechar; <b>Backspace</b> desfaz; <b>Esc</b> cancela. <a href="#" id="x">cancelar</a>`
            : areaId && area(areaId) ? `Área de <b>${esc(s.nome)}</b> selecionada: <b>arraste</b> para mover, arraste os <b>pontos</b> para remodelar, clique nos pontos tracejados para <b>criar um vértice</b>, duplo clique num ponto o remove. Setas movem (Shift = mais). <b>Delete</b> exclui.`
              : `<b>${esc(s.nome)}</b>: escolha “Desenhar retângulo/polígono” para marcar a área dele na planta atual, ou clique numa área existente para editá-la.`;
    $('#dica').innerHTML = t; const x = $('#x'); if (x) x.onclick = (e) => { e.preventDefault(); cancelar(); };
  }
  function cancelar() { modo = 'sel'; rascunho = []; if (mapa) { lateral(); overlay(); } }

  // ---------- desenho ----------
  function construir() {
    const p = D.pavimentos.find((x) => x.id === pav);
    mapa = montarMapa($('#mapa'), p.imagem, zoom);
    const st = mapa.stage; st.addEventListener('pointerdown', apertou); st.addEventListener('pointermove', moveu); st.addEventListener('pointerup', soltou);
    st.addEventListener('dblclick', duploClique);
    barra(); lateral(); overlay(); dica();
  }
  function overlay() {
    const { svg, layer } = mapa; svg.innerHTML = ''; layer.innerHTML = '';
    if (ctx) D.equipamentos.filter((e) => e.pavimento === pav).forEach((e) => { const d = document.createElement('div'); d.className = `pin ctx tp-${e.tipo}`; d.style.left = e.x + '%'; d.style.top = e.y + '%'; layer.append(d); });
    D.areas.filter((a) => a.pavimento === pav).forEach((a) => {
      const s = setor(a.setor); if (!s) return; const ativo = a.id === areaId, doSel = a.setor === setorId;
      const pg = document.createElementNS(NS, 'polygon'); pg.setAttribute('points', pts2str(a.pontos)); pg.dataset.area = a.id;
      pg.setAttribute('fill', s.cor); pg.setAttribute('fill-opacity', ativo ? .45 : doSel ? .3 : .15); pg.setAttribute('stroke', s.cor); if (ativo) pg.classList.add('sel');
      svg.append(pg);
      const [cx, cy] = centroide(a.pontos), r = document.createElement('div'); r.className = 'rotulo'; r.style.left = cx + '%'; r.style.top = cy + '%'; r.textContent = s.nome; layer.append(r);
      if (ativo && modo === 'sel') alcas(a);
    });
    if (rascunho.length) {
      const pl = document.createElementNS(NS, 'polyline'); pl.setAttribute('points', pts2str(rascunho.concat(cursor ? [cursor] : []))); pl.setAttribute('fill', 'none'); pl.setAttribute('stroke', '#000'); pl.setAttribute('stroke-width', 2); pl.setAttribute('vector-effect', 'non-scaling-stroke'); pl.setAttribute('stroke-dasharray', '5 3'); svg.append(pl);
      rascunho.forEach((q, i) => { const v = document.createElement('div'); v.className = 'vtx'; v.style.left = q[0] + '%'; v.style.top = q[1] + '%'; if (i === 0) v.style.background = '#e63329'; layer.append(v); });
    }
    if (arr && arr.tipo === 'rect' && arr.fim) { const [x1, y1] = arr.ini, [x2, y2] = arr.fim; const r = document.createElementNS(NS, 'rect'); r.setAttribute('x', Math.min(x1, x2)); r.setAttribute('y', Math.min(y1, y2)); r.setAttribute('width', Math.abs(x2 - x1)); r.setAttribute('height', Math.abs(y2 - y1)); r.setAttribute('fill', '#0002'); r.setAttribute('stroke', '#000'); r.setAttribute('stroke-dasharray', '5 3'); r.setAttribute('vector-effect', 'non-scaling-stroke'); svg.append(r); }
  }
  function alcas(a) {
    const p = a.pontos;
    p.forEach((q, i) => { const m = p[(i + 1) % p.length], mid = document.createElement('div'); mid.className = 'vtx mid'; mid.dataset.mid = i; mid.style.left = (q[0] + m[0]) / 2 + '%'; mid.style.top = (q[1] + m[1]) / 2 + '%'; mid.style.pointerEvents = 'auto'; mapa.layer.append(mid); });
    p.forEach((q, i) => { const v = document.createElement('div'); v.className = 'vtx'; v.dataset.v = i; v.style.left = q[0] + '%'; v.style.top = q[1] + '%'; v.style.pointerEvents = 'auto'; mapa.layer.append(v); });
  }

  let arr = null, cursor = null, ultimo = null;
  const pxPerto = (a, b) => { const r = mapa.stage.getBoundingClientRect(); return Math.hypot((a[0] - b[0]) * r.width / 100, (a[1] - b[1]) * r.height / 100) < 12; };
  function apertou(ev) {
    const pos = coordsNoMapa(ev, mapa.stage), a = areaId && area(areaId);
    if (modo === 'rect') { if (!setorId) return toast('Selecione um setor'); arr = { tipo: 'rect', ini: pos, fim: null }; mapa.stage.setPointerCapture(ev.pointerId); return; }
    if (modo === 'poly') { arr = { tipo: 'poly-click', ini: pos }; return; }
    const v = ev.target.closest('[data-v]'), mid = ev.target.closest('[data-mid]');
    if (a && v) { arr = { tipo: 'vertice', a, i: +v.dataset.v, antes: JSON.stringify(a.pontos) }; mapa.stage.setPointerCapture(ev.pointerId); ev.preventDefault(); return; }
    if (a && mid) { const i = +mid.dataset.mid + 1; const antes = JSON.stringify(a.pontos); a.pontos.splice(i, 0, pos); arr = { tipo: 'vertice', a, i, antes, novo: true }; mapa.stage.setPointerCapture(ev.pointerId); overlay(); ev.preventDefault(); return; }
    const pg = ev.target.closest('polygon[data-area]');
    if (pg) { const alvo = area(+pg.dataset.area); areaId = alvo.id; setorId = alvo.setor; arr = { tipo: 'mover', a: alvo, ini: pos, orig: JSON.parse(JSON.stringify(alvo.pontos)), moveu: false }; mapa.stage.setPointerCapture(ev.pointerId); lateral(); overlay(); dica(); return; }
    if (areaId) { areaId = null; lateral(); overlay(); dica(); }
  }
  function moveu(ev) {
    const pos = coordsNoMapa(ev, mapa.stage);
    if (modo === 'poly') { cursor = pos; if (rascunho.length) overlay(); }
    if (!arr) return;
    if (arr.tipo === 'rect') { arr.fim = pos; overlay(); }
    else if (arr.tipo === 'vertice') { arr.a.pontos[arr.i] = [+pos[0].toFixed(3), +pos[1].toFixed(3)]; arr.moveu = true; overlay(); }
    else if (arr.tipo === 'mover') {
      let dx = pos[0] - arr.ini[0], dy = pos[1] - arr.ini[1]; if (Math.hypot(dx, dy) < 0.05 && !arr.moveu) return;
      const xs = arr.orig.map((q) => q[0]), ys = arr.orig.map((q) => q[1]);
      dx = clamp(dx, -Math.min(...xs), 100 - Math.max(...xs)); dy = clamp(dy, -Math.min(...ys), 100 - Math.max(...ys));
      arr.a.pontos = arr.orig.map((q) => [+(q[0] + dx).toFixed(3), +(q[1] + dy).toFixed(3)]); arr.moveu = true; overlay();
    }
  }
  async function soltou(ev) {
    if (!arr) return; const a = arr; arr = null;
    if (a.tipo === 'rect') {
      const [x1, y1] = a.ini, [x2, y2] = a.fim || a.ini;
      if (Math.abs(x2 - x1) < 0.3 || Math.abs(y2 - y1) < 0.3) { overlay(); return; }
      await criarArea([[x1, y1], [x2, y1], [x2, y2], [x1, y2]].map((q) => q.map((n) => +n.toFixed(3))));
    } else if (a.tipo === 'poly-click') {
      const pos = a.ini, agora = Date.now();
      // fecha com clique no 1º ponto ou duplo clique (detectado à mão: a tela é redesenhada entre os cliques e o navegador não dispara dblclick)
      if (rascunho.length >= 3 && (pxPerto(pos, rascunho[0]) || (ultimo && agora - ultimo.t < 450 && pxPerto(pos, ultimo.pos)))) { ultimo = null; await fechar(); return; }
      ultimo = { t: agora, pos };
      rascunho.push([+pos[0].toFixed(3), +pos[1].toFixed(3)]); dica(); overlay();
    } else if (a.tipo === 'vertice') {
      const agora = Date.now();
      if (!a.moveu && !a.novo && ultimo && ultimo.i === a.i && ultimo.a === a.a.id && agora - ultimo.t < 450) {  // duplo clique no vértice: remove
        ultimo = null;
        if (a.a.pontos.length > 3) { const antes = JSON.parse(a.antes); a.a.pontos.splice(a.i, 1); overlay(); await salvarArea(a.a, antes); } else toast('Uma área precisa de 3 pontos.');
        return;
      }
      ultimo = { t: agora, i: a.i, a: a.a.id };
      if (a.moveu || a.novo) await salvarArea(a.a, JSON.parse(a.antes)); else overlay();
    } else if (a.tipo === 'mover' && a.moveu) {
      await salvarArea(a.a, a.orig);
    }
  }
  function duploClique(ev) {
    const v = ev.target.closest('[data-v]');
    if (modo === 'poly') { rascunho.pop(); if (rascunho.length >= 3) fechar(); return; }
    if (v && areaId) { const a = area(areaId); if (a.pontos.length > 3) { const antes = JSON.parse(JSON.stringify(a.pontos)); a.pontos.splice(+v.dataset.v, 1); overlay(); salvarArea(a, antes); } else toast('Uma área precisa de 3 pontos.'); }
  }
  async function fechar() { const p = rascunho.slice(); rascunho = []; cursor = null; await criarArea(p); }
  async function criarArea(pontos) {
    if (!setorId) return toast('Selecione um setor');
    try { const a = await api(U.area_criar, { setor: setorId, pavimento: pav, pontos }); D.areas.push(a); areaId = a.id; modo = 'sel'; toast('Área criada. Arraste para mover ou ajuste os pontos.'); }
    catch (er) { toast(er.message); }
    construir();
  }
  async function salvarArea(a, antes) {
    try { const r = await api(urlId(U.area, a.id), { pontos: a.pontos }); a.pontos = r.pontos; }
    catch (er) { a.pontos = antes; toast('Não salvou: ' + er.message); }
    overlay(); lateral();
  }
  async function excluirArea() {
    const a = areaId && area(areaId); if (!a || !confirm('Excluir esta área?')) return;
    try { await api(urlId(U.area_excluir, a.id)); D.areas = D.areas.filter((x) => x.id !== a.id); areaId = null; construir(); } catch (er) { toast(er.message); }
  }
  async function excluirSetor() {
    const s = setor(setorId); if (!s || !confirm(`Excluir o setor “${s.nome}” e suas áreas? Os equipamentos ficam sem setor.`)) return;
    try { await api(urlId(U.setor_excluir, s.id)); D.setores = D.setores.filter((x) => x.id !== s.id); D.areas = D.areas.filter((x) => x.setor !== s.id); setorId = areaId = null; construir(); } catch (er) { toast(er.message); }
  }
  document.addEventListener('keydown', (ev) => {
    if (/INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName)) return;
    if (ev.key === 'Escape') cancelar();
    else if (modo === 'poly' && ev.key === 'Enter' && rascunho.length >= 3) fechar();
    else if (modo === 'poly' && ev.key === 'Backspace') { ev.preventDefault(); rascunho.pop(); dica(); overlay(); }
    else if (modo === 'sel' && areaId && ev.key === 'Delete') excluirArea();
    else if (modo === 'sel' && areaId && ev.key.startsWith('Arrow')) {
      ev.preventDefault(); const a = area(areaId), p = ev.shiftKey ? 0.5 : 0.05, [dx, dy] = { ArrowLeft: [-p, 0], ArrowRight: [p, 0], ArrowUp: [0, -p], ArrowDown: [0, p] }[ev.key];
      if (!a.__antes) a.__antes = JSON.parse(JSON.stringify(a.pontos));
      const xs = a.pontos.map((q) => q[0]), ys = a.pontos.map((q) => q[1]), mx = clamp(dx, -Math.min(...xs), 100 - Math.max(...xs)), my = clamp(dy, -Math.min(...ys), 100 - Math.max(...ys));
      a.pontos = a.pontos.map((q) => [+(q[0] + mx).toFixed(3), +(q[1] + my).toFixed(3)]); overlay();
      clearTimeout(a.__h); a.__h = setTimeout(() => { const antes = a.__antes; delete a.__antes; salvarArea(a, antes); }, 400);
    }
  });
  construir();
})();
