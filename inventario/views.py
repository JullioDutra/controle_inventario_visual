import io
from collections import OrderedDict
from datetime import date, timedelta
from urllib.parse import urlencode

from django.conf import settings
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.urls import reverse
from django.views.decorators.http import require_POST

from . import importador, qualidade, relatorio
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
        "pendencias": [(k, nome, _pendencia(Equipamento.objects.all(), k).count()) for k, nome in PENDENCIAS.items()],
        "dias": settings.DIAS_CONFERENCIA,
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


PENDENCIAS = {
    "sem_responsavel": "Laptops operacionais sem responsável",
    "sem_setor": "Sem setor",
    "sem_posicao": "Sem posição na planta",
    "a_instalar": "A instalar",
    "conferencia": "Sem conferência recente",
}


def _limite_conferencia():
    return timezone.now() - timedelta(days=settings.DIAS_CONFERENCIA)


def _pendencia(qs, p):
    if p == "sem_responsavel":
        return qs.filter(tipo="laptop", status="operacional", responsavel="", ausente=False)
    if p == "sem_setor":
        return qs.filter(setor__isnull=True, ausente=False)
    if p == "sem_posicao":
        return qs.filter(Q(pavimento__isnull=True) | Q(pos_x__isnull=True), ausente=False)
    if p == "a_instalar":
        return qs.filter(status="instalar", ausente=False)
    if p == "conferencia":
        return qs.filter(Q(ultima_conferencia__isnull=True) | Q(ultima_conferencia__lt=_limite_conferencia()), ausente=False)
    return qs


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
    qs = _pendencia(qs, g.get("p"))
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
        "setores": Setor.objects.all(), "pavimentos": Pavimento.objects.all(), "pendencias": PENDENCIAS, "dias": settings.DIAS_CONFERENCIA,
    })


ROTULOS = {"asset_id": "Asset ID", "tipo": "Tipo", "status": "Status", "responsavel": "Responsável", "serial": "Nº série",
           "fornecedor": "Fornecedor", "setor": "Setor", "pavimento": "Andar", "obs": "Obs"}


def equipamento_form(request, pk=None):
    obj = get_object_or_404(Equipamento, pk=pk) if pk else None
    antes = {c: str(getattr(obj, c) or "") for c in ROTULOS} if obj else {}
    antes_disp = {c: (getattr(obj, f"get_{c}_display")() if c in ("tipo", "status") else str(getattr(obj, c) or "")) for c in ROTULOS} if obj else {}
    form = EquipamentoForm(request.POST or None, instance=obj)
    if request.method == "POST" and form.is_valid():
        e = form.save()
        if obj:
            difs = []
            for c in form.changed_data:
                dep = getattr(e, f"get_{c}_display")() if c in ("tipo", "status") else str(getattr(e, c) or "")
                difs.append(f"{ROTULOS[c]}: {antes_disp[c] or '—'} → {dep or '—'}")
            detalhe = "Edição manual · " + " · ".join(difs) if difs else "Salvo sem alterações"
        else:
            detalhe = "Criado manualmente"
        Historico.objects.create(asset_id=e.asset_id, evento="alterado" if obj else "novo", origem="manual", detalhe=detalhe)
        messages.success(request, f"{e.asset_id} salvo.")
        return redirect("lista")
    return render(request, "inventario/equipamento_form.html", {
        "form": form, "obj": obj, "historico": Historico.objects.filter(asset_id=obj.asset_id)[:60] if obj else [],
        "dias": settings.DIAS_CONFERENCIA})


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


# ---------------- relatório PDF ----------------
def relatorio_pagina(request):
    return render(request, "inventario/relatorio.html", {"pavimentos": Pavimento.objects.all(), "total": Equipamento.objects.filter(ausente=False).count()})


def relatorio_pdf(request):
    g = request.GET
    ids = {int(x) for x in g.getlist("pav") if x.isdigit()}
    pdf = relatorio.gerar_pdf(pavimento_ids=ids or None, pinos="1" in g.getlist("pinos") or "pinos" not in g, lista=g.get("lista") == "1")
    r = HttpResponse(pdf, content_type="application/pdf")
    r["Content-Disposition"] = f'{"attachment" if g.get("baixar") == "1" else "inline"}; filename="inventario-fsbr-{date.today():%Y-%m-%d}.pdf"'
    return r


# ---------------- dia a dia: busca, setores, conferência, etiquetas ----------------
def buscar(request):
    """Busca rápida do cabeçalho: se o código bate exatamente com um Asset ID/série, abre direto o equipamento."""
    q = (request.GET.get("q") or "").strip()
    if q:
        exato = Equipamento.objects.filter(Q(asset_id__iexact=q) | Q(serial__iexact=q))
        if exato.count() == 1:
            return redirect("equipamento_editar", pk=exato.first().pk)
    return redirect(reverse("lista") + "?" + urlencode({"q": q}))


def setores_gerenciar(request):
    setores = Setor.objects.annotate(n_eq=Count("equipamentos", distinct=True), n_areas=Count("areas", distinct=True))
    return render(request, "inventario/setores_gerenciar.html", {
        "setores": setores,
        "urls": {"editar": reverse("api_setor_editar", args=[0]), "mesclar": reverse("api_setor_mesclar", args=[0]),
                 "excluir": reverse("api_setor_excluir", args=[0]), "criar": reverse("api_setor_criar")},
    })


def conferencia(request):
    g = request.GET
    dias = int(g["dias"]) if (g.get("dias") or "").isdigit() else settings.DIAS_CONFERENCIA
    limite = timezone.now() - timedelta(days=dias)
    qs = Equipamento.objects.filter(ausente=False).select_related("setor", "pavimento")
    if g.get("setor") == "none":
        qs = qs.filter(setor__isnull=True)
    elif g.get("setor"):
        qs = qs.filter(setor_id=g["setor"])
    if g.get("pavimento"):
        qs = qs.filter(pavimento_id=g["pavimento"])
    itens = list(qs.order_by("setor__nome", "asset_id"))
    for e in itens:
        e.ok = bool(e.ultima_conferencia and e.ultima_conferencia >= limite)
    conferidos = sum(1 for e in itens if e.ok)
    return render(request, "inventario/conferencia.html", {
        "itens": itens, "conferidos": conferidos, "total": len(itens), "dias": dias, "g": g,
        "setores": Setor.objects.all(), "pavimentos": Pavimento.objects.all(), "so_pendentes": g.get("pendentes") == "1",
        "url_conferir": reverse("api_conferir")})


def etiquetas(request):
    """PDF de etiquetas (QR + código de barras Code128 do Asset ID). `ids=1,2,3` ou os mesmos filtros da lista."""
    ids = [int(i) for i in (request.GET.get("ids") or "").split(",") if i.isdigit()]
    qs = Equipamento.objects.filter(pk__in=ids) if ids else _filtrar(request)
    qs = qs.select_related("setor", "pavimento")[:600]
    r = HttpResponse(relatorio.gerar_etiquetas(list(qs)), content_type="application/pdf")
    r["Content-Disposition"] = f'inline; filename="etiquetas-fsbr-{date.today():%Y-%m-%d}.pdf"'
    return r
