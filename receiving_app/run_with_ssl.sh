#!/bin/bash
set -euo pipefail

# Receiving App HTTPS startup script.
# Uses SSL_KEYFILE / SSL_CERTFILE when provided, otherwise creates a local
# self-signed certificate outside the repo in /tmp.

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$APP_DIR"

# Activate virtual environment
source "$APP_DIR/env/bin/activate"

IP="$(hostname -I | awk '{print $1}')"
IP="${IP:-127.0.0.1}"
PORT="${PORT:-8000}"

SSL_KEYFILE="${SSL_KEYFILE:-}"
SSL_CERTFILE="${SSL_CERTFILE:-}"
SSL_DIR="${SSL_DIR:-/tmp/receiving_app_ssl}"

if [[ -z "$SSL_KEYFILE" || -z "$SSL_CERTFILE" ]]; then
    mkdir -p "$SSL_DIR"
    SSL_KEYFILE="$SSL_DIR/key.pem"
    SSL_CERTFILE="$SSL_DIR/cert.pem"

    if [[ ! -f "$SSL_KEYFILE" || ! -f "$SSL_CERTFILE" ]]; then
        if ! command -v openssl >/dev/null 2>&1; then
            echo "OpenSSL is required to generate a local development certificate."
            echo "Set SSL_KEYFILE and SSL_CERTFILE to existing files or install openssl."
            exit 1
        fi

        openssl req \
            -x509 \
            -nodes \
            -days 365 \
            -newkey rsa:2048 \
            -keyout "$SSL_KEYFILE" \
            -out "$SSL_CERTFILE" \
            -subj "/CN=${IP}" >/dev/null 2>&1
    fi
fi

echo "=============================================="
echo "Receiving App HTTPS Server"
echo "=============================================="
echo "Server Address: https://${IP}:${PORT}/receiving"
echo "SSL Key: ${SSL_KEYFILE}"
echo "SSL Cert: ${SSL_CERTFILE}"
echo ""
echo "Self-signed certificates will trigger a browser warning in development."
echo ""

uvicorn backend.main:app \
    --reload \
    --host 0.0.0.0 \
    --port "$PORT" \
    --ssl-keyfile="$SSL_KEYFILE" \
    --ssl-certfile="$SSL_CERTFILE" \
    --http=h11
