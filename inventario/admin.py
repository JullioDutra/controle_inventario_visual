from django.contrib import admin

from .models import Area, Equipamento, Historico, Importacao, Pavimento, Setor


@admin.register(Pavimento)
class PavimentoAdmin(admin.ModelAdmin):
    list_display = ("nome", "ordem", "imagem")


class AreaInline(admin.TabularInline):
    model = Area
    extra = 0


@admin.register(Setor)
class SetorAdmin(admin.ModelAdmin):
    list_display = ("nome", "cor")
    search_fields = ("nome",)
    inlines = [AreaInline]


@admin.register(Equipamento)
class EquipamentoAdmin(admin.ModelAdmin):
    list_display = ("asset_id", "tipo", "status", "responsavel", "setor", "pavimento", "ausente")
    list_filter = ("tipo", "status", "setor", "pavimento", "ausente")
    search_fields = ("asset_id", "serial", "responsavel", "obs")


admin.site.register(Historico)
admin.site.register(Importacao)
