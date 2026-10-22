/* Notas na linha do tempo do equipamento. */
$('#fnota').onsubmit = async (e) => {
  e.preventDefault();
  const t = $('#nota').value.trim(); if (!t) return;
  try {
    const r = await api(e.target.dataset.url, { texto: t });
    $('#nota').value = '';
    const li = document.createElement('li'); li.className = 'nota';
    li.innerHTML = `<span class="quando">${esc(r.quando)} · Nota · nota</span><br>${esc(r.texto)}`;
    $('#tl').prepend(li); toast('Nota registrada');
  } catch (er) { toast(er.message); }
};
