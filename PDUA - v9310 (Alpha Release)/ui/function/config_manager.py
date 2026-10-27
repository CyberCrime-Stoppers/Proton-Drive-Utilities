#!/usr/bin/env python3
"""
Unified Config Manager for Proton Drive Utility App (PDUA)
Single source of truth for all application settings.
"""

import json
import os
from pathlib import Path


# === CONFIGURATION ===
APP_NAME = "pdua"
CONFIG_DIR = Path.home() / ".config" / APP_NAME
CONFIG_FILE = CONFIG_DIR / "config.json"
VERSION = "1.2.10"  # Centralized version string

DEFAULT_CONFIG = {
    # Version tracking
    "version": VERSION,

    # Proton Drive remote paths
    "proton_drive_myfiles_remote": "/my-files",
    "proton_drive_albums_remote": "/albums",
    "proton_drive_photos_remote": "/photos",
    "proton_drive_trash_remote": "/trash",

    # Local source paths (for custom transfers)
    "local_source_myfiles": str(Path.home() / "Documents"),
    "local_source_albums": str(Path.home() / "Pictures" / "Albums"),
    "local_source_photos": str(Path.home() / "Pictures"),
    "local_source_trash": str(Path.home() / "Downloads"),

    # CLI binary detection
    "cli_binary": None,  # None means auto-detect on use

    # User preferences
    "username": "",  # Display name only — NOT a credential!
    "dark_mode": None,  # None = system default
    "notifications": True,
    "font_size": 9,  # Base font size in px (for CSS variables)

    # Transfer defaults
    "default_download_timeout": 600,  # seconds
    "default_upload_timeout": 600,
    "progress_enabled": True,
}

CLI_SEARCH_PATHS = [
    "/usr/bin/proton-drive",
    "/usr/local/bin/proton-drive",
    str(Path.home() / ".local" / "bin" / "proton-drive"),
    str(Path.home() / ".local" / "share" / "flatpak" / "app" / "dev.proton.drive" / "current" / "active" / "files" / "bin" / "proton-drive"),
    "/snap/proton-drive/current/bin/proton-drive",
]


class ConfigManager:
    """Thread-safe config manager with automatic migration."""

    _instance = None
    _lock = None  # Initialized on first call

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._lock = threading.Lock()
        return cls._instance

    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._config = None
            self._initialized = True

    def load(self):
        """Load config from disk, migrating legacy configs, falling back to defaults."""
        with self._lock:
            if self._config is not None:
                return self._config.copy()

            # Step 1: Check for legacy configs and migrate
            pass  # TEMP: migration disabled — recursion bug

            # Step 2: Load current config
            try:
                if CONFIG_FILE.exists():
                    with open(CONFIG_FILE, 'r') as f:
                        user_config = json.load(f)
                    # Merge with defaults
                    merged = DEFAULT_CONFIG.copy()
                    merged.update(user_config)
                    self._config = merged
                    return merged.copy()
            except (json.JSONDecodeError, IOError) as e:
                print(f"[Config] Error loading {CONFIG_FILE}: {e}")
                print("[Config] Falling back to defaults")

            # Step 3: Return defaults
            self._config = DEFAULT_CONFIG.copy()
            return self._config.copy()

    def save(self, config):
        """Save config to disk with atomic write."""
        with self._lock:
            try:
                # Ensure directory exists
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)

                # Atomic write: write to temp file, then rename
                temp_file = CONFIG_FILE.with_suffix('.tmp')
                with open(temp_file, 'w') as f:
                    json.dump(config, f, indent=2)
                temp_file.rename(CONFIG_FILE)

                self._config = config.copy()
                print(f"[Config] Saved to {CONFIG_FILE}")
                return True

            except (IOError, OSError) as e:
                print(f"[Config] Error saving: {e}")
                return False

    def get(self, key, default=None):
        """Get a config value."""
        config = self.load()
        return config.get(key, default)

    def set(self, key, value):
        """Set a config value and save immediately."""
        config = self.load()
        config[key] = value
        return self.save(config)

    def _migrate_legacy_configs(self):
        """Migrate configs from wrong legacy directories."""
        migrated = False

        # Legacy 1: auth2portal (from config_manager.py original)
        old_path_1 = Path.home() / ".config" / "auth2portal" / "config.json"
        if old_path_1.exists():
            try:
                with open(old_path_1, 'r') as f:
                    legacy_data = json.load(f)
                # Merge into current config
                current = self.load()
                current.update(legacy_data)
                self.save(current)
                print(f"[Config] Migrated from {old_path_1}")
                migrated = True
            except Exception as e:
                print(f"[Config] Migration warning: {e}")

        # Legacy 2: protondrive-utilityapp (from settings_page.py)
        old_path_2 = Path.home() / ".config" / "protondrive-utilityapp" / "settings.json"
        if old_path_2.exists():
            try:
                with open(old_path_2, 'r') as f:
                    legacy_data = json.load(f)
                current = self.load()
                # Only migrate safe fields (not passcode!)
                for key in ['username', 'dark_mode', 'notifications']:
                    if key in legacy_data:
                        current[key] = legacy_data[key]
                self.save(current)
                print(f"[Config] Migrated from {old_path_2}")
                migrated = True
            except Exception as e:
                print(f"[Config] Migration warning: {e}")

        # NOTE: passcode field intentionally NOT migrated — it was a security risk

        if migrated:
            print(f"[Config] Legacy configs migrated to {CONFIG_FILE}")

    @staticmethod
    def find_cli(cli_hint=None):
        """
        Locate proton-drive CLI binary.
        Returns absolute path or None if not found.
        """
        # Priority 1: User-specified hint (from config)
        if cli_hint:
            expanded = os.path.expanduser(cli_hint)
            if os.path.isfile(expanded) and os.access(expanded, os.X_OK):
                return expanded

        # Priority 2: System search paths
        for path in CLI_SEARCH_PATHS:
            p = Path(path)
            if p.exists() and os.access(p, os.X_OK):
                return str(p)

        # Priority 3: PATH lookup
        cli_in_path = shutil.which("proton-drive")
        if cli_in_path:
            return cli_in_path

        return None


# Import at module level after class definition
import shutil
import threading