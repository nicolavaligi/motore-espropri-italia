#!/bin/zsh
set -euo pipefail
export PATH="/Users/houdinick/.local/bin:/opt/homebrew/bin:$PATH"

cd /Users/houdinick/motore-espropri-italia || exit 1

# 1. Esegui la scansione automatica dei bollettini regionali (Fase 4 - Art. 16 DPR 327/2001)
uv run python collect_public_records.py --manifest config/fonti_pubbliche.json >> crawler.log 2>&1

# 2. Invia l'email settimanale di sintesi + CSV particelle catastali a n.valig@gmail.com
uv run python email_notifier.py >> email.log 2>&1
