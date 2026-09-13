#!/bin/bash
#
# Encrypted backup from Proton Drive
#

set -euo pipefail

# === Config ===
PROTON_DRIVE="/usr/bin/proton-drive"
SOURCE_DIR="/my-files/Pictures"
DEST_DIR="$HOME/Pictures"
LOG_FILE="$HOME/logs/drive-backup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# === Start ===
echo "[$TIMESTAMP] Starting download: $SOURCE_DIR → $DEST_DIR" | tee -a "$LOG_FILE"

# Download files from Proton Drive
if "$PROTON_DRIVE" filesystem download "$SOURCE_DIR" "$DEST_DIR" >> "$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] ✓ Download completed successfully." | tee -a "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] ✗ ERROR: Download failed with exit code $EXIT_CODE." | tee -a "$LOG_FILE"
    echo "[$TIMESTAMP] If auth expired, run: $PROTON_DRIVE auth login" | tee -a "$LOG_FILE"
    exit 1
fi

