#!/bin/bash
# Vertex Studio - avvio su macOS (doppio clic) o Linux (./avvia.command)
cd "$(dirname "$0")" || exit 1

# Cartella copiata da Windows: quella .venv non funziona su Mac/Linux, la si ricrea.
if [ -d .venv ] && [ ! -x .venv/bin/python ]; then
  echo "Trovato un ambiente creato su un altro sistema: lo ricreo per questo computer..."
  rm -rf .venv
fi

if [ ! -x .venv/bin/python ]; then
  PY="$(command -v python3)"
  if [ -z "$PY" ]; then
    echo "Python 3 non trovato. Installalo da https://www.python.org/downloads/"
    read -r -p "Premi Invio per chiudere"; exit 1
  fi
  if ! "$PY" -c 'import sys; sys.exit(sys.version_info < (3, 10))'; then
    echo "Serve Python 3.10 o superiore (trovato: $("$PY" --version)). Installalo da https://www.python.org/downloads/"
    read -r -p "Premi Invio per chiudere"; exit 1
  fi
  echo "Prima installazione, ci vuole circa un minuto..."
  "$PY" -m venv .venv || { read -r -p "Premi Invio per chiudere"; exit 1; }
fi

.venv/bin/python -m pip install -q --disable-pip-version-check -r requirements.txt \
  || { echo "Installazione delle librerie non riuscita."; read -r -p "Premi Invio per chiudere"; exit 1; }
exec .venv/bin/python -m app
