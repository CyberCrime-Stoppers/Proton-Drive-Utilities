#!/bin/bash
# ============================================================================
# PDUA Thumbnail Cache Setup Guide
# Proton Drive Utility App - Album/Photo Viewer with Safe Caching
# ============================================================================
# 
# This script helps you set up and test the thumbnail caching system for PDUA.
# Follow along carefully and watch for any error messages.
#
# Prerequisites:
#   - Linux system with GTK4 >= 4.6 and libadwaita >= 1.1
#   - Proton Drive CLI installed and working
#   - Python 3.10+ with PyGObject (gi) package
#
# Estimated time: 5-10 minutes
# ============================================================================

set -euo pipefail

echo "=========================================="
echo "PDUA Thumbnail Cache Setup"
echo "=========================================="
echo ""

# ----------------------------------------------------------------------------
# STEP 1: Verify Prerequisites
# ----------------------------------------------------------------------------
echo "[STEP 1] Checking prerequisites..."

# Check Python version
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python 3 not found!"
    exit 1
fi

python_version=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
echo "  ✓ Python version: $python_version"

# Check GTK4 and libadwaita
python3 -c "
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
print('  ✓ GTK4 version:', '.'.join(map(str, Gtk.get_version())))
print('  ✓ Libadwaita version:', '.'.join(map(str, Adw.get_version())))
" || {
    echo "ERROR: GTK4 or libadwaita not properly installed!"
    echo "Install with: sudo apt install python3-gi gir1.2-gtk-4.0 gir1.2-libadwaita-1"
    exit 1
}

# Check Proton Drive CLI
CLI_PATH=$(which proton-drive 2>/dev/null || echo "")
if [[ -z "$CLI_PATH" ]]; then
    echo "WARNING: proton-drive CLI not found in PATH!"
    echo "  Try: sudo apt install proton-drive"
    echo "  Or: Check your installation at https://github.com/protonme/proton-drive-cli"
    echo "  Continuing anyway..."
else
    echo "  ✓ Proton Drive CLI found: $CLI_PATH"
    proton_version=$("$CLI_PATH" --version 2>&1 | head -1 || echo "unknown")
    echo "    Version: $proton_version"
fi

echo ""

# ----------------------------------------------------------------------------
# STEP 2: Create Required Directories
# ----------------------------------------------------------------------------
echo "[STEP 2] Creating required directories..."

CONFIG_DIR="$HOME/.config/pdua"
CACHE_DIR="$HOME/.cache/pdua/thumbnails"
LOG_DIR="$HOME/logs"

mkdir -p "$CONFIG_DIR"
mkdir -p "$CACHE_DIR"
mkdir -p "$LOG_DIR"

echo "  ✓ Config directory: $CONFIG_DIR"
echo "  ✓ Cache directory: $CACHE_DIR"
echo "  ✓ Log directory: $LOG_DIR"

# Set proper permissions
chmod 700 "$CONFIG_DIR"
chmod 700 "$CACHE_DIR"

echo ""

# ----------------------------------------------------------------------------
# STEP 3: Create Initial Configuration File
# ----------------------------------------------------------------------------
echo "[STEP 3] Creating initial configuration..."

cat > "$CONFIG_DIR/config.json" << EOF
{
  "version": "1.2.10",
  "migrated": true,
  
  "username": "",
  
  "dark_mode": false,
  "notifications": true,
  "font_size": 9,
  
  "cli_binary": "$CLI_PATH",
  
  "proton_drive_myfiles_remote": "/my-files",
  "proton_drive_albums_remote": "/albums",
  "proton_drive_photos_remote": "/photos",
  "proton_drive_trash_remote": "/trash",
  
  "local_source_myfiles": "$HOME/Downloads",
  "local_source_albums": "$HOME/Pictures/Albums",
  "local_source_photos": "$HOME/Pictures",
  "local_source_trash": "$HOME/.Trash",
  
  "thumbnail_cache_enabled": true,
  "thumbnail_cache_mb": 100,
  "thumbnail_size_px": 256,
  
  "cached_count": 0,
  "cached_bytes": 0
}
EOF

echo "  ✓ Created config file: $CONFIG_DIR/config.json"
echo "  Note: Update username and local paths as needed"

echo ""

# ----------------------------------------------------------------------------
# STEP 4: Test CLI Listing Command
# ----------------------------------------------------------------------------
echo "[STEP 4] Testing CLI listing commands..."

echo "  Testing filesystem list command..."
if $CLI_PATH filesystem list /Albums 2>&1 | head -5; then
    echo "  ✓ Album listing works!"
else
    echo "  ⚠ Album listing may have issues (check if you're logged in)"
fi

echo "  Testing photos list command..."
if $CLI_PATH album photos /Albums/TestAlbum 2>&1 | head -5; then
    echo "  ✓ Photo listing works!"
else
    echo "  ⚠ Photo listing may have issues (album might not exist yet)"
fi

echo ""

# ----------------------------------------------------------------------------
# STEP 5: Test Thumbnail Download Logic
# ----------------------------------------------------------------------------
echo "[STEP 5] Testing thumbnail download logic..."

# Create a temporary directory for test downloads
TEST_DOWNLOAD_DIR=$(mktemp -d -t pdua_test_XXXXXX)
trap "rm -rf $TEST_DOWNLOAD_DIR" EXIT

# Test download command
SAMPLE_REMOTE="/Albums/Sample.jpg"
echo "  Testing download of: $SAMPLE_REMOTE to $TEST_DOWNLOAD_DIR"

if $CLI_PATH filesystem download "$SAMPLE_REMOTE" "$TEST_DOWNLOAD_DIR" 2>&1; then
    DOWNLOADED_FILE="$TEST_DOWNLOAD_DIR/$(basename $SAMPLE_REMOTE)"
    if [[ -f "$DOWNLOADED_FILE" ]]; then
        FILE_SIZE=$(stat -c%s "$DOWNLOADED_FILE" 2>/dev/null || echo "0")
        echo "  ✓ Download successful! Size: $FILE_SIZE bytes"
    else
        echo "  ⚠ Download completed but file not found"
    fi
else
    echo "  ⚠ Download command failed (might be authentication required or file not found)"
    echo "  TIP: Make sure you're logged in with 'proton-drive auth login'"
fi

echo ""

# ----------------------------------------------------------------------------
# STEP 6: Initialize Cache Statistics
# ----------------------------------------------------------------------------
echo "[STEP 6] Initializing cache statistics..."

python3 << EOF
import json
from pathlib import Path

config_file = Path("$CONFIG_DIR/config.json")
cache_dir = Path("$CACHE_DIR")

# Read current config
with open(config_file) as f:
    config = json.load(f)

# Calculate current cache stats
cache_files = list(cache_dir.glob("*.png"))
config["cached_count"] = len(cache_files)
config["cached_bytes"] = sum(f.stat().st_size for f in cache_files if f.exists())

# Update config
with open(config_file, 'w') as f:
    json.dump(config, f, indent=2)

print(f"  ✓ Cache initialized: {len(cache_files)} files, {config['cached_bytes']} bytes")
print(f"    Cache location: {cache_dir}")
print(f"    Max size: {config.get('thumbnail_cache_mb', 100)} MB")
EOF

echo ""

# ----------------------------------------------------------------------------
# STEP 7: Verify Python Module Imports
# ----------------------------------------------------------------------------
echo "[STEP 7] Verifying Python module imports..."

python3 << 'PYTEST'
try:
    from ui.function.config_manager import ConfigManager
    print("  ✓ ConfigManager imported successfully")
except ImportError as e:
    print(f"  ⚠ ConfigManager import failed: {e}")

try:
    from ui.function.pup.remote.thumbnail_cache import ThumbnailCache
    print("  ✓ ThumbnailCache imported successfully")
except ImportError as e:
    print(f"  ⚠ ThumbnailCache import failed: {e}")
    print("  TIP: Make sure you're running from the PDUA project root")

try:
    from ui.function.pup.remote.album_explorer_page import AlbumExplorerPage
    print("  ✓ AlbumExplorerPage imported successfully")
except ImportError as e:
    print(f"  ⚠ AlbumExplorerPage import failed: {e}")
    print("  TIP: Check that ui/function/pup/remote/ directory exists")
PYTEST

echo ""

# ----------------------------------------------------------------------------
# STEP 8: Display Configuration Summary
# ----------------------------------------------------------------------------
echo "[STEP 8] Configuration Summary"
echo "============================================="
cat "$CONFIG_DIR/config.json"
echo ""
echo "============================================="

# ----------------------------------------------------------------------------
# STEP 9: Next Steps
# ----------------------------------------------------------------------------
echo ""
echo "[NEXT STEPS]"
echo "============"
echo "1. Ensure you're logged in to Proton Drive:"
echo "   proton-drive auth login"
echo ""
echo "2. Launch the application:"
echo "   cd /path/to/pdua"
echo "   python3 main.py"
echo ""
echo "3. Navigate to 'Album Browser' in the sidebar"
echo ""
echo "4. If thumbnails don't load, check:"
echo "   - Are you logged in? (proton-drive auth status)"
echo "   - Do albums exist? (proton-drive album list)"
echo "   - Check terminal for error messages"
echo ""
echo "5. Monitor cache usage:"
echo "   du -sh ~/.cache/pdua/thumbnails/"
echo ""
echo "6. Clear cache if needed:"
echo "   rm -rf ~/.cache/pdua/thumbnails/*"
echo ""
echo "=========================================="
echo "Setup complete!"
echo "=========================================="