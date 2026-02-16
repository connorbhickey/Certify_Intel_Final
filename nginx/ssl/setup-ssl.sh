#!/bin/bash
# =============================================================================
# Certify Intel - SSL/TLS Certificate Setup
# =============================================================================
# Usage:
#   Production (Let's Encrypt):
#     ./setup-ssl.sh --production --domain certifyintel.com --email [YOUR-ADMIN-EMAIL]
#
#   Development (self-signed):
#     ./setup-ssl.sh --dev
# =============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SSL_DIR="$SCRIPT_DIR"

show_help() {
    echo "Usage: ./setup-ssl.sh [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --dev                  Generate self-signed certificates for local development"
    echo "  --production           Use Let's Encrypt for production certificates"
    echo "  --domain DOMAIN        Domain name (required for --production)"
    echo "  --email EMAIL          Email for Let's Encrypt notifications (required for --production)"
    echo "  --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  ./setup-ssl.sh --dev"
    echo "  ./setup-ssl.sh --production --domain certifyintel.com --email [YOUR-ADMIN-EMAIL]"
}

generate_dev_certs() {
    echo "==> Generating self-signed development certificates..."

    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout "$SSL_DIR/privkey.pem" \
        -out "$SSL_DIR/fullchain.pem" \
        -subj "/C=US/ST=State/L=City/O=CertifyIntel/CN=localhost" \
        -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

    chmod 600 "$SSL_DIR/privkey.pem"
    chmod 644 "$SSL_DIR/fullchain.pem"

    echo ""
    echo "==> Development certificates generated:"
    echo "    Certificate: $SSL_DIR/fullchain.pem"
    echo "    Private key: $SSL_DIR/privkey.pem"
    echo ""
    echo "    These are SELF-SIGNED and only for local development."
    echo "    Your browser will show a security warning - this is expected."
    echo ""
    echo "    Next steps:"
    echo "    1. cd $(dirname "$SCRIPT_DIR")/.. "
    echo "    2. docker-compose -f docker-compose.prod.yml up -d"
}

generate_production_certs() {
    local domain="$1"
    local email="$2"

    if [ -z "$domain" ] || [ -z "$email" ]; then
        echo "ERROR: --domain and --email are required for production mode."
        echo ""
        show_help
        exit 1
    fi

    echo "==> Requesting Let's Encrypt certificate for $domain..."

    # Step 1: Start nginx with HTTP-only config for ACME challenge
    # The docker-compose certbot service handles this automatically.
    # Run this from the project root:
    echo ""
    echo "Run these commands from the project root directory:"
    echo ""
    echo "  # 1. Start nginx (it will serve ACME challenges on HTTP)"
    echo "  docker-compose -f docker-compose.prod.yml up -d nginx"
    echo ""
    echo "  # 2. Request the certificate"
    echo "  docker-compose -f docker-compose.prod.yml run --rm certbot certonly \\"
    echo "    --webroot -w /var/www/certbot \\"
    echo "    -d $domain \\"
    echo "    --email $email \\"
    echo "    --agree-tos \\"
    echo "    --no-eff-email"
    echo ""
    echo "  # 3. Copy certs to the expected location"
    echo "  cp /etc/letsencrypt/live/$domain/fullchain.pem $SSL_DIR/fullchain.pem"
    echo "  cp /etc/letsencrypt/live/$domain/privkey.pem $SSL_DIR/privkey.pem"
    echo ""
    echo "  # 4. Restart nginx to pick up the new certificates"
    echo "  docker-compose -f docker-compose.prod.yml restart nginx"
    echo ""
    echo "  # 5. Start certbot auto-renewal (runs every 12h)"
    echo "  docker-compose -f docker-compose.prod.yml up -d certbot"
    echo ""
    echo "Certificate renewal is automatic via the certbot container."
}

# Parse arguments
MODE=""
DOMAIN=""
EMAIL=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --dev)
            MODE="dev"
            shift
            ;;
        --production)
            MODE="production"
            shift
            ;;
        --domain)
            DOMAIN="$2"
            shift 2
            ;;
        --email)
            EMAIL="$2"
            shift 2
            ;;
        --help)
            show_help
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

if [ -z "$MODE" ]; then
    echo "ERROR: Specify --dev or --production"
    echo ""
    show_help
    exit 1
fi

case $MODE in
    dev)
        generate_dev_certs
        ;;
    production)
        generate_production_certs "$DOMAIN" "$EMAIL"
        ;;
esac
