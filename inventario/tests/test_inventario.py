import json
from pathlib import Path

from django.core.files.base import ContentFile
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from inventario import geometria, importador
from inventario.models import Area, Equipamento, Historico, Importacao, Pavimento, Setor

EXEMPLO = Path(__file__).resolve().parents[1] / "seed" / "topdesk-exemplo.xlsx"
QUADRADO = [[10, 10], [50, 10], [50, 50], [10, 50]]


class GeometriaTests(TestCase):
    def test_ponto_em_poligono(self):
        self.assertTrue(geometria.ponto_em_poligono(30, 30, QUADRADO))
        self.assertFalse(geometria.ponto_em_poligono(60, 30, QUADRADO))
        l = [[0, 0], [40, 0], [40, 10], [10, 10], [10, 40], [0, 40]]  # formato em L
        self.assertTrue(geometria.ponto_em_poligono(5, 30, l))
        self.assertFalse(geometria.ponto_em_poligono(30, 30, l))

    def test_validar(self):
        self.assertEqual(len(geometria.validar_pontos(QUADRADO)), 4)
        for ruim in ([[0, 0], [1, 1]], [[0, 0], [1, 1], [200, 5]], "x", [[0, 0], [0, 0], [0, 0]]):
            with self.assertRaises(ValueError):
                geometria.validar_pontos(ruim)


@override_settings(MEDIA_ROOT="/tmp/inv_test_media")
class ImportadorTests(TestCase):
    def importar(self, linhas=None, aplicar=True, nome="x.xlsx"):
        if linhas is None:
            linhas, _ = importador.ler_arquivo(EXEMPLO.name, EXEMPLO.read_bytes())
        return importador.processar(linhas, nome, aplicar=aplicar)

    def test_leitura_do_exemplo(self):
        linhas, abas = importador.ler_arquivo(EXEMPLO.name, EXEMPLO.read_bytes())
        self.assertEqual(len(linhas), 134)
        self.assertEqual({a["nome"]: a["n"] for a in abas}, {"Laptop": 40, "PC - Tiny PC": 94})
        self.assertEqual(sum(l["tipo"] == "laptop" for l in linhas), 40)

    def test_previa_nao_grava(self):
        res, _ = self.importar(aplicar=False)
        self.assertEqual(res["novos"], 134)
        self.assertEqual(Equipamento.objects.count(), 0)
        self.assertEqual(Setor.objects.count(), 0)

    def test_aplicar_e_idempotencia(self):
        self.importar()
        self.assertEqual(Equipamento.objects.count(), 134)
        self.assertEqual(Equipamento.objects.filter(tipo="tinypc", status="instalar").count(), 10)
        self.assertTrue(Setor.objects.filter(nome="Produção").exists())
        res, mud = self.importar()
        self.assertEqual((res["novos"], res["alterados"], res["ausentes"], res["iguais"]), (0, 0, 0, 134))

    def test_atualiza_preserva_campos_locais_e_sinaliza_ausente(self):
        self.importar()
        pav = Pavimento.objects.create(nome="T", imagem="x.png")
        e = Equipamento.objects.get(asset_id="PLP001911")
        e.pavimento, e.pos_x, e.pos_y = pav, 12.5, 40.0
        e.save()
        linhas, _ = importador.ler_arquivo(EXEMPLO.name, EXEMPLO.read_bytes())
        for l in linhas:
            if l["asset_id"] == "PLP001911":
                l["status"], l["responsavel"] = "backup", ""
        linhas = [l for l in linhas if l["asset_id"] != "PPC000802"]
        res, mud = self.importar(linhas)
        self.assertEqual((res["alterados"], res["ausentes"]), (1, 1))
        e.refresh_from_db()
        self.assertEqual((e.status, e.responsavel, e.pos_x, e.pavimento_id), ("backup", "", 12.5, pav.pk))
        self.assertTrue(Equipamento.objects.get(asset_id="PPC000802").ausente)
        self.assertEqual(Equipamento.objects.count(), 134)  # nada apagado
        self.importar()  # volta a aparecer
        self.assertFalse(Equipamento.objects.get(asset_id="PPC000802").ausente)

    def test_coluna_ausente_nao_apaga_dado_e_extras_sao_guardados(self):
        Equipamento.objects.create(asset_id="PIM1", tipo="impressora", fornecedor="HP Brasil", responsavel="Ana")
        csv = "Asset ID;Status;Modelo\nPIM1;Operational;LaserJet 400\nPIM2;Backup;Zebra\n".encode()
        linhas, abas = importador.ler_arquivo("impressoras.csv", csv)
        self.assertEqual(len(linhas), 2)
        self.importar(linhas)
        e = Equipamento.objects.get(asset_id="PIM1")
        self.assertEqual((e.fornecedor, e.responsavel, e.tipo), ("HP Brasil", "Ana", "impressora"))
        self.assertEqual(e.extras, {"Modelo": "LaserJet 400"})
        self.assertEqual(Equipamento.objects.get(asset_id="PIM2").status, "backup")

    def test_duplicados_e_arquivo_sem_asset_id(self):
        linhas, _ = importador.ler_arquivo("a.csv", b"Asset ID;Status\nA1;Backup\nA1;Operational\n")
        res, _ = self.importar(linhas)
        self.assertEqual((res["novos"], res["duplicados"]), (1, 1))
        self.assertEqual(importador.ler_arquivo("b.csv", b"Nome;Valor\nx;1\n")[0], [])


@override_settings(MEDIA_ROOT="/tmp/inv_test_media")
class TelasEApiTests(TestCase):
    def setUp(self):
        self.pav = Pavimento.objects.create(nome="Térreo", imagem=ContentFile(b"x", "t.png"))
        self.pav2 = Pavimento.objects.create(nome="1º", ordem=1, imagem=ContentFile(b"x", "u.png"))
        self.e = Equipamento.objects.create(asset_id="PLP1", tipo="laptop", serial="S1", responsavel="Ana")

    def post(self, nome, dados, *args):
        return self.client.post(reverse(nome, args=args), json.dumps(dados), content_type="application/json")

    def test_ciclo_setor_area_posicao(self):
        r = self.post("api_setor_criar", {"nome": "Produção", "cor": "#ff0000"})
        self.assertEqual(r.status_code, 200)
        sid = r.json()["id"]
        self.assertEqual(self.post("api_setor_criar", {"nome": "produção"}).status_code, 400)  # nome repetido
        a = self.post("api_area_criar", {"setor": sid, "pavimento": self.pav.pk, "pontos": QUADRADO}).json()
        r = self.post("api_posicao", {"pavimento": self.pav.pk, "x": 30, "y": 30}, self.e.pk).json()
        self.assertEqual(r["setor"], sid)  # caiu dentro da área → herda o setor
        self.e.refresh_from_db()
        self.assertEqual((self.e.pos_x, self.e.setor_id), (30.0, sid))
        # mover a área para longe e reatribuir não tira o setor (fora de qualquer área mantém), mas outra área vence
        s2 = self.post("api_setor_criar", {"nome": "Lab"}).json()["id"]
        self.post("api_area_criar", {"setor": s2, "pavimento": self.pav.pk, "pontos": [[20, 20], [40, 20], [40, 40], [20, 40]]})
        self.assertEqual(self.post("api_posicao", {"pavimento": self.pav.pk, "x": 30, "y": 30}, self.e.pk).json()["setor"], s2)  # menor área vence
        self.assertEqual(self.post("api_reatribuir", {}).json()["alterados"], 0)
        # editar área
        r = self.post("api_area_editar", {"pontos": [[0, 0], [5, 0], [5, 5]]}, a["id"])
        self.assertEqual(r.status_code, 200)
        self.assertEqual(self.post("api_area_editar", {"pontos": [[0, 0]]}, a["id"]).status_code, 400)
        # remover do mapa
        self.post("api_posicao", {"x": None, "y": None}, self.e.pk)
        self.e.refresh_from_db()
        self.assertIsNone(self.e.pos_x)
        self.assertTrue(Historico.objects.filter(asset_id="PLP1", evento="posicao").exists())
        # excluir setor mantém o equipamento
        self.assertTrue(self.post("api_setor_excluir", {}, s2).json()["ok"])
        self.assertTrue(Equipamento.objects.filter(pk=self.e.pk).exists())

    def test_validacoes_api(self):
        self.assertEqual(self.post("api_posicao", {"pavimento": self.pav.pk, "x": 500, "y": 1}, self.e.pk).status_code, 400)
        self.assertEqual(self.client.get(reverse("api_setor_criar")).status_code, 405)
        self.assertEqual(self.client.post(reverse("api_setor_criar"), "{ruim", content_type="application/json").status_code, 400)

    def test_painel_larguras_com_ponto_decimal_e_ordem_dos_andares(self):
        Equipamento.objects.create(asset_id="PLP2", tipo="laptop", status="backup", responsavel="")
        html = self.client.get(reverse("painel")).content.decode()
        self.assertNotRegex(html, r"width:\d+,\d+%")  # vírgula decimal quebraria o CSS
        self.assertLess(html.index("Térreo"), html.index("1º"))

    def test_csrf_exigido(self):
        from django.test import Client
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post(reverse("api_setor_criar"), "{}", content_type="application/json").status_code, 403)

    def test_paginas_carregam(self):
        for nome in ("painel", "planta", "editor", "lista", "importar", "auditoria", "equipamento_novo"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200, nome)
        self.assertEqual(self.client.get(reverse("equipamento_editar", args=[self.e.pk])).status_code, 200)
        r = self.client.get(reverse("exportar"))
        self.assertEqual(r.status_code, 200)
        self.assertIn("spreadsheetml", r["Content-Type"])

    def test_fluxo_importacao_pela_tela(self):
        with open(EXEMPLO, "rb") as f:
            r = self.client.post(reverse("importar"), {"arquivo": f})
        imp = Importacao.objects.get()
        self.assertRedirects(r, reverse("importacao", args=[imp.pk]))
        self.assertEqual(imp.estado, "pendente")
        self.assertEqual(Equipamento.objects.count(), 1)  # nada gravado na pré-visualização
        self.assertContains(self.client.get(reverse("importacao", args=[imp.pk])), "134")
        self.client.post(reverse("importacao_aplicar", args=[imp.pk]))
        imp.refresh_from_db()
        self.assertEqual((imp.estado, imp.linhas), ("aplicada", []))
        self.assertEqual(Equipamento.objects.count(), 135)
        # PLP1 não veio no arquivo e é laptop → ausente
        self.assertTrue(Equipamento.objects.get(asset_id="PLP1").ausente)
        # aplicar de novo é recusado
        self.assertEqual(self.client.post(reverse("importacao_aplicar", args=[imp.pk])).status_code, 404)

    def test_lista_filtros_e_lote(self):
        Equipamento.objects.create(asset_id="PPC1", tipo="tinypc", status="backup")
        r = self.client.get(reverse("lista"), {"tipo": "tinypc"})
        self.assertContains(r, "PPC1")
        self.assertNotContains(r, "PLP1")
        self.client.post(reverse("lote") + "?tipo=tinypc", {"setor": "Novo Setor", "pavimento": self.pav2.pk})
        p = Equipamento.objects.get(asset_id="PPC1")
        self.assertEqual((p.setor.nome, p.pavimento_id), ("Novo Setor", self.pav2.pk))
        self.assertIsNone(Equipamento.objects.get(asset_id="PLP1").setor)


def png_bytes():
    from io import BytesIO
    from PIL import Image
    b = BytesIO(); Image.new("RGB", (400, 120), "white").save(b, "PNG"); return b.getvalue()


@override_settings(MEDIA_ROOT="/tmp/inv_test_media")
class RelatorioTests(TestCase):
    def setUp(self):
        self.pav = Pavimento.objects.create(nome="Térreo", imagem=ContentFile(png_bytes(), "t.png"))
        self.pav2 = Pavimento.objects.create(nome="1º", ordem=1, imagem=ContentFile(png_bytes(), "u.png"))
        self.s = Setor.objects.create(nome="Produção")
        Area.objects.create(setor=self.s, pavimento=self.pav, pontos=QUADRADO)
        Area.objects.create(setor=self.s, pavimento=self.pav, pontos=[[60, 60], [90, 60], [90, 90]])  # 2ª área, mesmo setor
        Equipamento.objects.create(asset_id="PLP1", tipo="laptop", pavimento=self.pav, pos_x=20, pos_y=20, setor=self.s)
        Equipamento.objects.create(asset_id="PIM1", tipo="impressora", status="backup", pavimento=self.pav, pos_x=70, pos_y=70, setor=self.s)
        Equipamento.objects.create(asset_id="PPC1", tipo="tinypc", ausente=True)

    def pdf(self, **q):
        r = self.client.get(reverse("relatorio_pdf"), q)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r["Content-Type"], "application/pdf")
        self.assertTrue(r.content.startswith(b"%PDF"))
        return r

    def test_pdf_variacoes(self):
        self.pdf()
        self.pdf(pinos="0")
        self.pdf(pav=self.pav.pk, lista="1")
        self.assertIn("attachment", self.pdf(baixar="1")["Content-Disposition"])
        self.assertIn("inline", self.pdf()["Content-Disposition"])

    def test_contagens_do_relatorio(self):
        from inventario.relatorio import _linha_contagem
        # [nome, laptop, tiny, impressora, outro, total, operacional, backup, instalar]
        self.assertEqual(_linha_contagem("X", [("laptop", "operacional"), ("impressora", "backup"), ("tinypc", "instalar"), ("outro", "outro")]),
                         ["X", 1, 1, 1, 1, 4, 1, 1, 1])

    def test_pdf_sem_dados_e_sem_plantas(self):
        Equipamento.objects.all().delete()
        Area.objects.all().delete()
        self.pdf()
        Pavimento.objects.all().delete()
        self.pdf(lista="1")

    def test_pagina_do_relatorio(self):
        self.assertContains(self.client.get(reverse("relatorio")), "Exportar relatório em PDF")


@override_settings(MEDIA_ROOT="/tmp/inv_test_media")
class DiaADiaTests(TestCase):
    def setUp(self):
        self.pav = Pavimento.objects.create(nome="Térreo", imagem=ContentFile(png_bytes(), "t.png"))
        self.a = Setor.objects.create(nome="Produção")
        self.b = Setor.objects.create(nome="Lab")
        Area.objects.create(setor=self.a, pavimento=self.pav, pontos=QUADRADO)
        self.e1 = Equipamento.objects.create(asset_id="PLP1", tipo="laptop", serial="SER1", responsavel="Ana", setor=self.a)
        self.e2 = Equipamento.objects.create(asset_id="PLP2", tipo="laptop", serial="SER2", setor=self.a)  # operacional sem responsável
        self.e3 = Equipamento.objects.create(asset_id="PPC1", tipo="tinypc", status="instalar", setor=self.b)

    def post(self, nome, dados, *args):
        return self.client.post(reverse(nome, args=args), json.dumps(dados), content_type="application/json")

    def test_renomear_setor_e_nome_repetido(self):
        self.assertEqual(self.post("api_setor_editar", {"nome": "Produção Líquidos", "cor": "#00ff00"}, self.a.pk).status_code, 200)
        self.a.refresh_from_db()
        self.assertEqual((self.a.nome, self.a.cor), ("Produção Líquidos", "#00ff00"))
        self.assertEqual(self.post("api_setor_editar", {"nome": "lab"}, self.a.pk).status_code, 400)  # já existe (sem diferenciar maiúsculas)
        self.assertEqual(self.post("api_setor_editar", {"nome": "  "}, self.a.pk).status_code, 400)

    def test_mesclar_setores(self):
        r = self.post("api_setor_mesclar", {"destino": self.b.pk}, self.a.pk)
        self.assertEqual(r.json()["equipamentos_movidos"], 2)
        self.assertFalse(Setor.objects.filter(pk=self.a.pk).exists())
        self.assertEqual(Equipamento.objects.filter(setor=self.b).count(), 3)
        self.assertEqual(Area.objects.get().setor_id, self.b.pk)  # a área da planta também passou
        self.assertEqual(self.post("api_setor_mesclar", {"destino": self.b.pk}, self.b.pk).status_code, 400)

    def test_excluir_setor_transferindo_ou_nao(self):
        self.post("api_setor_excluir", {"transferir_para": self.b.pk}, self.a.pk)
        self.assertEqual(Equipamento.objects.filter(setor=self.b).count(), 3)
        self.post("api_setor_excluir", {}, self.b.pk)
        self.assertEqual(Equipamento.objects.filter(setor__isnull=True).count(), 3)  # ficaram sem setor, nenhum apagado
        self.assertEqual(Equipamento.objects.count(), 3)

    def test_nota_e_historico_da_edicao(self):
        self.assertEqual(self.post("api_nota", {"texto": "teclado quebrado"}, self.e1.pk).status_code, 200)
        self.assertEqual(self.post("api_nota", {"texto": " "}, self.e1.pk).status_code, 400)
        r = self.client.post(reverse("equipamento_editar", args=[self.e1.pk]), {
            "asset_id": "PLP1", "tipo": "laptop", "status": "backup", "responsavel": "Bia", "serial": "SER1", "fornecedor": "", "setor": self.b.pk, "pavimento": "", "obs": ""})
        self.assertEqual(r.status_code, 302)
        det = Historico.objects.filter(asset_id="PLP1", evento="alterado").first().detalhe
        self.assertIn("Responsável: Ana → Bia", det)
        self.assertIn("Status: Operacional → Backup", det)
        self.assertIn("Setor: Produção → Lab", det)
        pagina = self.client.get(reverse("equipamento_editar", args=[self.e1.pk])).content.decode()
        self.assertIn("teclado quebrado", pagina)

    def test_conferencia_por_codigo_e_em_massa(self):
        self.assertEqual(self.post("api_conferir", {"codigo": "plp1"}).json()["conferidos"][0]["asset_id"], "PLP1")  # sem diferenciar maiúsculas
        self.assertEqual(self.post("api_conferir", {"codigo": "SER2"}).json()["conferidos"][0]["asset_id"], "PLP2")  # por nº de série
        self.assertEqual(self.post("api_conferir", {"codigo": "NAOEXISTE"}).status_code, 400)
        self.assertEqual(self.post("api_conferir", {"ids": [self.e3.pk]}).status_code, 200)
        self.assertEqual(self.post("api_conferir", {"ids": []}).status_code, 400)
        self.assertEqual(Equipamento.objects.filter(ultima_conferencia__isnull=False).count(), 3)
        self.assertEqual(Historico.objects.filter(evento="conferencia").count(), 3)
        r = self.client.get(reverse("conferencia"), {"setor": self.a.pk})
        self.assertContains(r, "2</b> de <b>2")

    def test_pendencias_na_lista_e_no_painel(self):
        r = self.client.get(reverse("lista"), {"p": "sem_responsavel"})
        self.assertContains(r, "PLP2"); self.assertNotContains(r, "PLP1")
        self.assertContains(self.client.get(reverse("lista"), {"p": "a_instalar"}), "PPC1")
        self.assertEqual(self.client.get(reverse("lista"), {"p": "conferencia"}).context["total"], 3)
        self.post("api_conferir", {"ids": [self.e1.pk, self.e2.pk, self.e3.pk]})
        self.assertEqual(self.client.get(reverse("lista"), {"p": "conferencia"}).context["total"], 0)
        self.assertContains(self.client.get(reverse("painel")), "Pendências do dia a dia")

    def test_busca_rapida(self):
        r = self.client.get(reverse("buscar"), {"q": "ser2"})
        self.assertRedirects(r, reverse("equipamento_editar", args=[self.e2.pk]))
        r = self.client.get(reverse("buscar"), {"q": "PLP"})  # parcial → lista filtrada
        self.assertEqual(r.status_code, 302); self.assertIn("/equipamentos/?q=PLP", r["Location"])

    def test_etiquetas_e_paginas_novas(self):
        for params in ({"ids": f"{self.e1.pk},{self.e2.pk}"}, {"tipo": "laptop"}, {"ids": "999"}):
            r = self.client.get(reverse("etiquetas"), params)
            self.assertEqual(r.status_code, 200); self.assertTrue(r.content.startswith(b"%PDF"))
        for nome in ("conferencia", "setores_gerenciar"):
            self.assertEqual(self.client.get(reverse(nome)).status_code, 200)


@override_settings(MEDIA_ROOT="/tmp/inv_test_media")
class ComandosTests(TestCase):
    def test_comandos_de_carga(self):
        from io import StringIO
        call_command("carregar_exemplo", "--partes", stdout=StringIO())
        call_command("carregar_exemplo", "--partes", stdout=StringIO())  # idempotente
        self.assertEqual(Pavimento.objects.count(), 3)
        self.assertEqual(Equipamento.objects.count(), 134)
        self.assertEqual(Area.objects.filter(setor__nome="Parte A").count(), 3)  # uma por pavimento
        self.assertEqual(Area.objects.count(), 24)
