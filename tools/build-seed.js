// Gera data/seed.js a partir de uma exportação do TopDesk: node tools/build-seed.js data/topdesk-exemplo.xlsx
const XLSX = require('../vendor/xlsx.full.min.js');
const Core = require('../data/core.js');
const fs = require('fs');
const wb = XLSX.read(fs.readFileSync(process.argv[2] || 'data/topdesk-exemplo.xlsx'));
let novos = [];
for (const n of wb.SheetNames) novos = novos.concat(Core.linhasParaAtivos(XLSX.utils.sheet_to_json(wb.Sheets[n], { defval: '' }), n));
const ativos = [], hoje = new Date().toISOString();
Core.aplicarImportacao(ativos, novos, hoje, 'seed');
fs.writeFileSync('data/seed.js', 'window.SEED_ATIVOS = ' + JSON.stringify(ativos) + ';\n');
console.log(ativos.length, 'ativos');
