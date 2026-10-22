@echo off
rem Windows: prepara o ambiente na 1a vez e sobe o servidor em http://127.0.0.1:8000
cd /d "%~dp0"
if not exist .venv ( py -3 -m venv .venv || python -m venv .venv )
call .venv\Scripts\activate.bat
pip install -q -r requirements.txt
python manage.py migrate --noinput
python manage.py carregar_plantas
echo Abrindo em http://127.0.0.1:8000  (Ctrl+C para parar)
start "" http://127.0.0.1:8000
python manage.py runserver 127.0.0.1:8000
