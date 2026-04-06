#!/bin/bash

# QA Form Application - HTTPS Startup Script
# This script runs the FastAPI server with self-signed SSL certificate

cd /home/guru/qa_app

# Activate virtual environment
source /home/guru/qa_app/env/bin/activate

echo "╔════════════════════════════════════════════════════════════╗"
echo "║       QA Form Application - HTTPS Server                   ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo ""
echo "🔒 Starting with SSL/TLS (Self-signed certificate)"
echo ""

# Get IP address
IP=$(hostname -I | awk '{print $1}')
PORT=8000

echo "📍 Server Address: https://${IP}:${PORT}/qa"
echo "⚠️  Note: Browser will show SSL warning (self-signed cert - this is normal)"
echo ""
echo "To proceed in browser:"
echo "  • Chrome/Edge: Click 'Advanced' → 'Proceed to...' "
echo "  • Firefox: Click 'Accept Risk and Continue'"
echo ""
echo "Starting server..."
echo ""

# Run uvicorn with SSL certificate and private key
# Using http11-only to avoid ALPN negotiation issues with self-signed certs
uvicorn backend.main:app \
    --reload \
    --host 0.0.0.0 \
    --port 8000 \
    --ssl-keyfile=/home/guru/qa_app/key.pem \
    --ssl-certfile=/home/guru/qa_app/cert.pem \
    --http=h11
