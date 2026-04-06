#!/bin/bash
# QA Form Application - Setup & Validation Checklist

echo "================================"
echo "QA FORM APPLICATION SETUP CHECK"
echo "================================"
echo ""

# Check Python installation
echo "✓ Checking Python..."
python --version
echo ""

# Check if dependencies are installed
echo "✓ Checking dependencies..."
python -c "import fastapi; print('  FastAPI OK')"
python -c "import sqlalchemy; print('  SQLAlchemy OK')"
python -c "import reportlab; print('  ReportLab OK')"
python -c "import multipart; print('  python-multipart OK')"
python -c "import PIL; print('  Pillow OK')"
python -c "import qrcode; print('  qrcode OK')"
echo ""

# Check .env file
echo "✓ Checking configuration..."
if [ -f "/home/guru/qa_app/.env" ]; then
    echo "  .env file exists"
    grep -q "WRITE_SQLSERVER_DATABASE=CNtempGuru" /home/guru/qa_app/.env && echo "  Write DB config OK"
    grep -q "METADATA_SQLSERVER_DATABASE=CrowsNest" /home/guru/qa_app/.env && echo "  Metadata DB config OK"
else
    echo "  WARNING: .env file not found"
fi
echo ""

# Check folder structure
echo "✓ Checking folder structure..."
[ -d "/home/guru/qa_app/backend" ] && echo "  backend/ directory OK"
[ -d "/home/guru/qa_app/frontend" ] && echo "  frontend/ directory OK"
[ -f "/home/guru/qa_app/backend/main.py" ] && echo "  main.py OK"
[ -f "/home/guru/qa_app/backend/db.py" ] && echo "  db.py OK"
[ -f "/home/guru/qa_app/backend/pdf_generator.py" ] && echo "  pdf_generator.py OK"
[ -f "/home/guru/qa_app/frontend/qa.html" ] && echo "  qa.html OK"
echo ""

# Check SQL schema
echo "✓ Checking SQL schema..."
if [ -f "/home/guru/qa_app/qa_submissions_schema.sql" ]; then
    echo "  Schema file exists - run with:"
    echo "  sqlcmd -S MAPLE\\\\SQLEXPRESS -U CNtempG -P Temp@224 -d CNtempGuru -i qa_submissions_schema.sql"
else
    echo "  WARNING: Schema file not found"
fi
echo ""

echo "================================"
echo "SETUP CHECKLIST COMPLETE"
echo "================================"
echo ""
echo "NEXT STEPS:"
echo "1. Execute SQL schema to create QA_Submissions table"
echo "2. Install dependencies: pip install -r requirements.txt"
echo "3. Start server: uvicorn backend.main:app --reload"
echo "4. Open browser: http://localhost:8000/qa"
echo ""
