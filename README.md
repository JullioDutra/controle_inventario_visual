# Inventário Visual FSBR (Fagron)

App web estático (sem build, sem servidor) para gestão visual dos ativos de TI da unidade FSBR.
Abra `index.html` no navegador. Os dados ficam no `localStorage`; use **Importar → Baixar backup** para portabilidade.

## Funcionalidades
- **Painel**: totais, Laptop / Tiny PC / Impressora, matriz tipo × status (Operacional · Backup · A instalar), equipamentos por setor e por andar/parte. Tudo é clicável e filtra a lista.
- **Planta**: 3 pavimentos (Térreo, 1º, 2º) a partir dos PDFs de arquitetura, com as Partes A–H clicáveis e contagem por parte. Selecione um equipamento e clique no mapa para posicioná-lo (andar/parte são deduzidos); pinos são arrastáveis.
- **Equipamentos**: busca, filtros, ordenação, edição, cadastro manual, atribuição em lote (setor/andar/parte dos itens filtrados) e exportação para Excel.
- **Importar TopDesk**: arraste o `.xlsx` (cada aba = um tipo: `Laptop`, `PC - Tiny PC`, `Impressora`). Chave = **Asset ID**. Pré-visualização antes de aplicar: novos, alterados, sem mudança e **ausentes**. Campos locais (setor, andar, parte, posição) nunca são sobrescritos. O setor inicial é inferido do campo *Obs* (ex.: "KIOSK PRODUÇÃO" → Produção).
- **Histórico & qualidade**: trilha de auditoria de cada mudança (qual arquivo, antes → depois) e verificações: laptop operacional sem responsável, backup com responsável, série ausente/duplicada, pessoa com 2+ laptops, ativo ausente no TopDesk, sem localização.

## Estrutura
`index.html`, `app.js` (UI), `data/core.js` (regras puras, testáveis em Node), `data/seed.js` (carga inicial gerada da planilha), `plans/` (plantas PNG), `vendor/xlsx.full.min.js` (SheetJS 0.18.5).
Regenerar a carga inicial: `node tools/build-seed.js caminho/export.xlsx`.

## Sobre o REA (morluto/rea)
O REA é um MCP de **engenharia reversa** (binários, apps, runtime). Não tem função de gestão de ativos, então não foi integrado como dependência. Dele foram aproveitadas apenas ideias de método: achados sempre com evidência (aba de qualidade cita o ID e o motivo), trilha de proveniência de cada mudança (histórico com arquivo de origem) e verificação antes de aplicar (pré-visualização da importação).

## Limitações / próximos passos
- Zonas das plantas são retângulos aproximados das Partes A–H; salas individuais podem ser refinadas.
- O arquivo de exemplo não tem aba de impressoras; o app já a reconhece quando existir.
- Dados são por navegador; para uso multiusuário, o próximo passo é um backend (ex.: SQLite/API).
