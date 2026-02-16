#!/bin/bash
# =============================================================================
# Certify Intel - Automated SQLite Backup with 30-day Retention
# =============================================================================
# Usage:
#   ./scripts/backup-db.sh
#   # Or via cron: 0 2 * * * /path/to/scripts/backup-db.sh
# =============================================================================

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-backups}"
DB_PATH="${DB_PATH:-backend/certify_intel.db}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

# Validate database exists
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: Database not found at $DB_PATH"
    exit 1
fi

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Create timestamped backup
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/certify_intel_${TIMESTAMP}.db"

# Use SQLite .backup for consistent snapshot (avoids partial writes)
if command -v sqlite3 &> /dev/null; then
    sqlite3 "$DB_PATH" ".backup '$BACKUP_FILE'"
else
    cp "$DB_PATH" "$BACKUP_FILE"
fi

# Compress backup
gzip "$BACKUP_FILE"

# Report backup size
BACKUP_SIZE=$(du -h "$BACKUP_FILE.gz" | cut -f1)
echo "Backup created: ${BACKUP_FILE}.gz ($BACKUP_SIZE)"

# Cleanup old backups
DELETED=$(find "$BACKUP_DIR" -name "*.db.gz" -mtime +$RETENTION_DAYS -delete -print | wc -l)
if [ "$DELETED" -gt 0 ]; then
    echo "Cleaned up $DELETED backup(s) older than $RETENTION_DAYS days"
fi
