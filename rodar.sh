#!/usr/bin/env bash
# Linux/macOS: prepara o ambiente na 1ª vez e sobe o servidor em http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
pip install -q -r requirements.txt
python manage.py migrate --noinput
python manage.py carregar_plantas
echo ">> Abrindo em http://127.0.0.1:8000  (Ctrl+C para parar)"
python manage.py runserver 127.0.0.1:8000
