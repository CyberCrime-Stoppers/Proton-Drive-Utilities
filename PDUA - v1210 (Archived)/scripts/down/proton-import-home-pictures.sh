#!/bin/bash
#
# Restore Downloads from Proton Drive
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

REMOTE_DIR="/my-files/Pictures"
LOCAL_DIR="$HOME/Pictures"
LOG_DIR="$HOME/logs"
LOG_FILE="$LOG_DIR/drive-restore.log"  # Different name for clarity
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# === Setup ===
mkdir -p "$LOG_DIR"

echo "[$TIMESTAMP] Starting restore of $REMOTE_DIR → $LOCAL_DIR" >> "$LOG_FILE"

# Validate remote
if [ -z "$($PROTON_DRIVE filesystem ls "$REMOTE_DIR" 2>/dev/null)" ]; then
    echo "[$TIMESTAMP] ERROR: Remote directory not found: $REMOTE_DIR" >> "$LOG_FILE"
    exit 1
fi

# Download (note: remote first, local second)
if $PROTON_DRIVE filesystem download "$REMOTE_DIR" "$LOCAL_DIR" >> "$LOG_FILE" 2>&1; then
    echo "[$TIMESTAMP] Restore completed successfully." >> "$LOG_FILE"
else
    EXIT_CODE=$?
    echo "[$TIMESTAMP] ERROR: Restore failed with exit code $EXIT_CODE." >> "$LOG_FILE"
    echo "[$TIMESTAMP] If auth expired, run: $PROTON_DRIVE auth login" >> "$LOG_FILE"
    exit 1
fi
