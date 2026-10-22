# Inventário Visual FSBR (Fagron) — Django

Gestão visual de ativos de TI da unidade FSBR: painel por tipo/status/setor, plantas dos 3 pavimentos com **setores desenhados por você**, equipamentos posicionados no **ponto exato** e importação da planilha do TopDesk. Roda localmente (SQLite), sem Docker.

## Como executar no seu PC
Requer **Python 3.10+**.

- **Windows:** dê duplo clique em `rodar.bat`
- **Linux/macOS:** `./rodar.sh`

O script cria o ambiente virtual, instala as dependências, cria o banco, cadastra as plantas e abre **http://127.0.0.1:8000**.
Para ver dados de exemplo (planilha enviada + Partes A–H como setores de partida):
`python manage.py carregar_exemplo --partes` (opcional; dentro do ambiente `.venv`).
Admin do Django (opcional): `python manage.py createsuperuser` → `/admin/`.

## Abas
| Aba | O que faz |
|---|---|
| **Painel** | Totais, Laptop / Tiny PC / Impressora, tipo × status (Operacional · Backup · A instalar), por setor e por andar. Tudo clicável. |
| **Planta** | Escolha um equipamento e **clique no ponto exato** da planta; arraste o pino para ajustar; **setas** (Shift = passo maior) para ajuste fino; zoom. Filtros por tipo e status; clique num setor para ver só os equipamentos dele. Ao soltar o pino dentro de uma área, o equipamento **herda o setor** dela. |
| **Setores na planta** | Crie o setor (nome/cor), **desenhe a área** (retângulo ou polígono) sobre a planta, **mova** arrastando, **remodele** arrastando os pontos, crie vértice nos pontos tracejados, duplo clique remove vértice, `Delete` exclui. Um setor pode ter várias áreas (inclusive em andares diferentes). Botão *Reatribuir setor pela posição* recalcula os equipamentos. |
| **Equipamentos** | Busca, filtros, edição, cadastro manual, atribuição em lote (setor/andar dos itens filtrados), exportação para Excel. |
| **Importar TopDesk** | Envie `.xlsx`/`.csv` → **pré-visualização** (novos, alterados, sem mudança, ausentes) → aplicar. |
| **Relatório PDF** | Gera um PDF A4 paisagem: página de **resumo** (total, tipo × status, por andar, por setor) e **uma página por andar** com a planta, as áreas dos setores, a quantidade de ativos por setor, os pinos dos equipamentos e a tabela de contagens. Opções: escolher andares, ocultar pinos, anexar lista de equipamentos por setor; abrir no navegador ou baixar. |
| **Histórico & qualidade** | Trilha de auditoria (quem/onde/antes→depois, com arquivo de origem) e verificações de qualidade dos dados. |

## Regras da importação (a planilha é o “atualizador de chaves”)
- Chave = **Asset ID**. Existente → atualiza; novo → cria; sumiu do arquivo → marca **ausente** (nunca apaga).
- Cada aba é um tipo (`Laptop`, `PC - Tiny PC`, `Impressora`…), ou use uma coluna `Tipo`; senão deduz pelo prefixo do ID (PLP, PPC, PIM).
- Só atualiza as colunas **presentes** no arquivo (aba sem Fornecedor não apaga o fornecedor).
- Colunas que o sistema não conhece (modelo, marca, localização…) ficam em *colunas extras* do equipamento — a planilha completa não perde dados.
- **Setor, andar e posição na planta nunca são sobrescritos** pela importação (o setor só é preenchido se estiver vazio, vindo da coluna `Setor` ou inferido do campo Obs).
- Colunas reconhecidas: Asset ID, Obs, Serial Number, Status, Supplier/Fornecedor, Assignments - Persons/Responsável, Tipo, Setor/Departamento.

## Estrutura
```
config/            settings, urls
inventario/
  models.py        Pavimento, Setor, Area(polígono), Equipamento, Historico, Importacao
  importador.py    leitura/aplicação do TopDesk       qualidade.py   verificações
  geometria.py     ponto-em-polígono, validação       api.py         endpoints JSON (CSRF)
  views.py / forms.py / urls.py / admin.py
  templates/ static/ (planta.js, editor.js, comum.js)
  seed/            plantas PNG + planilha de exemplo
  management/commands/  carregar_plantas, carregar_exemplo
  tests/           20 testes
  relatorio.py     geração do PDF (reportlab)
```
Testes: `python manage.py test`.
Backup: copie `db.sqlite3` e a pasta `media/`.

## Sobre o REA (morluto/rea)
É uma ferramenta de engenharia reversa; não há função de gestão de ativos nela, então não é dependência. Foram adotadas só ideias de método: achados com evidência (qualidade cita ID e motivo), proveniência de cada mudança (histórico com arquivo de origem) e verificação antes de aplicar (pré-visualização).

## Limitações
- Uso local/monousuário: sem login (o Admin exige superusuário). Para uso em rede, defina `DJANGO_ALLOWED_HOSTS`, `DJANGO_DEBUG=0` e coloque atrás de um servidor adequado.
- As plantas são imagens (PNG) geradas dos PDFs; novas plantas podem ser cadastradas no Admin (Pavimentos).
