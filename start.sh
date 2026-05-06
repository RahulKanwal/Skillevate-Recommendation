#!/bin/bash

set -e

echo "=== Skillevate Recommendation API - Setup & Start ==="

# ── 1. Check Python ────────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 is not installed. Please install Python 3.10 or higher."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "✓ Python $PYTHON_VERSION detected"

# ── 2. Create virtual environment if it doesn't exist ─────────────────────────
if [ ! -d "venv" ]; then
    echo "→ Creating virtual environment..."
    python3 -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# ── 3. Activate virtual environment ───────────────────────────────────────────
echo "→ Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"

# ── 4. Install / upgrade dependencies ─────────────────────────────────────────
echo "→ Installing dependencies..."
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
echo "✓ Dependencies installed"

# ── 5. Check .env file ────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo ""
    echo "WARNING: .env file not found."
    echo "  Copying .env.example to .env — please fill in your API keys before using the app."
    cp .env.example .env
    echo ""
fi

# ── 6. Fix macOS SSL certificates (needed for MongoDB Atlas) ──────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
    CERT_SCRIPT=$(ls /Applications/Python\ */Install\ Certificates.command 2>/dev/null | tail -1)
    if [ -n "$CERT_SCRIPT" ]; then
        echo "→ Installing macOS SSL certificates..."
        bash "$CERT_SCRIPT" &>/dev/null || true
        echo "✓ SSL certificates installed"
    fi
fi

# ── 7. Start the server ───────────────────────────────────────────────────────
echo ""
echo "=== Starting Skillevate Recommendation API ==="
echo "   URL:      http://localhost:8000"
echo "   Docs:     http://localhost:8000/docs"
echo "   Health:   http://localhost:8000/health"
echo ""

uvicorn main:app --reload --host 0.0.0.0 --port 8000
