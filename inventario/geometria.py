"""Geometria 2D simples (coordenadas em % da planta)."""


def ponto_em_poligono(x, y, pontos):
    dentro = False
    n = len(pontos)
    j = n - 1
    for i in range(n):
        xi, yi = pontos[i]
        xj, yj = pontos[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi:
            dentro = not dentro
        j = i
    return dentro


def area_poligono(pontos):
    s = 0.0
    for i in range(len(pontos)):
        x1, y1 = pontos[i]
        x2, y2 = pontos[(i + 1) % len(pontos)]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2


def validar_pontos(pontos):
    """Devolve a lista limpa [[x, y], ...] (>=3 pontos entre 0 e 100) ou levanta ValueError."""
    if not isinstance(pontos, list) or len(pontos) < 3:
        raise ValueError("Uma área precisa de pelo menos 3 pontos.")
    out = []
    for p in pontos:
        try:
            x, y = float(p[0]), float(p[1])
        except (TypeError, ValueError, IndexError, KeyError):
            raise ValueError("Pontos inválidos.")
        if not (-0.001 <= x <= 100.001 and -0.001 <= y <= 100.001):
            raise ValueError("Pontos fora da planta.")
        out.append([round(min(100.0, max(0.0, x)), 3), round(min(100.0, max(0.0, y)), 3)])
    if area_poligono(out) < 0.01:
        raise ValueError("Área muito pequena.")
    return out


def setor_no_ponto(areas, x, y):
    """`areas`: iterável de objetos com .pontos e .setor_id (já filtrado por pavimento).
    Em caso de áreas sobrepostas vence a menor (a mais específica)."""
    melhor, melhor_area = None, None
    for a in areas:
        if ponto_em_poligono(x, y, a.pontos):
            ar = area_poligono(a.pontos)
            if melhor is None or ar < melhor_area:
                melhor, melhor_area = a, ar
    return melhor.setor_id if melhor else None
