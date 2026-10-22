import io
from collections import OrderedDict
from datetime import date

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import importador, qualidade
from .forms import EquipamentoForm, ImportacaoForm, LoteForm
from .models import Area, Equipamento, Historico, Importacao, Pavimento, Setor

STATUS_ORDEM = ["operacional", "backup", "instalar", "outro"]


def painel(request):
    ativos = Equipamento.objects.filter(ausente=False)
    total = ativos.count()
    por_ts = {(r["tipo"], r["status"]): r["n"] for r in ativos.values("tipo", "status").annotate(n=Count("id"))}
    tipos = []
    for t, nome in Equipamento.Tipo.choices:
        linha = {s: por_ts.get((t, s), 0) for s in STATUS_ORDEM}
        n = sum(linha.values())
        if n or t != "outro":
            tipos.append({"chave": t, "nome": nome, "total": n, "status": linha})
    status_tot = {s: sum(por_ts.get((t, s), 0) for t, _ in Equipamento.Tipo.choices) for s in STATUS_ORDEM}
    # por setor (barra empilhada por status)
    cont = {}
    for r in ativos.values("setor", "setor__nome", "status").annotate(n=Count("id")):
        c = cont.setdefault(r["setor"], {"id": r["setor"], "nome": r["setor__nome"] or "Sem setor definido", "status": {}, "total": 0})
        c["status"][r["status"]] = r["n"]
        c["total"] += r["n"]
    setores = sorted(cont.values(), key=lambda c: -c["total"])
    maximo = max([c["total"] for c in setores] or [1])
    for c in setores:
        c["largura"] = c["total"] / maximo * 100
        c["segmentos"] = [{"status": s, "n": c["status"][s], "pct": c["status"][s] / c["total"] * 100} for s in STATUS_ORDEM if c["status"].get(s)]
    # por pavimento
    pavs = Pavimento.objects.annotate(
        n=Count("equipamentos", filter=Q(equipamentos__ausente=False, equipamentos__pos_x__isnull=False))).order_by("ordem", "nome")
    sem_pos = ativos.filter(Q(pavimento__isnull=True) | Q(pos_x__isnull=True)).count()
    return render(request, "inventario/painel.html", {
        "total": total, "tipos": tipos, "status_tot": status_tot, "setores": setores, "pavimentos": pavs, "sem_pos": sem_pos,
        "alertas": sum(1 for a in qualidade.verificar() if a["sev"] == "alta"),
        "ausentes": Equipamento.objects.filter(ausente=True).count(),
    })


# ---------------- planta / editor de setores ----------------
def _base_mapa():
    return {
        "pavimentos": [{"id": p.pk, "nome": p.nome, "imagem": p.imagem.url} for p in Pavimento.objects.all()],
        "setores": [{"id": s.pk, "nome": s.nome, "cor": s.cor} for s in Setor.objects.all()],
        "areas": [{"id": a.pk, "setor": a.setor_id, "pavimento": a.pavimento_id, "pontos": a.pontos} for a in Area.objects.all()],
    }


def planta(request):
    dados = _base_mapa()
    dados["equipamentos"] = [{
        "id": e.pk, "asset_id": e.asset_id, "tipo": e.tipo, "status": e.status, "responsavel": e.responsavel,
        "obs": e.obs, "setor": e.setor_id, "pavimento": e.pavimento_id, "x": e.pos_x, "y": e.pos_y,
    } for e in Equipamento.objects.filter(ausente=False)]
    dados["tipos"] = dict(Equipamento.Tipo.choices)
    dados["status"] = dict(Equipamento.Status.choices)
    dados["urls"] = {"posicao": reverse("api_posicao", args=[0]), "editar": reverse("equipamento_editar", args=[0])}
    return render(request, "inventario/planta.html", {"dados": dados, "sem_plantas": not dados["pavimentos"]})


def editor(request):
    dados = _base_mapa()
    dados["equipamentos"] = [{"id": e.pk, "tipo": e.tipo, "pavimento": e.pavimento_id, "x": e.pos_x, "y": e.pos_y}
                             for e in Equipamento.objects.filter(pavimento__isnull=False, pos_x__isnull=False, ausente=False)]
    dados["urls"] = {
        "setor_criar": reverse("api_setor_criar"), "setor": reverse("api_setor_editar", args=[0]),
        "setor_excluir": reverse("api_setor_excluir", args=[0]), "area_criar": reverse("api_area_criar"),
        "area": reverse("api_area_editar", args=[0]), "area_excluir": reverse("api_area_excluir", args=[0]),
        "reatribuir": reverse("api_reatribuir"),
    }
    return render(request, "inventario/editor.html", {"dados": dados, "sem_plantas": not dados["pavimentos"]})


# ---------------- equipamentos ----------------
ORDENACAO = {"asset_id", "tipo", "status", "responsavel", "setor__nome", "pavimento__nome", "serial"}


def _filtrar(request):
    g = request.GET
    qs = Equipamento.objects.select_related("setor", "pavimento")
    if g.get("tipo"):
        qs = qs.filter(tipo=g["tipo"])
    if g.get("status"):
        qs = qs.filter(status=g["status"])
    if g.get("setor") == "none":
        qs = qs.filter(setor__isnull=True)
    elif g.get("setor"):
        qs = qs.filter(setor_id=g["setor"])
    if g.get("pavimento") == "none":
        qs = qs.filter(Q(pavimento__isnull=True) | Q(pos_x__isnull=True))
    elif g.get("pavimento"):
        qs = qs.filter(pavimento_id=g["pavimento"])
    if g.get("ausente") == "1":
        qs = qs.filter(ausente=True)
    q = (g.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(asset_id__icontains=q) | Q(serial__icontains=q) | Q(responsavel__icontains=q) | Q(obs__icontains=q)
                       | Q(setor__nome__icontains=q) | Q(fornecedor__icontains=q))
    o = g.get("o", "asset_id")
    campo = o.lstrip("-")
    return qs.order_by(o if campo in ORDENACAO else "asset_id")


def lista(request):
    qs = _filtrar(request)
    pag = Paginator(qs, 150).get_page(request.GET.get("page"))
    sem_page = request.GET.copy()
    sem_page.pop("page", None)
    return render(request, "inventario/lista.html", {
        "pag": pag, "total": pag.paginator.count, "qs": sem_page.urlencode(), "g": request.GET,
        "tipos": Equipamento.Tipo.choices, "status": Equipamento.Status.choices,
        "setores": Setor.objects.all(), "pavimentos": Pavimento.objects.all(),
    })


def equipamento_form(request, pk=None):
    obj = get_object_or_404(Equipamento, pk=pk) if pk else None
    form = EquipamentoForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        e = form.save()
        Historico.objects.create(asset_id=e.asset_id, evento="alterado" if obj else "novo", origem="manual",
                                 detalhe=("Edição manual: " + ", ".join(form.changed_data)) if obj else "Criado manualmente")
        messages.success(request, f"{e.asset_id} salvo.")
        return redirect("lista")
    return render(request, "inventario/equipamento_form.html", {"form": form, "obj": obj})


@require_POST
def equipamento_excluir(request, pk):
    e = get_object_or_404(Equipamento, pk=pk)
    Historico.objects.create(asset_id=e.asset_id, evento="alterado", detalhe="Excluído manualmente", origem="manual")
    e.delete()
    messages.success(request, f"{e.asset_id} excluído.")
    return redirect("lista")


@require_POST
def lote(request):
    """Atribui setor/andar a todos os equipamentos que casam com os filtros atuais."""
    qs = _filtrar(request)
    f = LoteForm(request.POST)
    if f.is_valid():
        n, upd = qs.count(), {}
        nome = f.cleaned_data["setor"].strip()
        if nome:
            upd["setor"] = Setor.objects.get_or_create(nome=nome)[0]
        if f.cleaned_data["pavimento"]:
            upd.update(pavimento=get_object_or_404(Pavimento, pk=f.cleaned_data["pavimento"]), pos_x=None, pos_y=None)
        if upd:
            qs.update(**upd)
            Historico.objects.create(evento="setor", origem="lote", detalhe=f"Atribuição em lote a {n} equipamento(s): "
                                     + ", ".join(k for k in upd if k not in ("pos_x", "pos_y")))
            messages.success(request, f"{n} equipamento(s) atualizado(s).")
    return redirect(reverse("lista") + ("?" + request.GET.urlencode() if request.GET else ""))


def exportar(request):
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    ws.title = "Inventário"
    ws.append(["Asset ID", "Tipo", "Status", "Responsável", "Setor", "Andar", "X %", "Y %", "Nº série", "Fornecedor", "Obs", "Ausente no TopDesk"])
    for e in _filtrar(request):
        ws.append([e.asset_id, e.get_tipo_display(), e.get_status_display(), e.responsavel, e.setor.nome if e.setor else "",
                   e.pavimento.nome if e.pavimento else "", e.pos_x, e.pos_y, e.serial, e.fornecedor, e.obs, "Sim" if e.ausente else ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = HttpResponse(buf.getvalue(), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    r["Content-Disposition"] = f'attachment; filename="inventario-fsbr-{date.today():%Y-%m-%d}.xlsx"'
    return r


# ---------------- importação ----------------
def importar(request):
    form = ImportacaoForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        arq = form.cleaned_data["arquivo"]
        try:
            linhas, abas = importador.ler_arquivo(arq.name, arq.read())
        except Exception as exc:  # arquivo corrompido, formato inesperado...
            messages.error(request, f"Não consegui ler o arquivo: {exc}")
            return redirect("importar")
        if not linhas:
            messages.error(request, 'Nenhuma linha com coluna "Asset ID" encontrada. Confira o cabeçalho da planilha.')
            return redirect("importar")
        resumo, mudancas = importador.processar(linhas, arq.name, aplicar=False)
        imp = Importacao.objects.create(arquivo=arq.name, linhas=linhas, resumo=resumo, mudancas=mudancas, abas=abas)
        return redirect("importacao", pk=imp.pk)
    return render(request, "inventario/importar.html", {
        "form": form, "recentes": Importacao.objects.exclude(estado="pendente")[:10], "total": Equipamento.objects.count()})


def importacao_detalhe(request, pk):
    imp = get_object_or_404(Importacao, pk=pk)
    return render(request, "inventario/importacao.html", {"imp": imp, "mudancas": imp.mudancas[:500], "cortado": len(imp.mudancas) > 500})


@require_POST
def importacao_aplicar(request, pk):
    imp = get_object_or_404(Importacao, pk=pk, estado="pendente")
    resumo, mudancas = importador.processar(imp.linhas, imp.arquivo, aplicar=True)  # recalcula contra o estado atual
    imp.resumo, imp.mudancas, imp.estado = resumo, mudancas, "aplicada"
    imp.linhas = []  # não guardar a planilha inteira depois de aplicada
    imp.save()
    messages.success(request, f"Importação aplicada: {resumo['novos']} novos, {resumo['alterados']} alterados, {resumo['ausentes']} ausentes.")
    return redirect("painel")


@require_POST
def importacao_cancelar(request, pk):
    imp = get_object_or_404(Importacao, pk=pk, estado="pendente")
    imp.estado, imp.linhas = "cancelada", []
    imp.save()
    return redirect("importar")


def auditoria(request):
    return render(request, "inventario/auditoria.html", {
        "achados": qualidade.verificar(), "historico": Historico.objects.all()[:300]})
