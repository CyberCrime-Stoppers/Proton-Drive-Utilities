#!/usr/bin/env python3
"""
Thumbnail Cache for PDUA — TOS-safe, content-addressed, LRU-bounded
====================================================================
FIXED VERSION: Updated to match Proton CLI 2026 syntax
  - filesystem download expects: download <path>... <LOCAL_FOLDER>
  - NOT: download <path> <FILE_PATH> (this is WRONG)

Design principles (README compliant):
  - Only SCALED thumbnails are written to disk (default 256px)
  - Full-resolution originals go to a TEMP directory, get scaled, then DELETED
  - Cache keys are SHA-256 hashes of the remote path (privacy)
  - Bounded by LRU eviction (default 100 MB, configurable)
  - Location: ~/.cache/pdua/thumbnails/ (standard XDG cache dir)

Config keys (in ~/.config/pdua/config.json):
  "thumbnail_cache_enabled": true
  "thumbnail_cache_mb":      100
  "thumbnail_size_px":       256
  
Version  9.3.10-Alpha
"""

import os
import hashlib
import tempfile
import threading
import subprocess
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import GLib, GdkPixbuf

from ui.function.config_manager import ConfigManager

_XDG_CACHE = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
CACHE_DIR = Path(_XDG_CACHE) / "pdua" / "thumbnails"


class ThumbnailCache:
    """Thread-safe thumbnail cache with async CLI-backed fetching."""

    _lock = threading.Lock()

    def __init__(self, cli_path=None):
        config = ConfigManager().load()
        self.enabled = config.get("thumbnail_cache_enabled", True)
        self.max_bytes = int(config.get("thumbnail_cache_mb", 100)) * 1024 * 1024
        self.size_px = int(config.get("thumbnail_size_px", 256))
        self.cli = cli_path or ConfigManager.find_cli(None)

        if self.enabled:
            CACHE_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # PUBLIC API (CORRECTED CALLBACK CONTRACT)
    # ------------------------------------------------------------------

    def get_async_with_callback(self, remote_path, callback, size_px=None):
        """
        Fetch a thumbnail asynchronously. Invokes callback(pixbuf) on the
        GTK main thread when done — pixbuf is None on failure.
        Cached hits invoke the callback immediately.
        
        IMPORTANT: Callback MUST be bound to the target widget via closure
        to avoid signature mismatch bugs:
          self.cache.get_async_with_callback(remote_path, lambda pb, holder=w: ...)
        """
        if not self.enabled:
            GLib.idle_add(callback, None)
            return

        size = size_px or self.size_px
        cached = self._read_cached(remote_path, size)
        if cached is not None:
            GLib.idle_add(callback, cached)
            return

        def worker():
            pixbuf = self.get_sync(remote_path, size)
            GLib.idle_add(callback, pixbuf)

        threading.Thread(target=worker, daemon=True).start()

    def get_sync(self, remote_path, size_px=None):
        """Synchronous variant — ONLY for tests/tooling, never UI thread."""
        size = size_px or self.size_px
        cached = self._read_cached(remote_path, size)
        if cached is not None:
            return cached
        downloaded_file = self._download_single(remote_path)
        if downloaded_file is None:
            return None
        try:
            pixbuf = self._scale_from(downloaded_file, size)
            if pixbuf is not None:
                self._store(remote_path, size, downloaded_file)
            return pixbuf
        finally:
            try:
                os.unlink(downloaded_file)  # Never keep original
            except Exception:
                pass

    def purge(self):
        """Delete every cached thumbnail."""
        with ThumbnailCache._lock:
            removed = 0
            try:
                for f in CACHE_DIR.iterdir():
                    if f.is_file():
                        f.unlink()
                        removed += 1
            except Exception:
                pass
            return removed

    def stats(self):
        """Return (file_count, total_bytes)."""
        count, total = 0, 0
        try:
            for f in CACHE_DIR.iterdir():
                if f.is_file():
                    count += 1
                    total += f.stat().st_size
        except Exception:
            pass
        return count, total

    # ------------------------------------------------------------------
    # INTERNALS
    # ------------------------------------------------------------------

    @staticmethod
    def _key(remote_path, size):
        digest = hashlib.sha256(remote_path.encode("utf-8")).hexdigest()[:32]
        return CACHE_DIR / f"{digest}_{size}.png"

    def _read_cached(self, remote_path, size):
        path = self._key(remote_path, size)
        if not path.exists():
            return None
        try:
            os.utime(path, None)  # Touch mtime for LRU
            return GdkPixbuf.Pixbuf.new_from_file_at_size(str(path), size, size)
        except Exception:
            return None

    def _download_single(self, remote_path):
        """
        Download a SINGLE file from Proton Drive using the CLI.
        
        CLI SYNTAX (PROTON 2026):
          filesystem download <remote_path> <LOCAL_FOLDER>
          
        Note: It downloads INTO a folder, not to a specific file path.
        The downloaded file will have the same basename as remote_path.
        
        Returns: absolute path to the downloaded file, or None on error.
        """
        if not self.cli:
            return None
            
        # Create a temp DIRECTORY for the download
        temp_dir = tempfile.mkdtemp(prefix="pdua_dl_")
        
        try:
            cmd = [self.cli, "filesystem", "download", remote_path, temp_dir]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                import logging
                log = logging.getLogger("pdua.cache")
                log.error(f"Download failed: {result.stderr}")
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
            
            # Find the downloaded file (same basename as remote_path)
            basename = os.path.basename(remote_path.rstrip("/"))
            downloaded_file = os.path.join(temp_dir, basename)
            
            if not os.path.isfile(downloaded_file):
                # Maybe the CLI renamed it? Look for any file in the dir
                files = os.listdir(temp_dir)
                if files:
                    downloaded_file = os.path.join(temp_dir, files[0])
                else:
                    import shutil
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    return None
            
            if os.path.getsize(downloaded_file) == 0:
                os.unlink(downloaded_file)
                shutil.rmtree(temp_dir, ignore_errors=True)
                return None
            
            # Success — move file OUT of the temp dir so we can delete the dir
            final_path = downloaded_file + ".tmp"
            os.rename(downloaded_file, final_path)
            shutil.rmtree(temp_dir, ignore_errors=True)
            
            return final_path
            
        except Exception as exc:
            import logging
            log = logging.getLogger("pdua.cache")
            log.error(f"Download exception: {exc}")
            try:
                import shutil
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass
            return None

    @staticmethod
    def _scale_from(temp_file, size):
        """Scale a downloaded image to a square-ish thumbnail."""
        try:
            return GdkPixbuf.Pixbuf.new_from_file_at_scale(temp_file, size, size, True)
        except Exception:
            return None

    def _store(self, remote_path, size, temp_file):
        """Save the SCALED thumbnail into the cache (PNG), then evict."""
        with ThumbnailCache._lock:
            try:
                dest = self._key(remote_path, size)
                src_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(temp_file, size, size, True)
                success = src_pixbuf.savev(str(dest), "png", [None], [None])
                if success:
                    self._evict_locked()
            except Exception:
                pass
            finally:
                try:
                    os.unlink(temp_file)
                except Exception:
                    pass

    def _evict_locked(self):
        """Caller must hold _lock. Evict oldest files until under budget."""
        try:
            files = [(f.stat().st_mtime, f.stat().st_size, f) for f in CACHE_DIR.iterdir() if f.is_file()]
        except Exception:
            return
        total = sum(sz for _, sz, _ in files)
        if total <= self.max_bytes:
            return
        files.sort()  # Oldest first
        for _, sz, f in files:
            if total <= self.max_bytes:
                break
            try:
                f.unlink()
                total -= sz
            except Exception:
                pass


# Manual check: python3 -m ui.function.pup.remote.thumbnail_cache
if __name__ == "__main__":
    tc = ThumbnailCache()
    print(f"Enabled : {tc.enabled}")
    print(f"Budget  : {tc.max_bytes // (1024 * 1024)} MB")
    print(f"Size px : {tc.size_px}")
    print(f"Dir     : {CACHE_DIR}")
    print(f"Stats   : {tc.stats()}")
    print(f"CLI     : {tc.cli}")
    
    # Quick test (comment out unless you have an actual image path)
    # print("Testing download...")
    # pb = tc.get_sync("/Photos/test.jpg", 256)
    # print(f"Result: {pb}")
