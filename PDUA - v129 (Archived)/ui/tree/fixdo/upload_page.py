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

SCRIPTS_UP_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "scripts", "up")
SCRIPT_HASHES = {
    "proton-export-home-documents.sh":  "ac9962c9e230d928ff72c5f5bb18ff41c0e278ef7e7d50257ab9b14e76d2a046",
    "proton-export-home-pictures.sh":  "07aa8d1cb10e5f14a1f31cb9af18a45ee8c09639ad4b87982e34c7b590fc2a50",
    "proton-export-home-videos.sh":  "6ff6716ecd73bd1d2feac0795cdca782bcd017b0ee339cb4d3cac5d502c02386",
    "proton-export-home-music.sh":  "e4e9fe168e321a28778dc90fe5f06fe6e20f1b3761c9efbe2818f654c61810a2",
    "proton-export-home-downloads.sh": "e242ca129a166dbb81f1b440448f42284af0744f5d1df279630bd932d054e54d",
}

def validate_script(script_path):
    abs_path = os.path.abspath(script_path)
    expected_dir = os.path.abspath(SCRIPTS_UP_DIR)

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


class UploadPage:
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

        title = Gtk.Label(label="<span size='x-large' weight='bold'>Instructions to Upload</span>")
        title.set_use_markup(True)
        container.append(title)

        info = Gtk.Label(label=(
            "Click on any of these options to export your file onto your personal Proton Drive."
        ))
        info.add_css_class("dim-label")
        container.append(info)

        self.script_map = {
            "Documents": "proton-export-home-documents.sh",
            "Pictures":  "proton-export-home-pictures.sh",
            "Videos":    "proton-export-home-videos.sh",
            "Music":     "proton-export-home-music.sh",
            "Downloads": "proton-export-home-downloads.sh",
        }

        for folder_name in self.script_map.keys():
            btn = Gtk.Button(label=f"Export from Directory: {folder_name}")
            btn.set_size_request(400, -1)
            btn.connect("clicked", lambda w, fn=folder_name: self._run_script(fn))
            container.append(btn)

        return container

    def _run_script(self, folder_name):
        script_file = self.script_map.get(folder_name)
        if not script_file:
            log.warning("No script for: %s", folder_name)
            return

        script_path = os.path.join(SCRIPTS_UP_DIR, script_file)

        try:
            safe_path = validate_script(script_path)
        except (ValueError, FileNotFoundError, PermissionError) as e:
            msg = f"✗ Script validation failed: {e}"
            log.error(msg)
            if self._parent_window and hasattr(self._parent_window, "add_toast"):
                self._parent_window.add_toast(Adw.Toast(title=msg, timeout=5))
            return

        log.info("Running script: %s", safe_path)

        t = threading.Thread(
            target=self._execute_script,
            args=(safe_path, folder_name),
            daemon=True,
        )
        t.start()

    def _execute_script(self, script_path, folder_name):
        msg = ""
        try:
            result = subprocess.run(
                [script_path],
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.returncode == 0:
                msg = f"✓ {folder_name} uploaded successfully!"
                log.info("Success: %s", result.stdout.strip())
            else:
                msg = f"✗ {folder_name} upload failed: {result.stderr.strip()[:100]}"
                log.error("Failed: %s", result.stderr.strip())

        except subprocess.TimeoutExpired:
            msg = f"✗ {folder_name} upload timed out (>10 min)"
            log.error(msg)

        except FileNotFoundError:
            msg = f"✗ Script not found: {script_path}"
            log.error(msg)

        except PermissionError:
            msg = f"✗ Script not executable: {script_path}"
            log.error(msg)

        except Exception as e:
            msg = f"✗ Error: {e}"
            log.exception("Unexpected error")

        def show_result():
            if self._parent_window and hasattr(self._parent_window, "add_toast"):
                self._parent_window.add_toast(Adw.Toast(title=msg, timeout=5))
            return False  # ← CRITICAL

        GLib.idle_add(show_result)
