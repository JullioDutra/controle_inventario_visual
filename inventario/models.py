from django.db import models


class Pavimento(models.Model):
    """Um andar/planta. A imagem é a planta de fundo onde setores e equipamentos são posicionados."""
    nome = models.CharField(max_length=80, unique=True)
    ordem = models.PositiveSmallIntegerField(default=0)
    imagem = models.FileField(upload_to="plantas/")

    class Meta:
        ordering = ["ordem", "nome"]

    def __str__(self):
        return self.nome


class Setor(models.Model):
    """Setor/departamento. Pode ter várias áreas desenhadas (inclusive em andares diferentes)."""
    nome = models.CharField(max_length=80, unique=True)
    cor = models.CharField(max_length=7, default="#1f6feb")
    descricao = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["nome"]
        verbose_name_plural = "setores"

    def __str__(self):
        return self.nome


class Area(models.Model):
    """Polígono de um setor numa planta. `pontos` = [[x, y], ...] em % da largura/altura da imagem (0–100)."""
    setor = models.ForeignKey(Setor, on_delete=models.CASCADE, related_name="areas")
    pavimento = models.ForeignKey(Pavimento, on_delete=models.CASCADE, related_name="areas")
    pontos = models.JSONField(default=list)

    def __str__(self):
        return f"{self.setor} @ {self.pavimento}"


class Equipamento(models.Model):
    class Tipo(models.TextChoices):
        LAPTOP = "laptop", "Laptop"
        TINYPC = "tinypc", "Tiny PC"
        IMPRESSORA = "impressora", "Impressora"
        OUTRO = "outro", "Outro"

    class Status(models.TextChoices):
        OPERACIONAL = "operacional", "Operacional"
        BACKUP = "backup", "Backup"
        INSTALAR = "instalar", "A instalar"
        OUTRO = "outro", "Outro"

    asset_id = models.CharField("Asset ID", max_length=60, unique=True)
    tipo = models.CharField(max_length=20, choices=Tipo.choices, default=Tipo.OUTRO)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OPERACIONAL)
    serial = models.CharField("Nº de série", max_length=80, blank=True)
    fornecedor = models.CharField(max_length=120, blank=True)
    responsavel = models.CharField("Responsável", max_length=120, blank=True)
    obs = models.TextField("Obs", blank=True)
    # Campos locais: nunca sobrescritos pela importação do TopDesk.
    setor = models.ForeignKey(Setor, null=True, blank=True, on_delete=models.SET_NULL, related_name="equipamentos")
    pavimento = models.ForeignKey(Pavimento, null=True, blank=True, on_delete=models.SET_NULL, related_name="equipamentos")
    pos_x = models.FloatField(null=True, blank=True)
    pos_y = models.FloatField(null=True, blank=True)
    # Colunas extras da planilha que o sistema não conhece (modelo, marca, ...).
    extras = models.JSONField(default=dict, blank=True)
    ausente = models.BooleanField("Ausente no último TopDesk", default=False)
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_id"]

    def __str__(self):
        return self.asset_id

    @property
    def posicionado(self):
        return self.pavimento_id is not None and self.pos_x is not None and self.pos_y is not None


class Historico(models.Model):
    class Evento(models.TextChoices):
        NOVO = "novo", "Novo"
        ALTERADO = "alterado", "Alterado"
        AUSENTE = "ausente", "Ausente"
        POSICAO = "posicao", "Posição"
        SETOR = "setor", "Setor/planta"

    asset_id = models.CharField(max_length=60, blank=True, db_index=True)
    evento = models.CharField(max_length=20, choices=Evento.choices)
    detalhe = models.TextField()
    origem = models.CharField(max_length=200, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em", "-id"]
        verbose_name_plural = "histórico"


class Importacao(models.Model):
    class Estado(models.TextChoices):
        PENDENTE = "pendente", "Pré-visualização"
        APLICADA = "aplicada", "Aplicada"
        CANCELADA = "cancelada", "Cancelada"

    arquivo = models.CharField(max_length=200)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDENTE)
    linhas = models.JSONField(default=list)      # linhas normalizadas lidas do arquivo
    resumo = models.JSONField(default=dict)      # contagens
    mudancas = models.JSONField(default=list)    # [{id, evento, detalhe}]
    abas = models.JSONField(default=list)        # [{nome, n}]
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name_plural = "importações"
