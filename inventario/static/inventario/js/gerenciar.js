/* Gerenciar setores: renomear/cor, mesclar, excluir (com transferência de equipamentos). */
(() => {
  const U = JSON.parse($('#u').textContent), dlg = $('#dlg');
  const linhas = () => [...document.querySelectorAll('#tab tbody tr[data-id]')];
  const outros = (id) => linhas().filter((r) => r.dataset.id !== id).map((r) => `<option value="${r.dataset.id}">${esc(r.dataset.nome)}</option>`).join('');
  const recarrega = (msg) => { if (msg) sessionStorage.setItem('flash', msg); location.reload(); };
  const f = sessionStorage.getItem('flash'); if (f) { sessionStorage.removeItem('flash'); toast(f); }

  $('#novo').onsubmit = async (e) => { e.preventDefault(); const d = new FormData(e.target); try { await api(U.criar, { nome: d.get('nome'), cor: d.get('cor') }); recarrega('Setor criado'); } catch (er) { toast(er.message); } };
  linhas().forEach((tr) => {
    const id = tr.dataset.id, nome = tr.dataset.nome;
    $('.salvar', tr).onclick = async () => { try { await api(urlId(U.editar, id), { nome: $('.nome', tr).value, cor: $('.cor', tr).value }); recarrega('Setor salvo'); } catch (er) { toast(er.message); } };
    $('.mesclar', tr).onclick = () => {
      dlg.innerHTML = `<h3>Mesclar “${esc(nome)}” em outro setor</h3><p class="mut">Todos os equipamentos e as áreas da planta de “${esc(nome)}” passam para o setor escolhido, e “${esc(nome)}” deixa de existir.</p>
        <select id="dest" style="width:100%">${outros(id)}</select><div class="tools" style="margin-top:12px"><button class="b p" id="ok">Mesclar</button><button class="b" id="nao">Cancelar</button></div>`;
      dlg.showModal(); $('#nao').onclick = () => dlg.close();
      $('#ok').onclick = async () => { try { const r = await api(urlId(U.mesclar, id), { destino: +$('#dest').value }); dlg.close(); recarrega(`Mesclado (${r.equipamentos_movidos} equipamento(s) movidos)`); } catch (er) { toast(er.message); } };
    };
    $('.excluir', tr).onclick = () => {
      dlg.innerHTML = `<h3>Excluir “${esc(nome)}”</h3><p class="mut">As áreas dele na planta serão removidas. O que fazer com os equipamentos deste setor?</p>
        <select id="dest" style="width:100%"><option value="">Deixar sem setor</option>${outros(id).replace(/<option/g, '<option data-t="1"')}</select>
        <div class="tools" style="margin-top:12px"><button class="b danger" id="ok">Excluir setor</button><button class="b" id="nao">Cancelar</button></div>`;
      dlg.showModal(); $('#nao').onclick = () => dlg.close();
      $('#ok').onclick = async () => { try { const v = $('#dest').value; const r = await api(urlId(U.excluir, id), { transferir_para: v ? +v : null }); dlg.close(); recarrega(`Setor excluído (${r.equipamentos_afetados} equipamento(s) afetados)`); } catch (er) { toast(er.message); } };
    };
  });
})();
