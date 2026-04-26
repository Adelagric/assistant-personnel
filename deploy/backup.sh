#!/bin/bash
# ============================================================================
#  Backup quotidien des données critiques
#  - data.json, rag_db/, token.pickle, .env, credentials.json
#  - Archive locale + optionnellement upload Backblaze B2
#
#  Variables d'env utilisables (dans .env ou crontab) :
#    B2_ACCOUNT_ID, B2_APPLICATION_KEY, B2_BUCKET
#    BACKUP_ENCRYPTION_KEY (mot de passe GPG symétrique, optionnel)
# ============================================================================
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_DIR="$PROJECT_DIR/backups"
RETENTION_DAYS=7

mkdir -p "$BACKUP_DIR"
cd "$PROJECT_DIR"

# Charger les variables d'env si .env présent
if [[ -f .env ]]; then
    set -a
    source .env
    set +a
fi

TIMESTAMP=$(date -u +%Y%m%d_%H%M%S)
ARCHIVE="$BACKUP_DIR/backup_${TIMESTAMP}.tar.gz"

echo "[$(date -Iseconds)] Backup start → $ARCHIVE"

# 1. Créer l'archive (en excluant ce qui se regénère)
tar --exclude='__pycache__' \
    --exclude='*.log' \
    --exclude='*.log.*' \
    --exclude='.venv' \
    --exclude='backups' \
    -czf "$ARCHIVE" \
    data.json \
    rag_db/ \
    token.pickle \
    .env \
    credentials.json \
    2>/dev/null || true

# 2. Chiffrement optionnel si BACKUP_ENCRYPTION_KEY défini
if [[ -n "${BACKUP_ENCRYPTION_KEY:-}" ]]; then
    if command -v gpg &>/dev/null; then
        gpg --batch --yes --symmetric --cipher-algo AES256 \
            --passphrase "$BACKUP_ENCRYPTION_KEY" \
            --output "${ARCHIVE}.gpg" "$ARCHIVE"
        rm "$ARCHIVE"
        ARCHIVE="${ARCHIVE}.gpg"
        echo "[$(date -Iseconds)] Chiffré (GPG AES256)"
    else
        echo "[$(date -Iseconds)] ⚠️  gpg non installé, backup non chiffré"
    fi
fi

SIZE=$(du -h "$ARCHIVE" | cut -f1)
echo "[$(date -Iseconds)] Archive créée ($SIZE)"

# 3. Upload Backblaze B2 si configuré
if [[ -n "${B2_ACCOUNT_ID:-}" && -n "${B2_APPLICATION_KEY:-}" && -n "${B2_BUCKET:-}" ]]; then
    if ! command -v b2 &>/dev/null; then
        echo "[$(date -Iseconds)] Installation de b2 CLI..."
        pip install --user b2 --quiet
        export PATH="$HOME/.local/bin:$PATH"
    fi
    b2 account authorize "$B2_ACCOUNT_ID" "$B2_APPLICATION_KEY" > /dev/null
    b2 file upload "$B2_BUCKET" "$ARCHIVE" "backups/$(basename "$ARCHIVE")" > /dev/null
    echo "[$(date -Iseconds)] ✓ Uploadé vers B2 ($B2_BUCKET)"
fi

# 4. Rotation locale (garde les N derniers jours)
find "$BACKUP_DIR" -type f -name 'backup_*' -mtime +$RETENTION_DAYS -delete
LOCAL_COUNT=$(find "$BACKUP_DIR" -type f -name 'backup_*' | wc -l)
echo "[$(date -Iseconds)] Backups locaux conservés : $LOCAL_COUNT"

echo "[$(date -Iseconds)] ✅ Backup terminé"
