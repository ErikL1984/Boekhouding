#!/bin/bash
# ============================================================
# Privé Boekhoudprogramma — Setup & Start script
# Gebruik: bash setup.sh
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        Privé Boekhoudprogramma Setup         ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Python controleren ──────────────────────────────────────
if ! command -v python3 &> /dev/null; then
    echo "❌ Python3 niet gevonden. Installeer Python 3.9+ eerst."
    exit 1
fi
PYTHON=$(command -v python3)
echo "✓ Python: $($PYTHON --version)"

# ── Virtual environment ──────────────────────────────────────
if [ ! -d "venv" ]; then
    echo "→ Virtuele omgeving aanmaken..."
    $PYTHON -m venv venv
fi
source venv/bin/activate
echo "✓ Virtuele omgeving actief"

# ── Dependencies ─────────────────────────────────────────────
echo "→ Dependencies installeren..."
pip install flask --quiet
echo "✓ Flask geïnstalleerd"

# ── Data directory ───────────────────────────────────────────
mkdir -p data
echo "✓ Data directory aangemaakt"

# ── Database initialiseren ───────────────────────────────────
echo "→ Database initialiseren..."
cd backend
python3 -c "
import sys, os
sys.path.insert(0, '.')
from db import init_db
init_db()
print('  Database schema aangemaakt')
"

# ── Seed uitvoeren ───────────────────────────────────────────
echo "→ Standaard grootboeken aanmaken..."
cd ../database
python3 seed.py
cd ..

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║              Setup voltooid! ✅               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Standaard inloggegevens:"
echo "  Gebruikersnaam: beheerder"
echo "  Wachtwoord:     Wijzig_dit_wachtwoord!"
echo ""
echo "  ⚠️  Wijzig het wachtwoord direct na eerste login!"
echo ""
echo "  Starten: bash start.sh"
echo ""
