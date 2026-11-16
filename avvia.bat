@echo off
rem Vertex Studio - avvio su Windows (doppio clic)
cd /d "%~dp0"

if exist .venv\Scripts\python.exe goto installa

set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY (
  echo Python non trovato. Installa Python 3.10 o superiore da https://www.python.org/downloads/
  echo Durante l'installazione spunta "Add python.exe to PATH".
  pause
  exit /b 1
)
%PY% -c "import sys; sys.exit(sys.version_info < (3, 10))" || (
  echo Serve Python 3.10 o superiore.
  pause
  exit /b 1
)
echo Prima installazione, ci vuole circa un minuto...
%PY% -m venv .venv || (pause & exit /b 1)

:installa
.venv\Scripts\python -m pip install -q --disable-pip-version-check -r requirements.txt || (
  echo Installazione delle librerie non riuscita.
  pause
  exit /b 1
)
.venv\Scripts\python -m app
pause
