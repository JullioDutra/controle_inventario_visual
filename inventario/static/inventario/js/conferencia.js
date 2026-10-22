/* Conferência física: leitor de código de barras (campo de texto + Enter) e marcação em massa. */
(() => {
  const corpo = $('#corpo'), scan = $('#scan'), fl = $('#flash');
  const total = () => corpo.querySelectorAll('tr[data-id]').length;
  const atualizaProgresso = () => {
    const ok = corpo.querySelectorAll('tr.ok-row').length, t = total();
    $('#nconf').textContent = ok; $('#barra').style.width = (t ? ok / t * 100 : 0) + '%';
  };
  const marca = (r) => {
    const tr = corpo.querySelector(`tr[data-id="${r.id}"]`); if (!tr) return;
    tr.classList.add('ok-row'); $('.ult', tr).textContent = new Date().toLocaleDateString('pt-BR'); $('.sel', tr).checked = false;
  };
  const aviso = (txt, erro) => { fl.innerHTML = `<div class="flash ${erro ? 'erro' : ''}">${esc(txt)}</div>`; };
  const bip = (ok) => { try { const a = new (window.AudioContext || window.webkitAudioContext)(), o = a.createOscillator(); o.frequency.value = ok ? 880 : 220; o.connect(a.destination); o.start(); o.stop(a.currentTime + 0.12); } catch (e) { /* sem áudio */ } };

  scan.addEventListener('keydown', async (ev) => {
    if (ev.key !== 'Enter') return; ev.preventDefault();
    const cod = scan.value.trim(); if (!cod) return; scan.value = '';
    try {
      const r = await api(window.URL_CONFERIR, { codigo: cod });
      r.conferidos.forEach(marca); atualizaProgresso(); bip(true);
      const e = r.conferidos[0];
      aviso(`✔ ${e.asset_id} · ${e.tipo}${e.responsavel ? ' · ' + e.responsavel : ''}${e.setor ? ' · ' + e.setor : ''}${e.ausente ? ' — atenção: ausente no último TopDesk' : ''}${corpo.querySelector(`tr[data-id="${e.id}"]`) ? '' : ' (fora deste filtro)'}`, false);
    } catch (er) { bip(false); aviso(er.message, true); }
  });
  $('#todos').onchange = (ev) => corpo.querySelectorAll('.sel').forEach((c) => { c.checked = ev.target.checked; });
  $('#marcar').onclick = async () => {
    const ids = [...corpo.querySelectorAll('tr[data-id]')].filter((tr) => $('.sel', tr).checked).map((tr) => +tr.dataset.id);
    if (!ids.length) return toast('Selecione equipamentos na lista.');
    try { const r = await api(window.URL_CONFERIR, { ids }); r.conferidos.forEach(marca); atualizaProgresso(); toast(`${r.conferidos.length} conferido(s)`); } catch (er) { toast(er.message); }
  };
})();
