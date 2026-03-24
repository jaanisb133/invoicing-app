#!/bin/bash
# V-Rēķini Offline Launcher (macOS)

cd "$(dirname "$0")"

echo ""
echo "  ╔══════════════════════════════════════════╗"
echo "  ║        V-Rēķini — Offline režīms          ║"
echo "  ╚══════════════════════════════════════════╝"
echo ""

# Check if Python 3 is installed
if command -v python3 &>/dev/null; then
    PYTHON=python3
elif command -v python &>/dev/null; then
    PYTHON=python
else
    echo "  [!] Python 3 nav atrasts."
    echo "      Lejupielādējiet no: https://www.python.org/downloads/"
    echo ""
    read -p "  Nospiediet Enter lai aizvērtu..."
    exit 1
fi

# Install dependencies if needed
$PYTHON -c "import fastapi" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "  Instalē nepieciešamās bibliotēkas..."
    $PYTHON -m pip install -r requirements.txt --quiet
    if [ $? -ne 0 ]; then
        echo "  [!] Kļūda instalējot bibliotēkas."
        read -p "  Nospiediet Enter lai aizvērtu..."
        exit 1
    fi
    echo "  Bibliotēkas instalētas veiksmīgi."
    echo ""
fi

# Launch the app
$PYTHON run_offline.py
