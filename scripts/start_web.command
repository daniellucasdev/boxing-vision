#!/bin/bash
# Boxing Vision — inicia a interface web (duplo-clique no Finder)
cd "$(dirname "$0")/.."
source .venv/bin/activate
echo "🥊 Boxing Vision — http://127.0.0.1:5000  (Ctrl+C para sair)"
open http://127.0.0.1:5000 2>/dev/null &
python src/webapp.py "$@"
