#!/usr/bin/env bash
# Inicia o bot em modo PAPER no Mac/Linux:  bash iniciar_paper.sh   (Ctrl+C para parar)
set -e
cd "$(dirname "$0")"
[ -d .venv ] || python3 -m venv .venv
. .venv/bin/activate
python -m pip install -q --upgrade "pip>=26.2.2" certifi   # versões antigas confiam em certificados comprometidos
python -m pip install -q -r requirements.txt
if [ ! -f .env ]; then
  cp .env.example .env && chmod 600 .env
  echo "Arquivo .env criado. Preencha o Telegram (nano .env) e rode de novo."
  exit 0
fi
python -m bot paper
