from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand

from inventario.models import Pavimento

SEED = Path(__file__).resolve().parents[2] / "seed" / "plantas"
PLANTAS = [("Térreo", 0, "terreo.png"), ("1º Pavimento", 1, "pavimento1.png"), ("2º Pavimento", 2, "pavimento2.png")]


class Command(BaseCommand):
    help = "Cadastra as plantas dos 3 pavimentos (idempotente). Novas plantas também podem ser enviadas pelo Admin."

    def handle(self, *args, **opts):
        for nome, ordem, arq in PLANTAS:
            if Pavimento.objects.filter(nome=nome).exists():
                continue
            with open(SEED / arq, "rb") as f:
                p = Pavimento(nome=nome, ordem=ordem)
                p.imagem.save(arq, File(f), save=True)
            self.stdout.write(f"Planta cadastrada: {nome}")
