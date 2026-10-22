"""Endpoints JSON (POST) das telas interativas. CSRF é exigido (header X-CSRFToken)."""
import json
import re
from functools import wraps

from django.http import JsonResponse
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from . import geometria
from .models import Area, Equipamento, Historico, Pavimento, Setor


def json_view(fn):
    @require_POST
    @wraps(fn)
    def inner(request, *a, **kw):
        try:
            dados = json.loads(request.body or b"{}")
            if not isinstance(dados, dict):
                raise ValueError
        except ValueError:
            return JsonResponse({"erro": "JSON inválido"}, status=400)
        try:
            return JsonResponse(fn(request, dados, *a, **kw))
        except ValueError as exc:
            return JsonResponse({"erro": str(exc)}, status=400)
    return inner


def _cor(v, padrao="#1f6feb"):
    return v if isinstance(v, str) and re.fullmatch(r"#[0-9a-fA-F]{6}", v) else padrao


def _num(v):
    if v is None:
        return None
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError("Coordenada inválida.")
    if not (0 <= v <= 100):
        raise ValueError("Coordenada fora da planta.")
    return round(v, 3)


def aplicar_setor_por_posicao(e):
    """Se o equipamento está dentro de uma área desenhada, o setor da área vence."""
    if not e.posicionado:
        return False
    sid = geometria.setor_no_ponto(Area.objects.filter(pavimento_id=e.pavimento_id), e.pos_x, e.pos_y)
    if sid is not None and sid != e.setor_id:
        e.setor_id = sid
        return True
    return False


@json_view
def posicao(request, d, pk):
    e = get_object_or_404(Equipamento, pk=pk)
    if d.get("x") is None or d.get("y") is None:  # remover do mapa
        e.pos_x = e.pos_y = None
        e.save(update_fields=["pos_x", "pos_y", "atualizado_em"])
        Historico.objects.create(asset_id=e.asset_id, evento="posicao", detalhe="Removido da planta", origem="planta")
    else:
        pav = get_object_or_404(Pavimento, pk=d.get("pavimento"))
        e.pavimento, e.pos_x, e.pos_y = pav, _num(d["x"]), _num(d["y"])
        mudou_setor = aplicar_setor_por_posicao(e)
        e.save()
        det = f"Posicionado em {pav.nome} ({e.pos_x:.1f}%, {e.pos_y:.1f}%)"
        if mudou_setor:
            det += f" → setor {e.setor.nome}"
        Historico.objects.create(asset_id=e.asset_id, evento="posicao", detalhe=det, origem="planta")
    return {"ok": True, "setor": e.setor_id, "pavimento": e.pavimento_id, "x": e.pos_x, "y": e.pos_y}


def _setor_dict(s):
    return {"id": s.pk, "nome": s.nome, "cor": s.cor}


def _dados_setor(d, s):
    nome = (d.get("nome") or "").strip()
    if not nome:
        raise ValueError("Informe o nome do setor.")
    if Setor.objects.filter(nome__iexact=nome).exclude(pk=s.pk).exists():
        raise ValueError("Já existe um setor com esse nome.")
    s.nome, s.cor = nome[:80], _cor(d.get("cor"))


@json_view
def setor_criar(request, d):
    s = Setor()
    _dados_setor(d, s)
    s.save()
    return _setor_dict(s)


@json_view
def setor_editar(request, d, pk):
    s = get_object_or_404(Setor, pk=pk)
    _dados_setor(d, s)
    s.save()
    return _setor_dict(s)


@json_view
def setor_excluir(request, d, pk):
    """Exclui o setor e suas áreas. Os equipamentos vão para `transferir_para` (se informado) ou ficam sem setor."""
    s = get_object_or_404(Setor, pk=pk)
    destino = get_object_or_404(Setor, pk=d["transferir_para"]) if d.get("transferir_para") else None
    if destino and destino.pk == s.pk:
        raise ValueError("Escolha outro setor como destino.")
    with transaction.atomic():
        n = s.equipamentos.count()
        if destino:
            s.equipamentos.update(setor=destino)
        Historico.objects.create(evento="setor", origem="setores", detalhe=(
            f"Setor “{s.nome}” excluído; {n} equipamento(s) " + (f"transferido(s) para “{destino.nome}”" if destino else "ficaram sem setor")))
        s.delete()  # áreas somem junto
    return {"ok": True, "equipamentos_afetados": n}


@json_view
def setor_mesclar(request, d, pk):
    """Junta o setor `pk` em `destino`: equipamentos e áreas passam para o destino e o setor de origem deixa de existir."""
    origem = get_object_or_404(Setor, pk=pk)
    destino = get_object_or_404(Setor, pk=d.get("destino"))
    if origem.pk == destino.pk:
        raise ValueError("Escolha outro setor como destino.")
    with transaction.atomic():
        n = origem.equipamentos.update(setor=destino)
        origem.areas.update(setor=destino)
        Historico.objects.create(evento="setor", origem="setores",
                                 detalhe=f"Setor “{origem.nome}” mesclado em “{destino.nome}” ({n} equipamento(s))")
        origem.delete()
    return {"ok": True, "equipamentos_movidos": n}


def _area_dict(a):
    return {"id": a.pk, "setor": a.setor_id, "pavimento": a.pavimento_id, "pontos": a.pontos}


@json_view
def area_criar(request, d):
    a = Area(setor=get_object_or_404(Setor, pk=d.get("setor")), pavimento=get_object_or_404(Pavimento, pk=d.get("pavimento")),
             pontos=geometria.validar_pontos(d.get("pontos")))
    a.save()
    return _area_dict(a)


@json_view
def area_editar(request, d, pk):
    a = get_object_or_404(Area, pk=pk)
    a.pontos = geometria.validar_pontos(d.get("pontos"))
    a.save()
    return _area_dict(a)


@json_view
def area_excluir(request, d, pk):
    get_object_or_404(Area, pk=pk).delete()
    return {"ok": True}


@json_view
def reatribuir(request, d):
    """Recalcula o setor de todos os equipamentos posicionados a partir das áreas desenhadas."""
    areas = {}
    for a in Area.objects.all():
        areas.setdefault(a.pavimento_id, []).append(a)
    mudados = []
    for e in Equipamento.objects.filter(pavimento__isnull=False, pos_x__isnull=False, pos_y__isnull=False).select_related("setor"):
        sid = geometria.setor_no_ponto(areas.get(e.pavimento_id, []), e.pos_x, e.pos_y)
        if sid is not None and sid != e.setor_id:
            e.setor_id = sid
            e.save(update_fields=["setor", "atualizado_em"])
            mudados.append(e.asset_id)
    if mudados:
        Historico.objects.create(asset_id="", evento="setor", origem="setores",
                                 detalhe=f"Setor reatribuído pela posição na planta em {len(mudados)} equipamento(s)")
    return {"ok": True, "alterados": len(mudados)}


@json_view
def nota(request, d, pk):
    e = get_object_or_404(Equipamento, pk=pk)
    texto = (d.get("texto") or "").strip()
    if not texto:
        raise ValueError("Escreva a nota.")
    h = Historico.objects.create(asset_id=e.asset_id, evento="nota", detalhe=texto[:1000], origem="nota")
    return {"ok": True, "quando": timezone.localtime(h.criado_em).strftime("%d/%m/%Y %H:%M"), "texto": h.detalhe}


@json_view
def conferir(request, d):
    """Marca equipamentos como conferidos fisicamente hoje. Aceita `ids` (pks) ou `codigo` (Asset ID ou nº de série, p. ex. leitor de código de barras)."""
    if d.get("codigo"):
        cod = str(d["codigo"]).strip()
        qs = Equipamento.objects.filter(asset_id__iexact=cod) or Equipamento.objects.filter(serial__iexact=cod)
        if not qs:
            raise ValueError(f"Nenhum equipamento com Asset ID ou série “{cod}”.")
    else:
        ids = [int(i) for i in d.get("ids", []) if str(i).isdigit()]
        if not ids:
            raise ValueError("Nada selecionado.")
        qs = Equipamento.objects.filter(pk__in=ids)
    agora = timezone.now()
    res = []
    for e in qs:
        e.ultima_conferencia = agora
        e.save(update_fields=["ultima_conferencia"])
        Historico.objects.create(asset_id=e.asset_id, evento="conferencia", detalhe="Conferido fisicamente", origem="conferência")
        res.append({"id": e.pk, "asset_id": e.asset_id, "tipo": e.get_tipo_display(), "responsavel": e.responsavel,
                    "setor": e.setor.nome if e.setor else "", "ausente": e.ausente})
    return {"ok": True, "conferidos": res}
