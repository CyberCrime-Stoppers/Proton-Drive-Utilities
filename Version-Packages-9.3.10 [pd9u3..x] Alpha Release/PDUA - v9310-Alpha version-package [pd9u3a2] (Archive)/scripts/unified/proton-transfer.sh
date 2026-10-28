#!/bin/bash
#
# PDUA Unified Transfer Script
# Replaces all 10 scripts in scripts/up/ and scripts/down/
#
# Usage: proton-transfer.sh <up|down> <Documents|Downloads|Music|Pictures|Videos>
#
# Fixes applied vs the originals:
#   - ~/logs created with mkdir -p (up/ scripts crashed if missing)
#   - CLI discovery loop initializes to empty (dead check now works)
#   - Correct per-folder headers (no more "Restore Downloads" everywhere)
#   - Single source of truth — one script, ten fewer copies to maintain

set -euo pipefail

# === Arguments ===
DIRECTION="${1:?Usage: proton-transfer.sh <up|down> <folder>}"
FOLDER="${2:?Usage: proton-transfer.sh <up|down> <folder>}"

case "$DIRECTION" in
    up|down) ;;
    *) echo "[ERROR] Invalid direction: $DIRECTION (use 'up' or 'down')" >&2; exit 1 ;;
esac

case "$FOLDER" in
    Documents|Downloads|Music|Pictures|Videos) ;;
    *) echo "[ERROR] Invalid folder: $FOLDER" >&2; exit 1 ;;
esac

# === CLI Discovery (fixed: starts empty, check actually fires) ===
PROTON_DRIVE=""
for candidate in "/usr/local/bin/proton-drive" "/usr/bin/proton-drive" "$HOME/.local/bin/proton-drive" "./proton-drive"; do
    if [ -x "$candidate" ]; then
        PROTON_DRIVE="$candidate"
        break
    fi
done

if [ -z "$PROTON_DRIVE" ]; then
    echo "[ERROR] proton-drive CLI not found in any known location" >&2
    echo "[ERROR] Install from: https://proton.me/drive/download" >&2
    exit 1
fi

# === Paths ===
LOCAL_DIR="$HOME/$FOLDER"

if [ "$DIRECTION" = "up" ]; then
    REMOTE_DIR="/my-files/$FOLDER"
    ACTION="Backup"
    LOG_FILE="$HOME/logs/drive-backup.log"
else
    REMOTE_DIR="/my-files/$FOLDER"
    ACTION="Restore"
    LOG_FILE="$HOME/logs/drive-restore.log"
fi

LOG_DIR="$(dirname "$LOG_FILE")"
TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')

# === Setup (FIXED: mkdir -p before ANY logging — up/ scripts died here) ===
mkdir -p "$LOG_DIR"

echo "[$TIMESTAMP] Starting $ACTION of $LOCAL_DIR ↔ $REMOTE_DIR" >> "$LOG_FILE"

if [ "$DIRECTION" = "down" ]; then
    # Validate remote exists before downloading
    if [ -z "$($PROTON_DRIVE filesystem ls "$REMOTE_DIR" 2>/dev/null)" ]; then
        echo "[$TIMESTAMP] ERROR: Remote directory not found: $REMOTE_DIR" >> "$LOG_FILE"
        exit 1
    fi
fi

# === Transfer ===
if [ "$DIRECTION" = "up" ]; then
    # FIX: use find to handle filenames with spaces safely
    if find "$LOCAL_DIR" -maxdepth 1 -mindepth 1 -print0 |
       xargs -0 -r "$PROTON_DRIVE" filesystem upload "$REMOTE_DIR" >> "$LOG_FILE" 2>&1; then
        echo "[$TIMESTAMP] $ACTION of $FOLDER completed successfully." >> "$LOG_FILE"
    else
        EXIT_CODE=$?
        echo "[$TIMESTAMP] ERROR: $ACTION of $FOLDER failed with exit code $EXIT_CODE." >> "$LOG_FILE"
        echo "[$TIMESTAMP] If auth expired, run: $PROTON_DRIVE auth login" >> "$LOG_FILE"
        exit 1
    fi
else
    if "$PROTON_DRIVE" filesystem download "$REMOTE_DIR" "$LOCAL_DIR" >> "$LOG_FILE" 2>&1; then
        echo "[$TIMESTAMP] $ACTION of $FOLDER completed successfully." >> "$LOG_FILE"
    else
        EXIT_CODE=$?
        echo "[$TIMESTAMP] ERROR: $ACTION of $FOLDER failed with exit code $EXIT_CODE." >> "$LOG_FILE"
        echo "[$TIMESTAMP] If auth expired, run: $PROTON_DRIVE auth login" >> "$LOG_FILE"
        exit 1
    fi
fi