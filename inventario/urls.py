from django.urls import path

from . import api, views

urlpatterns = [
    path("", views.painel, name="painel"),
    path("planta/", views.planta, name="planta"),
    path("setores/", views.editor, name="editor"),
    path("equipamentos/", views.lista, name="lista"),
    path("equipamentos/novo/", views.equipamento_form, name="equipamento_novo"),
    path("equipamentos/lote/", views.lote, name="lote"),
    path("equipamentos/exportar/", views.exportar, name="exportar"),
    path("equipamentos/<int:pk>/", views.equipamento_form, name="equipamento_editar"),
    path("equipamentos/<int:pk>/excluir/", views.equipamento_excluir, name="equipamento_excluir"),
    path("importar/", views.importar, name="importar"),
    path("importar/<int:pk>/", views.importacao_detalhe, name="importacao"),
    path("importar/<int:pk>/aplicar/", views.importacao_aplicar, name="importacao_aplicar"),
    path("importar/<int:pk>/cancelar/", views.importacao_cancelar, name="importacao_cancelar"),
    path("auditoria/", views.auditoria, name="auditoria"),
    # API JSON usada pelas telas Planta e Setores
    path("api/equipamentos/<int:pk>/posicao/", api.posicao, name="api_posicao"),
    path("api/setores/", api.setor_criar, name="api_setor_criar"),
    path("api/setores/<int:pk>/", api.setor_editar, name="api_setor_editar"),
    path("api/setores/<int:pk>/excluir/", api.setor_excluir, name="api_setor_excluir"),
    path("api/areas/", api.area_criar, name="api_area_criar"),
    path("api/areas/<int:pk>/", api.area_editar, name="api_area_editar"),
    path("api/areas/<int:pk>/excluir/", api.area_excluir, name="api_area_excluir"),
    path("api/reatribuir/", api.reatribuir, name="api_reatribuir"),
]
