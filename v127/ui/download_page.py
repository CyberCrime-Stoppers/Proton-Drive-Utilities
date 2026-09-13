import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw, GLib
import subprocess
import os
import threading
import stat
import hashlib
import logging

log = logging.getLogger("pdua")

SCRIPTS_DOWN_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts", "down")

# Generate real hashes with: sha256sum scripts/down/prtn-drv-hme-*.sh
SCRIPT_HASHES = {
    "prtn-drv-hme-dcs.sh":  "ea3243788a9fd4dfc34f3e3963bf0105514b2f126c5cdbad37e8c7522e5304ff",
    "prtn-drv-hme-pcs.sh":  "dc684e1c7013c327dfbf2d98d4804e6f51ff7978f31e9639f80e0ffaa8a9899f",
    "prtn-drv-hme-vid.sh":  "a8bf34dc2fd1e0047c9e28ce1592e4b44c254015fff687c56fe5a87f003b4946",
    "prtn-drv-hme-mus.sh":  "f845328a9613c9eb1d4f0fb54c215d85eff39ee15383cb42b1a5153fd6892bc1",
    "prtn-drv-hme-dnld.sh": "f2bd0bfc8ae7bde9b754266bba3a6acede53c9547bdd4005902c75729cbfd119",
}


def validate_script(script_path):
    """Validate script path, permissions, and integrity."""
    abs_path = os.path.abspath(script_path)
    expected_dir = os.path.abspath(SCRIPTS_DOWN_DIR)

    # Path traversal protection
    if not abs_path.startswith(expected_dir):
        raise ValueError("Script path outside allowed directory")

    if not os.path.exists(abs_path):
        raise FileNotFoundError(f"Script not found: {script_path}")

    mode = os.stat(abs_path).st_mode
    if not (mode & stat.S_IXUSR):
        raise PermissionError(f"Script not executable: {script_path}")

    with open(abs_path, "rb") as f:
        actual_hash = hashlib.sha256(f.read()).hexdigest()

    if actual_hash != SCRIPT_HASHES.get(os.path.basename(script_path)):
        raise ValueError("Script integrity check failed")

    return abs_path


class DownloadPage:
    """Download page with functional buttons."""

    SCRIPT_MAP = {
        "Documents": "prtn-drv-hme-dcs.sh",
        "Pictures":  "prtn-drv-hme-pcs.sh",
        "Videos":    "prtn-drv-hme-vid.sh",
        "Music":     "prtn-drv-hme-mus.sh",
        "Downloads": "prtn-drv-hme-dnld.sh",
    }

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate

    def build(self, parent_window=None):
        self._parent_window = parent_window

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=15,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        title = Gtk.Label(label="<span size='x-large' weight='bold'>Instructions to Download</span>")
        title.set_use_markup(True)
        container.append(title)

        info = Gtk.Label(label=(
            "Click on any of these options to import files from your Proton Drive "
            "to the corresponding directory on your system."
        ))
        info.add_css_class("dim-label")
        container.append(info)

        # Create buttons dynamically from SCRIPT_MAP
        for folder_name in self.SCRIPT_MAP.keys():
            btn = Gtk.Button(label=f"Import into Directory: {folder_name}")
            btn.set_size_request(400, -1)
            btn.connect("clicked", lambda w, fn=folder_name: self._run_script(fn))
            container.append(btn)

        return container

    def _run_script(self, folder_name):
        """Validate and start script execution thread."""
        script_file = self.SCRIPT_MAP.get(folder_name)
        if not script_file:
            log.warning("No script for: %s", folder_name)
            return

        script_path = os.path.join(SCRIPTS_DOWN_DIR, script_file)

        # Validate BEFORE spawning thread — fail fast
        try:
            safe_path = validate_script(script_path)
        except (ValueError, FileNotFoundError, PermissionError) as e:
            msg = f"✗ Script validation failed: {e}"
            log.error(msg)
            if self._parent_window and hasattr(self._parent_window, "add_toast"):
                self._parent_window.add_toast(Adw.Toast(title=msg, timeout=5))
            return

        log.info("Running download script: %s", safe_path)

        t = threading.Thread(
            target=self._execute_script,
            args=(safe_path, folder_name),
            daemon=True,
        )
        t.start()

    def _execute_script(self, script_path, folder_name):
        """Execute script in background thread."""
        msg = ""
        try:
            result = subprocess.run(
                [script_path],
                capture_output=True,
                text=True,
                timeout=600,  # ← FIXED: prevent hanging
            )

            if result.returncode == 0:
                msg = f"✓ {folder_name} downloaded successfully!"
                log.info("Success: %s", result.stdout.strip())
            else:
                msg = f"✗ {folder_name} download failed: {result.stderr.strip()[:100]}"
                log.error("Failed: %s", result.stderr.strip())

        except subprocess.TimeoutExpired:
            msg = f"✗ {folder_name} download timed out (>10 min)"
            log.error(msg)

        except FileNotFoundError:
            msg = f"✗ Script not found: {script_path}"
            log.error(msg)

        except PermissionError:
            msg = f"✗ Script not executable: {script_path}"
            log.error(msg)

        except Exception as e:
            msg = f"✗ Error: {e}"
            log.exception("Unexpected error during download")

        # Show result toast — CRITICAL: return False to stop idle recurrence
        def show_result():
            if self._parent_window and hasattr(self._parent_window, "add_toast"):
                self._parent_window.add_toast(Adw.Toast(title=msg, timeout=5))
            return False  # ← FIXED: stops infinite loop

        GLib.idle_add(show_result)
