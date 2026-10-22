/* Utilidades compartilhadas pelas telas Planta e Setores na planta. */
const NS = 'http://www.w3.org/2000/svg';
const $ = (s, r = document) => r.querySelector(s);
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const lsGet = (k, d) => { try { const v = localStorage.getItem('inv_' + k); return v === null ? d : JSON.parse(v); } catch (e) { return d; } };
const lsSet = (k, v) => { try { localStorage.setItem('inv_' + k, JSON.stringify(v)); } catch (e) { /* sem storage: tudo bem */ } };

function toast(msg) {
  const t = $('#toast'); t.textContent = msg; t.classList.add('on');
  clearTimeout(toast.h); toast.h = setTimeout(() => t.classList.remove('on'), 2800);
}
async function api(url, dados) {
  const r = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRFToken': $('meta[name=csrf-token]').content }, body: JSON.stringify(dados || {}) });
  let j = {}; try { j = await r.json(); } catch (e) { /* resposta não-JSON */ }
  if (!r.ok) throw new Error(j.erro || 'Erro ' + r.status);
  return j;
}
// Os templates de URL do Django vêm com id 0 ("/api/areas/0/"); troca pelo id real.
const urlId = (tpl, id) => tpl.replace('/0/', `/${id}/`);

function pontoEmPoligono(x, y, p) {
  let d = false;
  for (let i = 0, j = p.length - 1; i < p.length; j = i++) {
    const [xi, yi] = p[i], [xj, yj] = p[j];
    if ((yi > y) !== (yj > y) && x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-12) + xi) d = !d;
  }
  return d;
}
function centroide(p) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0; i < p.length; i++) {
    const [x1, y1] = p[i], [x2, y2] = p[(i + 1) % p.length], c = x1 * y2 - x2 * y1;
    a += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c;
  }
  if (Math.abs(a) < 1e-9) return [p.reduce((s, q) => s + q[0], 0) / p.length, p.reduce((s, q) => s + q[1], 0) / p.length];
  return [cx / (3 * a), cy / (3 * a)];
}
const pts2str = (p) => p.map((q) => q.join(',')).join(' ');
const clamp = (v, a = 0, b = 100) => Math.min(b, Math.max(a, v));

/** Monta a planta (imagem + SVG das áreas + camada HTML de pinos/rótulos). Devolve {stage, svg, layer}. */
function montarMapa(host, src, zoom) {
  host.innerHTML = '';
  const stage = document.createElement('div'); stage.className = 'stage'; stage.style.width = (zoom * 100) + '%';
  const img = new Image(); img.src = src; img.alt = 'Planta'; img.draggable = false;
  const svg = document.createElementNS(NS, 'svg'); svg.setAttribute('viewBox', '0 0 100 100'); svg.setAttribute('preserveAspectRatio', 'none');
  const layer = document.createElement('div'); layer.style.cssText = 'position:absolute;inset:0;pointer-events:none';
  stage.append(img, svg, layer); host.append(stage);
  return { stage, svg, layer };
}
function coordsNoMapa(e, stage) {
  const r = stage.getBoundingClientRect();
  return [clamp((e.clientX - r.left) / r.width * 100), clamp((e.clientY - r.top) / r.height * 100)];
}
/** Botões de zoom; `aoMudar(novoZoom)`. */
function controlesZoom(zoom, aoMudar) {
  const w = document.createElement('span'); w.className = 'zoom';
  w.innerHTML = `<button class="b" data-z="-">−</button><span class="mut">${Math.round(zoom * 100)}%</span><button class="b" data-z="+">+</button><button class="b" data-z="0">Ajustar</button>`;
  w.onclick = (e) => { const z = e.target.dataset.z; if (!z) return; aoMudar(z === '0' ? 1 : clamp(zoom * (z === '+' ? 1.4 : 1 / 1.4), 1, 10)); };
  return w;
}
