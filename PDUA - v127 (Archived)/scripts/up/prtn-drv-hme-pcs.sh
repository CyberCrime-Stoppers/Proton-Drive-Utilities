#!/bin/bash
#
# Upload Documents to Proton Drive
#

set -euo pipefail

# === Config ===
PROTON_DRIVE="/usr/bin/proton-drive"
for candidate in "/usr/local/bin/proton-drive" "/usr/bin/proton-drive" "$HOME/.local/bin/proton-drive" "./proton-drive"; do
    if [ -x "$candidate" ]; then
        PROTON_DRIVE="$candidate"
        break
    fi
done

if [ -z "$PROTON_DRIVE" ]; then
    echo "[ERROR] proton-drive CLI not found" >&2
    exit 1
fi

SOURCE_DIR="$HOME/Pictures"
DEST_DIR="/my-files/Documents"
LOG_DIR="$HOME/logs"
LOG_FILE="$LOG_DIR/drive-backup.log"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# === Setup ===
mkdir -p "$LOG_DIR"

echo "[$TIMESTAMP] Starting backup of $SOURCE_DIR → $DEST_DIR" >> "$LOG_FILE"

# Validate source
if [ ! -d "$SOURCE_DIR" ]; then
    echo "[$TIMESTAMP] ERROR: Source directory not found: $SOURCE_DIR" >> "$LOG_FILE"
    exit 1
fi

# Check for files
if ! compgen -G "$SOURCE_DIR/*" > /dev/null 2>&1; then
    echo "[$TIMESTAMP] INFO: No files in $SOURCE_DIR, skipping." >> "$LOG_FILE"
    exit 0
fi

# Upload
if $PROTON_DRIVE filesystem upload "$SOURCE_DIR" "$DEST_DIR" >> "$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] Backup completed successfully." >> "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] ERROR: Backup failed with exit code $EXIT_CODE." >> "$LOG_FILE"
    echo "[$TIMESTAMP] If auth expired, run: $PROTON_DRIVE auth login" >> "$LOG_FILE"
    exit 1
fi
