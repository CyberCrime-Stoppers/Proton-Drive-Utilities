#!/bin/bash
#
# Encrypted backup to Proton Drive
#

set -euo pipefail

# === Config ===
PROTON_DRIVE="/usr/bin/proton-drive"
SOURCE_DIR="$HOME/Pictures"
DEST_DIR="/my-files/Pictures"
LOG_FILE="$HOME/logs/drive-backup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# === Start ===
echo "[$TIMESTAMP] Starting backup of $SOURCE_DIR → $DEST_DIR" >> "$LOG_FILE"

# Upload files (will fail with non-zero exit if not authenticated)
if $PROTON_DRIVE filesystem upload "$SOURCE_DIR"/* "$DEST_DIR" >> "$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] Backup completed successfully." >> "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] ERROR: Backup failed with exit code $EXIT_CODE." >> "$LOG_FILE"
    echo "[$TIMESTAMP] If auth expired, run: $PROTON_DRIVE auth login" >> "$LOG_FILE"
    exit 1
fi
