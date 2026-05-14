#!/usr/bin/env bash
# Pipeline de faturamento hospitalar
#
# Cron para execução automática toda segunda-feira às 06h30:
# 30 6 * * 1 /bin/bash /caminho/para/o/projeto/run.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="$SCRIPT_DIR/.venv/bin/python"

if [ ! -f "$PYTHON" ]; then
    echo "ERRO: Ambiente virtual nao encontrado."
    echo "Execute: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Logging, tratamento de erros e exit code sao responsabilidade do main.py
exec "$PYTHON" "$SCRIPT_DIR/main.py"
