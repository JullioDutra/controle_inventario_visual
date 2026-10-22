"""Relatório em PDF: resumo geral + uma página por andar (planta com áreas, pinos e quantidades por setor)."""
import io
from collections import Counter, defaultdict

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import Flowable, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .geometria import area_poligono
from .models import Area, Equipamento, Pavimento, Setor

VERMELHO = colors.HexColor("#e63329")
CINZA = colors.HexColor("#656d76")
LINHA = colors.HexColor("#d8dee4")
COR_TIPO = {"laptop": "#e63329", "tinypc": "#1f6feb", "impressora": "#8957e5", "outro": "#6e7781"}
COR_STATUS = {"operacional": "#1a7f37", "backup": "#bf8700", "instalar": "#0969da", "outro": "#6e7781"}
TIPOS = list(Equipamento.Tipo.choices)
STATUS = list(Equipamento.Status.choices)
COLUNAS_TIPO = [(k, n) for k, n in TIPOS if k != "outro"]
COLUNAS_STATUS = [(k, n) for k, n in STATUS if k != "outro"]

_ss = getSampleStyleSheet()
H1 = ParagraphStyle("h1", parent=_ss["Heading1"], fontSize=17, spaceAfter=4, textColor=colors.HexColor("#1f2328"))
H2 = ParagraphStyle("h2", parent=_ss["Heading2"], fontSize=12, spaceBefore=8, spaceAfter=4)
TXT = ParagraphStyle("t", parent=_ss["BodyText"], fontSize=8.5, leading=11, textColor=CINZA)


def _tabela(dados, larguras=None, destaque_ultima=False, alinhar_direita_a_partir=1):
    t = Table(dados, colWidths=larguras, repeatRows=1)
    est = [
        ("FONT", (0, 0), (-1, -1), "Helvetica", 8), ("FONT", (0, 0), (-1, 0), "Helvetica-Bold", 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f6f7f9")), ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINHA),
        ("ALIGN", (alinhar_direita_a_partir, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2.5), ("BOTTOMPADDING", (0, 0), (-1, -1), 2.5),
    ]
    if destaque_ultima:
        est += [("FONT", (0, -1), (-1, -1), "Helvetica-Bold", 8), ("LINEABOVE", (0, -1), (-1, -1), 0.8, colors.black)]
    t.setStyle(TableStyle(est))
    return t


class Planta(Flowable):
    """Imagem da planta com as áreas dos setores (translúcidas), rótulos com a quantidade e os pinos."""

    def __init__(self, caminho, largura, areas, rotulos, pinos):
        super().__init__()
        self.caminho, self.w, self.areas, self.rotulos, self.pinos = caminho, largura, areas, rotulos, pinos
        from reportlab.lib.utils import ImageReader
        iw, ih = ImageReader(caminho).getSize()
        self.h = largura * ih / iw

    def wrap(self, *_):
        return self.w, self.h

    def _pt(self, x, y):
        return x / 100 * self.w, self.h - y / 100 * self.h

    def draw(self):
        c = self.canv
        c.drawImage(self.caminho, 0, 0, self.w, self.h)
        for pontos, cor in self.areas:
            p = c.beginPath()
            for i, (x, y) in enumerate(pontos):
                (p.moveTo if i == 0 else p.lineTo)(*self._pt(x, y))
            p.close()
            c.saveState(); c.setFillColor(colors.HexColor(cor)); c.setFillAlpha(0.22); c.drawPath(p, stroke=0, fill=1); c.restoreState()
            c.saveState(); c.setStrokeColor(colors.HexColor(cor)); c.setLineWidth(1.1); c.drawPath(p, stroke=1, fill=0); c.restoreState()
        for x, y, nome, n in self.rotulos:
            texto = nome if n is None else f"{nome}  {n}"
            c.setFont("Helvetica-Bold", 6.5)
            larg = stringWidth(texto, "Helvetica-Bold", 6.5) + 6
            px, py = self._pt(x, y)
            px = min(max(px, larg / 2), self.w - larg / 2)
            c.saveState(); c.setFillColor(colors.white); c.setFillAlpha(0.88); c.setStrokeColor(colors.HexColor("#8c959f")); c.setLineWidth(0.3)
            c.roundRect(px - larg / 2, py - 4.5, larg, 9, 3, stroke=1, fill=1); c.restoreState()
            c.setFillColor(colors.black); c.drawCentredString(px, py - 2.2, texto)
        for x, y, tipo, status in self.pinos:
            px, py = self._pt(x, y)
            c.saveState()
            c.setFillColor(colors.HexColor(COR_TIPO.get(tipo, "#6e7781"))); c.setStrokeColor(colors.HexColor(COR_STATUS.get(status, "#fff")) if status != "operacional" else colors.white)
            c.setLineWidth(0.9 if status != "operacional" else 0.6)
            if tipo == "impressora":
                c.rect(px - 2.3, py - 2.3, 4.6, 4.6, stroke=1, fill=1)
            else:
                c.circle(px, py, 2.4, stroke=1, fill=1)
            c.restoreState()


class Legenda(Flowable):
    def __init__(self, largura):
        super().__init__(); self.w = largura

    def wrap(self, *_):
        return self.w, 12

    def draw(self):
        c, x = self.canv, 0
        for k, nome in COLUNAS_TIPO:
            c.setFillColor(colors.HexColor(COR_TIPO[k]))
            (c.rect(x, 2, 6, 6, stroke=0, fill=1) if k == "impressora" else c.circle(x + 3, 5, 3, stroke=0, fill=1))
            c.setFillColor(CINZA); c.setFont("Helvetica", 7.5); c.drawString(x + 9, 3, nome); x += 20 + stringWidth(nome, "Helvetica", 7.5)
        x += 14
        c.setFillColor(CINZA); c.drawString(x, 3, "Contorno do pino:"); x += 66
        for k, nome in [("operacional", "branco = operacional"), ("backup", "amarelo = backup"), ("instalar", "azul = a instalar")]:
            c.setFillColor(colors.HexColor(COR_STATUS[k] if k != "operacional" else "#c0c6cc")); c.circle(x + 3, 5, 3, stroke=0, fill=1)
            c.setFillColor(CINZA); c.drawString(x + 9, 3, nome); x += 20 + stringWidth(nome, "Helvetica", 7.5)


def _linha_contagem(nome, regs):
    """regs: lista de (tipo, status). Devolve [nome, laptop, tiny, impressora, outro, total, operac, backup, instalar]."""
    ct, cs = Counter(t for t, _ in regs), Counter(s for _, s in regs)
    return [nome] + [ct.get(k, 0) for k, _ in COLUNAS_TIPO] + [ct.get("outro", 0), len(regs)] + [cs.get(k, 0) for k, _ in COLUNAS_STATUS]


CAB = ["Local"] + [n for _, n in COLUNAS_TIPO] + ["Outro", "Total"] + [n for _, n in COLUNAS_STATUS]


def _tabela_contagens(linhas, larg_total, total=True, rotulo="Local"):
    dados = [[rotulo] + CAB[1:]] + linhas
    if total and linhas:
        dados.append(["TOTAL"] + [sum(l[i] for l in linhas) for i in range(1, len(CAB))])
    resto = (larg_total - 150) / (len(CAB) - 1)
    return _tabela(dados, [150] + [resto] * (len(CAB) - 1), destaque_ultima=total and bool(linhas))


def gerar_pdf(pavimento_ids=None, pinos=True, lista=False):
    agora = timezone.localtime()
    todos = list(Equipamento.objects.select_related("setor", "pavimento"))
    ativos = [e for e in todos if not e.ausente]
    n_ausentes = len(todos) - len(ativos)
    setores = {s.pk: s for s in Setor.objects.all()}
    pavs = list(Pavimento.objects.order_by("ordem", "nome"))
    if pavimento_ids is not None:
        pavs = [p for p in pavs if p.pk in pavimento_ids]

    buf = io.BytesIO()
    pag = landscape(A4)
    M = 14 * mm
    util = pag[0] - 2 * M

    def moldura(c, doc):
        c.saveState()
        c.setFillColor(VERMELHO); c.rect(0, pag[1] - 11 * mm, pag[0], 11 * mm, stroke=0, fill=1)
        c.setFillColor(colors.white); c.setFont("Helvetica-Bold", 11); c.drawString(M, pag[1] - 7.2 * mm, "Fagron  ·  Inventário visual FSBR")
        c.setFont("Helvetica", 8); c.drawRightString(pag[0] - M, pag[1] - 7 * mm, f"Gerado em {agora:%d/%m/%Y %H:%M}")
        c.setFillColor(CINZA); c.setFont("Helvetica", 7.5); c.drawRightString(pag[0] - M, 7 * mm, f"Página {doc.page}")
        c.drawString(M, 7 * mm, "Contagens consideram apenas ativos presentes na última exportação do TopDesk.")
        c.restoreState()

    doc = SimpleDocTemplate(buf, pagesize=pag, leftMargin=M, rightMargin=M, topMargin=17 * mm, bottomMargin=13 * mm,
                            title="Inventário visual FSBR", author="Inventário visual FSBR")
    h = []

    # ---------- resumo ----------
    cs = Counter(e.status for e in ativos)
    ct = Counter(e.tipo for e in ativos)
    h += [Paragraph("Resumo do inventário de ativos", H1),
          Paragraph(f"{len(ativos)} ativos no total · {len([e for e in ativos if e.posicionado])} posicionados nas plantas"
                    + (f" · {n_ausentes} ausente(s) no último TopDesk não contados" if n_ausentes else ""), TXT), Spacer(1, 6)]
    kpi = [["Total"] + [n for _, n in COLUNAS_TIPO] + [n for _, n in COLUNAS_STATUS],
           [len(ativos)] + [ct.get(k, 0) for k, _ in COLUNAS_TIPO] + [cs.get(k, 0) for k, _ in COLUNAS_STATUS]]
    t = Table(kpi, colWidths=[util / len(kpi[0])] * len(kpi[0]))
    t.setStyle(TableStyle([("FONT", (0, 0), (-1, 0), "Helvetica", 8), ("TEXTCOLOR", (0, 0), (-1, 0), CINZA), ("FONT", (0, 1), (-1, 1), "Helvetica-Bold", 20),
                           ("BOX", (0, 0), (-1, -1), 0.5, LINHA), ("INNERGRID", (0, 0), (-1, -1), 0.5, LINHA), ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fafbfc")),
                           ("ALIGN", (0, 0), (-1, -1), "CENTER"), ("TOPPADDING", (0, 1), (-1, 1), 6), ("BOTTOMPADDING", (0, 1), (-1, 1), 6)]))
    h += [t, Spacer(1, 8), Paragraph("Tipo × status", H2)]
    linhas = []
    for k, n in TIPOS:
        regs = [(e.tipo, e.status) for e in ativos if e.tipo == k]
        if regs or k != "outro":
            linhas.append([n, *(sum(1 for _, s in regs if s == sk) for sk, _ in COLUNAS_STATUS), len(regs)])
    dados = [["Tipo"] + [n for _, n in COLUNAS_STATUS] + ["Total"]] + linhas
    tt = _tabela(dados, [120, 70, 70, 70, 70]); tt.hAlign = "LEFT"; h += [tt]

    h += [Paragraph("Por andar", H2)]
    por_pav = defaultdict(list)
    for e in ativos:
        por_pav[e.pavimento_id].append((e.tipo, e.status))
    linhas = [_linha_contagem(p.nome, por_pav.get(p.pk, [])) for p in Pavimento.objects.order_by("ordem", "nome")]
    if por_pav.get(None):
        linhas.append(_linha_contagem("Sem andar definido", por_pav[None]))
    h += [_tabela_contagens(linhas, util, rotulo="Andar")]

    h += [Paragraph("Por setor", H2)]
    por_set = defaultdict(list)
    for e in ativos:
        por_set[e.setor_id].append((e.tipo, e.status))
    linhas = [_linha_contagem(setores[sid].nome, regs) for sid, regs in sorted(por_set.items(), key=lambda kv: (kv[0] is None, -len(kv[1]))) if sid is not None]
    if por_set.get(None):
        linhas.append(_linha_contagem("Sem setor definido", por_set[None]))
    h += [_tabela_contagens(linhas, util, rotulo="Setor")]

    # ---------- uma página por andar ----------
    areas_por_pav = defaultdict(list)
    for a in Area.objects.select_related("setor"):
        areas_por_pav[a.pavimento_id].append(a)
    for p in pavs:
        no_andar = [e for e in ativos if e.pavimento_id == p.pk]
        por_setor = defaultdict(list)
        for e in no_andar:
            por_setor[e.setor_id].append(e)
        h += [PageBreak(), Paragraph(f"{p.nome} — {len(no_andar)} ativos", H1)]
        sem_pos = sum(1 for e in no_andar if not e.posicionado)
        h += [Paragraph("Rótulo = nome do setor e quantidade de ativos atribuídos a ele neste andar."
                        + (f" {sem_pos} ativo(s) deste andar ainda sem posição exata na planta." if sem_pos else ""), TXT), Spacer(1, 4)]
        areas, rotulos, maiores = [], [], {}
        for a in areas_por_pav.get(p.pk, []):
            areas.append((a.pontos, a.setor.cor))
            ar = area_poligono(a.pontos)
            if a.setor_id not in maiores or ar > maiores[a.setor_id][0]:
                maiores[a.setor_id] = (ar, a)
        for a in areas_por_pav.get(p.pk, []):
            cx, cy = _centroide(a.pontos)
            principal = maiores[a.setor_id][1].pk == a.pk
            rotulos.append((cx, cy, a.setor.nome, len(por_setor.get(a.setor_id, [])) if principal else None))
        pins = [(e.pos_x, e.pos_y, e.tipo, e.status) for e in no_andar if e.posicionado] if pinos else []
        h += [Planta(p.imagem.path, util, areas, rotulos, pins), Spacer(1, 3), Legenda(util), Spacer(1, 6)]
        linhas = [_linha_contagem(setores[sid].nome, [(e.tipo, e.status) for e in es]) for sid, es in
                  sorted(por_setor.items(), key=lambda kv: (kv[0] is None, -len(kv[1]))) if sid is not None]
        if por_setor.get(None):
            linhas.append(_linha_contagem("Sem setor definido", [(e.tipo, e.status) for e in por_setor[None]]))
        h += [_tabela_contagens(linhas, util, rotulo="Setor") if linhas else Paragraph("Nenhum ativo atribuído a este andar.", TXT)]

    # ---------- anexo: lista por setor ----------
    if lista:
        h += [PageBreak(), Paragraph("Anexo — equipamentos por setor", H1)]
        grupos = defaultdict(list)
        for e in ativos:
            grupos[e.setor_id].append(e)
        for sid, es in sorted(grupos.items(), key=lambda kv: (kv[0] is None, setores[kv[0]].nome if kv[0] else "")):
            h += [Paragraph(f"{setores[sid].nome if sid else 'Sem setor definido'} ({len(es)})", H2)]
            dados = [["Asset ID", "Tipo", "Status", "Responsável", "Andar", "Nº série", "Obs"]]
            for e in sorted(es, key=lambda x: x.asset_id):
                dados.append([e.asset_id, e.get_tipo_display(), e.get_status_display(), (e.responsavel or "—")[:28],
                              e.pavimento.nome if e.pavimento else "—", e.serial, (e.obs or "")[:48]])
            h += [_tabela(dados, [62, 55, 60, 120, 75, 70, util - 442], alinhar_direita_a_partir=99)]

    doc.build(h, onFirstPage=moldura, onLaterPages=moldura)
    return buf.getvalue()


def _centroide(p):
    a = cx = cy = 0.0
    for i in range(len(p)):
        x1, y1 = p[i]
        x2, y2 = p[(i + 1) % len(p)]
        c = x1 * y2 - x2 * y1
        a += c; cx += (x1 + x2) * c; cy += (y1 + y2) * c
    if abs(a) < 1e-9:
        return sum(q[0] for q in p) / len(p), sum(q[1] for q in p) / len(p)
    return cx / (3 * a), cy / (3 * a)


def gerar_etiquetas(equipamentos, colunas=3, linhas=8):
    """Folha A4 retrato de etiquetas (colunas x linhas). Cada uma: Asset ID, tipo, setor/andar, QR e Code128 do Asset ID."""
    from reportlab.graphics import renderPDF
    from reportlab.graphics.barcode import code128
    from reportlab.graphics.barcode.qr import QrCodeWidget
    from reportlab.graphics.shapes import Drawing
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4, pageCompression=1)
    W, H = A4
    mx, my = 6 * mm, 10 * mm
    cw, ch = (W - 2 * mx) / colunas, (H - 2 * my) / linhas
    por_pagina = colunas * linhas
    if not equipamentos:
        c.setFont("Helvetica", 11); c.drawString(mx, H - 20 * mm, "Nenhum equipamento selecionado."); c.save(); return buf.getvalue()
    for i, e in enumerate(equipamentos):
        pos = i % por_pagina
        if i and pos == 0:
            c.showPage()
        x = mx + (pos % colunas) * cw
        y = H - my - (pos // colunas + 1) * ch
        c.setStrokeColor(colors.HexColor("#c0c6cc")); c.setLineWidth(0.3); c.setDash(1, 2); c.roundRect(x + 1, y + 1, cw - 2, ch - 2, 2 * mm); c.setDash()
        c.setFillColor(VERMELHO); c.setFont("Helvetica-Bold", 6.5); c.drawString(x + 3 * mm, y + ch - 5 * mm, "FAGRON · FSBR")
        c.setFillColor(colors.black); c.setFont("Helvetica-Bold", 13); c.drawString(x + 3 * mm, y + ch - 11 * mm, e.asset_id)
        c.setFont("Helvetica", 7); c.setFillColor(CINZA)
        c.drawString(x + 3 * mm, y + ch - 15 * mm, e.get_tipo_display() + (f" · {e.serial}" if e.serial else ""))
        local = " · ".join(v for v in (e.setor.nome if e.setor else "", e.pavimento.nome if e.pavimento else "") if v)
        c.drawString(x + 3 * mm, y + ch - 18.5 * mm, local[:34])
        bc = code128.Code128(e.asset_id, barHeight=7 * mm, barWidth=0.32 * mm, quiet=False)
        if bc.width > cw - 8 * mm - 17 * mm:  # códigos longos: estreita as barras
            bc = code128.Code128(e.asset_id, barHeight=7 * mm, barWidth=0.2 * mm, quiet=False)
        bc.drawOn(c, x + 3 * mm, y + 3 * mm)
        q = QrCodeWidget(e.asset_id, barLevel="M")
        b = q.getBounds(); lado = 16 * mm
        d = Drawing(lado, lado, transform=[lado / (b[2] - b[0]), 0, 0, lado / (b[3] - b[1]), 0, 0]); d.add(q)
        renderPDF.draw(d, c, x + cw - lado - 3 * mm, y + ch - lado - 3 * mm)
    c.save()
    return buf.getvalue()
