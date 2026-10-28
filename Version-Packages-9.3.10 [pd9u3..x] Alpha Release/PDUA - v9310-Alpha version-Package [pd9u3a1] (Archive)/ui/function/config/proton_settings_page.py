#!/usr/bin/env python3

import os
import json
import shutil
import tempfile
import threading
from pathlib import Path

# ----------------------------------------------------------------------
# Constants
# ----------------------------------------------------------------------
VERSION = "1.2.10"

_XDG = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
CONFIG_DIR = Path(_XDG) / "pdua"
CONFIG_FILE = CONFIG_DIR / "config.json"

# Legacy locations migrated FROM (read-only, never written again)
LEGACY_CONFIG_FILES = [
    Path(_XDG) / "auth2portal" / "config.json",
    Path(_XDG) / "protondrive-utilityapp" / "settings.json",
]

# Keys that must NEVER be carried across from legacy configs
FORBIDDEN_KEYS = {"passcode", "password", "passphrase", "token", "secret", "credentials"}

DEFAULTS = {
    "version": VERSION,
    "migrated": False,

    # Identity
    "username": "",

    # Appearance / behaviour
    "dark_mode": False,
    "notifications": True,
    "font_size": 9,

    # CLI
    "cli_binary": None,

    # Remote destinations
    "proton_drive_myfiles_remote": "/my-files",
    "proton_drive_albums_remote": "/albums",
    "proton_drive_photos_remote": "/photos",
    "proton_drive_trash_remote": "/trash",

    # Local folders
    "local_source_myfiles": "",
    "local_source_albums": "",
    "local_source_photos": "",
    "local_source_trash": "",
}


class ConfigManager:
    """Thread-safe, recursion-free configuration manager."""

    _lock = threading.Lock()
    _cache = None

    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # PUBLIC API
    # ------------------------------------------------------------------
    def load(self):
        """
        Return the effective config (defaults merged with user values).

        Migration happens at most ONCE perinstall, and is performed inline
        without ever re-entering load().
        """
        with ConfigManager._lock:
            if ConfigManager._cache is not None:
                return dict(ConfigManager._cache)

            stored = self._read_json(CONFIG_FILE) or {}

            # ---- One-time legacy migration ----
            if not stored.get("migrated", False):
                stored = self._merge_legacy(stored)
                stored["migrated"] = True
                merged = {**DEFAULTS, **stored}
                # Direct write. NOT save(). NOT load(). No recursion possible.
                self._write_json(merged)
                ConfigManager._cache = merged
                return dict(merged)

            merged = {**DEFAULTS, **stored}
            ConfigManager._cache = merged
            return dict(merged)

    def save(self, config):
        """Merge with defaults and persist atomically. Returns bool."""
        with ConfigManager._lock:
            merged = {**DEFAULTS, **(config or {})}
            merged["migrated"] = True          # never re-migrate after a save
            ok = self._write_json(merged)
            if ok:
                ConfigManager._cache = merged
            return ok

    def reset(self):
        """Delete the config file and clear the cache."""
        with ConfigManager._lock:
            try:
                if CONFIG_FILE.exists():
                    CONFIG_FILE.unlink()
            except Exception:
                pass
            ConfigManager._cache = None
            return True

    # ------------------------------------------------------------------
    # MIGRATION (reads legacy files directly — never calls load/save)
    # ------------------------------------------------------------------
    def _merge_legacy(self, current):
        merged = dict(current)
        for legacy_path in LEGACY_CONFIG_FILES:
            if not legacy_path.exists():
                continue
            legacy_data = self._read_json(legacy_path)
            if not isinstance(legacy_data, dict):
                continue
            for key, value in legacy_data.items():
                if key in FORBIDDEN_KEYS:
                    continue                      # drop credentials, by design
                if key not in DEFAULTS:
                    continue                      # ignore unknown/foreign keys
                if key in merged and merged[key] not in (None, "", [], {}):
                    continue                      # don't clobber existing values
                merged[key] = value
        return merged

    # ------------------------------------------------------------------
    # LOW-LEVEL IO
    # ------------------------------------------------------------------
    @staticmethod
    def _read_json(path):
        """Read JSON, returning None on ANY failure. Never raises."""
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except Exception:
            return None

    @staticmethod
    def _write_json(data):
        """Atomic write via tempfile + os.replace. Never raises."""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            fd, tmp_path = tempfile.mkstemp(dir=str(CONFIG_DIR), suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump(data, fh, indent=2, sort_keys=False)
                os.replace(tmp_path, CONFIG_FILE)
            except Exception:
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass
                raise
            return True
        except Exception:
            return False

    # ------------------------------------------------------------------
    # CLI DISCOVERY (raw file read — no load(), no recursion)
    # ------------------------------------------------------------------
    @staticmethod
    def find_cli(explicit=None):
        """
        Locate the proton-drive binary.
        Order: explicit arg -> saved config -> standard paths -> PATH lookup.
        """
        candidates = []

        if explicit:
            candidates.append(explicit)

        # Raw read so we never trigger load()/migration from here
        raw = ConfigManager._read_json(CONFIG_FILE) or {}
        saved = raw.get("cli_binary")
        if saved:
            candidates.append(saved)

        home = os.path.expanduser("~")
        candidates.extend([
            "/usr/bin/proton-drive",
            "/usr/local/bin/proton-drive",
            os.path.join(home, ".local", "bin", "proton-drive"),
            # Flatpak (per-user)
            os.path.join(home, ".local", "share", "flatpak", "app",
                         "dev.proton.drive", "current", "active", "files", "bin",
                         "proton-drive"),
            # Flatpak (system)
            "/var/lib/flatpak/app/dev.proton.drive/current/active/files/bin/proton-drive",
            # Snap
            "/snap/proton-drive/current/bin/proton-drive",
            "/snap/bin/proton-drive",
        ])

        for candidate in candidates:
            if candidate and os.path.isfile(candidate) and os.access(candidate, os.X_OK):
                return candidate

        return shutil.which("proton-drive")


# ----------------------------------------------------------------------
# Manual check:  python3 -m ui.function.config_manager
# ----------------------------------------------------------------------
if __name__ == "__main__":
    cm = ConfigManager()
    print(f"Config file : {CONFIG_FILE}")
    print(f"Exists      : {CONFIG_FILE.exists()}")
    print(f"CLI found   : {ConfigManager.find_cli(None)}")
    print("--- effective config ---")
    print(json.dumps(cm.load(), indent=2))
