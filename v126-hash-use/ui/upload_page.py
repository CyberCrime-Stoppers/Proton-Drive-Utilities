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

SCRIPTS_UP_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts", "up")
SCRIPT_HASHES = {
    "prtn-drv-hme-dcs.sh":  "b4686a849e27b6ea7519e2c98d92052c79b3b2a24b861573e86a4c28a81889d8",
    "prtn-drv-hme-pcs.sh":  "e9d929426fa901dcf9b1e6c4f3cb08d40addf425a1042a760aba949597a6fa87",
    "prtn-drv-hme-vid.sh":  "0c02d4342266ae47acaf50e57e1edd2aa6d0bc0919325a9f93f3aed62c1d8d5a",
    "prtn-drv-hme-mus.sh":  "fd16ef21ec1b6ded91dc9d34e2323b5d9c38f399c0d7a089dd86d75ba004fdf1",
    "prtn-drv-hme-dnld.sh": "466be78915131f6d69f136b2eaad667e137a30a3da2e63beb3596dfb5895bb14",
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
            "Documents": "prtn-drv-hme-dcs.sh",
            "Pictures":  "prtn-drv-hme-pcs.sh",
            "Videos":    "prtn-drv-hme-vid.sh",
            "Music":     "prtn-drv-hme-mus.sh",
            "Downloads": "prtn-drv-hme-dnld.sh",
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
