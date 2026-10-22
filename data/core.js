/* Regras de negócio (sem DOM) — usado pelo app e pelos testes em Node. */
(function (root) {
  const TIPOS = {
    laptop: { nome: 'Laptop', plural: 'Laptops', cor: '#e63329', icone: '💻' },
    tinypc: { nome: 'Tiny PC', plural: 'Tiny PCs', cor: '#1f6feb', icone: '🖥️' },
    impressora: { nome: 'Impressora', plural: 'Impressoras', cor: '#8957e5', icone: '🖨️' },
    outro: { nome: 'Outro', plural: 'Outros', cor: '#6e7781', icone: '📦' },
  };
  const STATUS = {
    operacional: { nome: 'Operacional', cor: '#1a7f37' },
    backup: { nome: 'Backup', cor: '#bf8700' },
    instalar: { nome: 'A instalar', cor: '#0969da' },
    outro: { nome: 'Outro', cor: '#6e7781' },
  };
  // Setores inferidos do campo "Obs" do TopDesk (só quando o setor ainda está vazio).
  const REGRAS_SETOR = [
    [/kiosk\s+produ/i, 'Produção'], [/kiosk\s+lcq|laborat|lcq/i, 'Laboratório (LCQ)'],
    [/kiosk\s+alimentos|smac/i, 'Alimentos / SMAC'], [/manuten/i, 'Manutenção'],
    [/engenharia/i, 'Engenharia'], [/descanso/i, 'Sala de descanso'],
    [/portaria|camera/i, 'Portaria / Segurança'], [/seguran[cç]a do trabalho/i, 'SST'],
  ];
  const norm = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').trim().toLowerCase();
  const str = (v) => (v === null || v === undefined ? '' : String(v).trim());

  function tipoPorNome(nome, id) {
    const n = norm(nome), p = norm(id).slice(0, 3);
    if (/laptop|notebook/.test(n)) return 'laptop';
    if (/tiny|pc/.test(n)) return 'tinypc';
    if (/impress|printer/.test(n)) return 'impressora';
    if (p === 'plp') return 'laptop';
    if (p === 'ppc') return 'tinypc';
    if (p === 'pim' || p === 'pip') return 'impressora';
    return 'outro';
  }
  function statusNorm(s) {
    const n = norm(s);
    if (/operat|operac/.test(n)) return 'operacional';
    if (/backup|reserva/.test(n)) return 'backup';
    if (/install|instalar/.test(n)) return 'instalar';
    return 'outro';
  }
  function setorPorObs(obs) {
    for (const [re, setor] of REGRAS_SETOR) if (re.test(obs || '')) return setor;
    return '';
  }
  const COLS = {
    id: ['asset id', 'id', 'asset', 'ativo', 'patrimonio'], obs: ['obs', 'observacao', 'observacoes'],
    serial: ['serial number', 'serial', 'numero de serie', 'n/s'], status: ['status', 'situacao'],
    supplier: ['supplier', 'fornecedor'], person: ['assignments - persons', 'assignments', 'pessoa', 'usuario', 'responsavel'],
    local: ['setor', 'location', 'localizacao'],
  };
  /** rows: array de objetos {cabeçalho: valor}. Retorna ativos normalizados do TopDesk. */
  function linhasParaAtivos(rows, nomeAba) {
    const out = [];
    for (const r of rows) {
      const m = {};
      for (const k of Object.keys(r)) m[norm(k)] = r[k];
      const pick = (key) => { for (const c of COLS[key]) if (c in m) return str(m[c]); return ''; };
      const id = pick('id').toUpperCase();
      if (!id) continue;
      out.push({ id, tipo: tipoPorNome(nomeAba, id), serial: pick('serial'), status: statusNorm(pick('status')),
        statusOrig: pick('status'), person: pick('person'), obs: pick('obs'), supplier: pick('supplier'), setorTD: pick('local') });
    }
    return out;
  }
  const CAMPOS_TD = ['tipo', 'serial', 'status', 'person', 'obs', 'supplier'];
  const ROT = { tipo: 'Tipo', serial: 'Nº série', status: 'Status', person: 'Responsável', obs: 'Obs', supplier: 'Fornecedor' };
  /** Aplica importação sobre o estado: a chave (Asset ID) atualiza campos do TopDesk; campos locais (setor/andar/zona/posição) são preservados. */
  function aplicarImportacao(ativos, novos, quando, arquivo) {
    const mapa = new Map(ativos.map((a) => [a.id, a]));
    const vistos = new Set(), log = [], res = { novos: 0, alterados: 0, iguais: 0, ausentes: 0, duplicados: 0 };
    for (const n of novos) {
      if (vistos.has(n.id)) { res.duplicados++; continue; }
      vistos.add(n.id);
      const a = mapa.get(n.id);
      if (!a) {
        const setor = n.setorTD || setorPorObs(n.obs);
        const novo = { id: n.id, tipo: n.tipo, serial: n.serial, status: n.status, person: n.person, obs: n.obs, supplier: n.supplier,
          setor, andar: null, zona: '', x: null, y: null, ausente: false, criado: quando };
        ativos.push(novo); mapa.set(n.id, novo); res.novos++;
        log.push({ t: quando, id: n.id, tipo: 'novo', det: `Novo ${TIPOS[n.tipo].nome} (${STATUS[n.status].nome})`, arq: arquivo });
        continue;
      }
      const difs = [];
      for (const c of CAMPOS_TD) if (c === 'tipo' ? a.tipo !== n.tipo && n.tipo !== 'outro' : (a[c] || '') !== (n[c] || '')) {
        difs.push(`${ROT[c]}: ${c === 'status' ? STATUS[a[c]]?.nome : a[c] || '—'} → ${c === 'status' ? STATUS[n[c]].nome : n[c] || '—'}`); a[c] = n[c];
      }
      if (!a.setor) a.setor = n.setorTD || setorPorObs(n.obs);
      if (a.ausente) { difs.push('Voltou a aparecer no TopDesk'); a.ausente = false; }
      if (difs.length) { res.alterados++; log.push({ t: quando, id: n.id, tipo: 'alterado', det: difs.join(' · '), arq: arquivo }); } else res.iguais++;
    }
    // ausentes: só dentro dos tipos presentes no arquivo importado
    const tipos = new Set(novos.map((n) => n.tipo));
    for (const a of ativos) if (!vistos.has(a.id) && tipos.has(a.tipo) && !a.ausente) {
      a.ausente = true; res.ausentes++;
      log.push({ t: quando, id: a.id, tipo: 'ausente', det: 'Não veio na última exportação do TopDesk', arq: arquivo });
    }
    return { res, log };
  }
  /** Checagens de qualidade (inspirado nos "diagnostics" do REA: cada achado traz evidência). */
  function qualidade(ativos) {
    const ach = [], porSerial = new Map();
    for (const a of ativos) {
      if (a.serial) { const k = a.serial.toUpperCase(); (porSerial.get(k) || porSerial.set(k, []).get(k)).push(a); }
      if (a.status === 'operacional' && !a.person && a.tipo === 'laptop') ach.push({ sev: 'alta', id: a.id, msg: 'Laptop operacional sem responsável' });
      if (a.status === 'backup' && a.person) ach.push({ sev: 'media', id: a.id, msg: `Em backup mas atribuído a ${a.person}` });
      if (a.status === 'instalar' && a.person && a.tipo === 'tinypc') ach.push({ sev: 'baixa', id: a.id, msg: 'A instalar com responsável definido' });
      if (!a.serial) ach.push({ sev: 'alta', id: a.id, msg: 'Sem número de série' });
      if (!a.ausente && (a.andar === null || a.andar === undefined)) ach.push({ sev: 'baixa', id: a.id, msg: 'Sem localização na planta' });
      if (a.ausente) ach.push({ sev: 'alta', id: a.id, msg: 'Ausente na última exportação do TopDesk' });
    }
    for (const [s, l] of porSerial) if (l.length > 1) ach.push({ sev: 'alta', id: l.map((x) => x.id).join(', '), msg: `Número de série duplicado (${s})` });
    const pess = new Map();
    for (const a of ativos) if (a.person && a.tipo === 'laptop' && a.status === 'operacional') (pess.get(a.person) || pess.set(a.person, []).get(a.person)).push(a.id);
    for (const [p, l] of pess) if (l.length > 1) ach.push({ sev: 'media', id: l.join(', '), msg: `${p} tem ${l.length} laptops operacionais` });
    return ach;
  }
  // Zonas das plantas (retângulos em px do desenho original 2000 px de largura; origem do recorte 185,165; 1350x385).
  const CROP = { x: 185, y: 165, w: 1350, h: 385 };
  const ANDARES = [
    { nome: 'Térreo', img: 'plans/andar0.png', zonas: { A: [233, 262, 415, 405], C: [415, 255, 810, 365], E: [810, 255, 1075, 365], B: [220, 405, 510, 538], D: [510, 395, 907, 538], F: [907, 392, 1165, 538], G: [1108, 237, 1500, 400], H: [1165, 400, 1500, 540] } },
    { nome: '1º Pavimento', img: 'plans/andar1.png', zonas: { A: [252, 262, 437, 400], B: [240, 400, 530, 515], C: [437, 262, 815, 390], D: [530, 390, 925, 520], E: [815, 262, 1078, 390], F: [925, 390, 1170, 520], G: [1170, 230, 1520, 400], H: [1170, 400, 1520, 540] } },
    { nome: '2º Pavimento', img: 'plans/andar2.png', zonas: { A: [245, 250, 455, 385], B: [228, 388, 518, 508], C: [455, 235, 820, 385], D: [518, 385, 912, 508], E: [820, 235, 1062, 385], F: [912, 380, 1160, 508], G: [1160, 225, 1510, 375], H: [1160, 375, 1510, 515] } },
  ];
  const api = { TIPOS, STATUS, ANDARES, CROP, norm, tipoPorNome, statusNorm, setorPorObs, linhasParaAtivos, aplicarImportacao, qualidade };
  if (typeof module !== 'undefined') module.exports = api; else root.Core = api;
})(typeof window !== 'undefined' ? window : globalThis);
