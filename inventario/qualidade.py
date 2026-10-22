"""Verificações de qualidade dos dados. Cada achado cita o(s) ativo(s) e o motivo."""
from collections import defaultdict

from .models import Equipamento


def verificar():
    achados = []
    eqs = list(Equipamento.objects.select_related("setor", "pavimento"))
    por_serial, por_pessoa = defaultdict(list), defaultdict(list)
    for e in eqs:
        add = lambda sev, msg: achados.append({"sev": sev, "ids": [e.asset_id], "pk": e.pk, "msg": msg})
        if e.serial:
            por_serial[e.serial.upper()].append(e)
        else:
            add("alta", "Sem número de série")
        if e.ausente:
            add("alta", "Ausente na última exportação do TopDesk")
        if e.tipo == "laptop" and e.status == "operacional" and not e.responsavel:
            add("alta", "Laptop operacional sem responsável")
            continue
        if e.status == "backup" and e.responsavel:
            add("media", f"Em backup mas atribuído a {e.responsavel}")
        if e.tipo == "laptop" and e.status == "operacional" and e.responsavel:
            por_pessoa[e.responsavel].append(e)
        if not e.ausente and not e.posicionado:
            add("baixa", "Sem posição na planta")
        elif e.posicionado and e.setor_id is None:
            add("baixa", "Posicionado fora de qualquer setor desenhado")
    for s, l in por_serial.items():
        if len(l) > 1:
            achados.append({"sev": "alta", "ids": [x.asset_id for x in l], "pk": l[0].pk, "msg": f"Número de série duplicado ({s})"})
    for p, l in por_pessoa.items():
        if len(l) > 1:
            achados.append({"sev": "media", "ids": [x.asset_id for x in l], "pk": l[0].pk, "msg": f"{p} tem {len(l)} laptops operacionais"})
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    achados.sort(key=lambda a: ordem[a["sev"]])
    return achados
