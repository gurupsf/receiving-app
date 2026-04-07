#!/bin/bash
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$APP_DIR/env/bin/python}"

if [ ! -x "$PYTHON_BIN" ]; then
    PYTHON_BIN="python"
fi

echo "================================"
echo "RECEIVING APP SETUP CHECK"
echo "================================"
echo ""

echo "Checking Python..."
"$PYTHON_BIN" --version
echo ""

echo "Checking dependencies..."
"$PYTHON_BIN" -c "import fastapi; print('  FastAPI OK')"
"$PYTHON_BIN" -c "import sqlalchemy; print('  SQLAlchemy OK')"
"$PYTHON_BIN" -c "import reportlab; print('  ReportLab OK')"
"$PYTHON_BIN" -c "import multipart; print('  python-multipart OK')"
"$PYTHON_BIN" -c "import PIL; print('  Pillow OK')"
"$PYTHON_BIN" -c "import qrcode; print('  qrcode OK')"
echo ""

echo "Checking configuration..."
if [ -f "$APP_DIR/.env" ]; then
    echo "  .env file exists"
    grep -q "^WRITE_SQLSERVER_DATABASE=" "$APP_DIR/.env" && echo "  Write DB config present"
    grep -q "^METADATA_SQLSERVER_DATABASE=" "$APP_DIR/.env" && echo "  Metadata DB config present"
else
    echo "  WARNING: .env file not found"
fi
echo ""

echo "Checking folder structure..."
[ -d "$APP_DIR/backend" ] && echo "  backend/ directory OK"
[ -d "$APP_DIR/frontend" ] && echo "  frontend/ directory OK"
[ -f "$APP_DIR/backend/main.py" ] && echo "  main.py OK"
[ -f "$APP_DIR/backend/db.py" ] && echo "  db.py OK"
[ -f "$APP_DIR/backend/pdf_generator.py" ] && echo "  pdf_generator.py OK"
[ -f "$APP_DIR/frontend/receiving.html" ] && echo "  receiving.html OK"
[ -f "$APP_DIR/frontend/receiving_data.html" ] && echo "  receiving_data.html OK"
[ -f "$APP_DIR/frontend/supplier_dashboard.html" ] && echo "  supplier_dashboard.html OK"
echo ""

echo "Checking SQL schema..."
if [ -f "$APP_DIR/receiving_schema.sql" ]; then
    echo "  Schema file exists - run with:"
    echo "  sqlcmd -S YOUR_SERVER -d YOUR_DATABASE -i receiving_schema.sql"
else
    echo "  WARNING: Schema file not found"
fi
echo ""

echo "================================"
echo "SETUP CHECK COMPLETE"
echo "================================"
echo ""
echo "NEXT STEPS:"
echo "1. Execute receiving_schema.sql and receiving_schema_update.sql"
echo "2. Install dependencies: pip install -r requirements.txt"
echo "3. Start server: uvicorn backend.main:app --reload"
echo "4. Open browser: http://localhost:8000/receiving"
echo "5. Use run_with_ssl.sh for local HTTPS"
echo ""
