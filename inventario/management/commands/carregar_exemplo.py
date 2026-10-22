from pathlib import Path

from django.core.management import call_command
from django.core.management.base import BaseCommand

from inventario import importador
from inventario.models import Area, Pavimento, Setor

SEED = Path(__file__).resolve().parents[2] / "seed"
# Retângulos aproximados das Partes A–H, medidos nas plantas (px do desenho a 2000 px de largura).
# O recorte da planta começa em (185, 165) e mede 1350 x 385; abaixo convertemos para % da imagem.
_RECORTE = (185, 165, 1350, 385)
_PX = {
    "Térreo": {"A": (233, 262, 415, 405), "C": (415, 255, 810, 365), "E": (810, 255, 1075, 365), "B": (220, 405, 510, 538),
               "D": (510, 395, 907, 538), "F": (907, 392, 1165, 538), "G": (1108, 237, 1500, 400), "H": (1165, 400, 1500, 540)},
    "1º Pavimento": {"A": (252, 262, 437, 400), "B": (240, 400, 530, 515), "C": (437, 262, 815, 390), "D": (530, 390, 925, 520),
                     "E": (815, 262, 1078, 390), "F": (925, 390, 1170, 520), "G": (1170, 230, 1520, 400), "H": (1170, 400, 1520, 540)},
    "2º Pavimento": {"A": (245, 250, 455, 385), "B": (228, 388, 518, 508), "C": (455, 235, 820, 385), "D": (518, 385, 912, 508),
                     "E": (820, 235, 1062, 385), "F": (912, 380, 1160, 508), "G": (1160, 225, 1510, 375), "H": (1160, 375, 1510, 515)},
}


def _pct(r):
    ox, oy, w, h = _RECORTE
    x1, y1, x2, y2 = r
    return tuple(round(v, 2) for v in ((x1 - ox) / w * 100, (y1 - oy) / h * 100, (x2 - ox) / w * 100, (y2 - oy) / h * 100))


PARTES = {pav: {k: _pct(v) for k, v in zonas.items()} for pav, zonas in _PX.items()}
CORES = dict(zip("ABCDEFGH", ["#f0a030", "#6a5acd", "#d6457a", "#4caf50", "#d4c020", "#2a9d8f", "#4aa3df", "#1f6feb"]))


class Command(BaseCommand):
    help = "Carrega a planilha de exemplo do TopDesk e, com --partes, cria 'Parte A…H' como setores de partida na planta."

    def add_arguments(self, p):
        p.add_argument("--partes", action="store_true", help="Cria as Partes A–H do projeto como setores editáveis.")

    def handle(self, *args, **o):
        call_command("carregar_plantas")
        arq = SEED / "topdesk-exemplo.xlsx"
        linhas, _ = importador.ler_arquivo(arq.name, arq.read_bytes())
        res, _ = importador.processar(linhas, arq.name, aplicar=True)
        self.stdout.write(f"Importados: {res}")
        if o["partes"]:
            for pav in Pavimento.objects.all():
                for letra, (x1, y1, x2, y2) in PARTES.get(pav.nome, {}).items():
                    s, _ = Setor.objects.get_or_create(nome=f"Parte {letra}", defaults={"cor": CORES[letra]})
                    if not Area.objects.filter(setor=s, pavimento=pav).exists():
                        Area.objects.create(setor=s, pavimento=pav, pontos=[[x1, y1], [x2, y1], [x2, y2], [x1, y2]])
            self.stdout.write("Partes A–H criadas.")
