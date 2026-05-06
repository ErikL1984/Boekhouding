#!/bin/bash
# ============================================================
# Privé Boekhoudprogramma — Start script
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Virtual environment activeren
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Standaard instellingen (overschrijfbaar via environment variabelen)
export PORT=${PORT:-5000}
export DEBUG=${DEBUG:-false}
export DB_PATH=${DB_PATH:-"$(pwd)/data/boekhouding.db"}

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║        Privé Boekhoudprogramma               ║"
echo "╚══════════════════════════════════════════════╝"
echo ""
echo "  Database:  $DB_PATH"
echo "  Adres:     http://0.0.0.0:$PORT"
echo "  Debug:     $DEBUG"
echo ""
echo "  Open in browser: http://localhost:$PORT"
echo "  Stoppen: Ctrl+C"
echo ""

cd backend
python3 app.py
