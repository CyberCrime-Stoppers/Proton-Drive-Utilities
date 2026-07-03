import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw
import subprocess


class UploadPage:
    """Home page with functional buttons."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate

    def build(self):
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=20,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        # --- Button: Upload Documents ---
        btn_dcs = Gtk.Button(label="Upload Home Directory: Documents")
        btn_dcs.set_size_request(400, -1)
        btn_dcs.connect("clicked", lambda w: self._run_script(w, "Documents"))
        container.append(btn_dcs)

        # --- Button: Upload Pictures ---
        btn_pcs = Gtk.Button(label="Upload Home Directory: Pictures")
        btn_pcs.set_size_request(400, -1)
        btn_pcs.connect("clicked", lambda w: self._run_script(w, "Pictures"))
        container.append(btn_pcs)

        # --- Button: Upload Pictures ---
        btn_vid = Gtk.Button(label="Upload Home Directory: Videos")
        btn_vid.set_size_request(400, -1)
        btn_vid.connect("clicked", lambda w: self._run_script(w, "Videos"))
        container.append(btn_vid)

        # --- Button: Upload Pictures ---
        btn_mus = Gtk.Button(label="Upload Home Directory: Music")
        btn_mus.set_size_request(400, -1)
        btn_mus.connect("clicked", lambda w: self._run_script(w, "Music"))
        container.append(btn_mus)

        # --- Button: Upload Pictures ---
        btn_dnld = Gtk.Button(label="Upload Home Directory: Downloads")
        btn_dnld.set_size_request(400, -1)
        btn_dnld.connect("clicked", lambda w: self._run_script(w, "Downloads"))
        container.append(btn_dnld)


        return container

    def _run_script(self, widget, folder_name):

        if folder_name == "Documents":
            script_path = "./scripts/prtn-drv-hme-dcs.sh"
        elif folder_name == "Pictures":
            script_path = "./scripts/prtn-drv-hme-pcs.sh"
        elif folder_name == "Videos":
            script_path = "./scripts/prtn-drv-hme-vid.sh"
        elif folder_name == "Music":
            script_path = "./scripts/prtn-drv-hme-mus.sh"
        elif folder_name == "Downloads":
            script_path = "./scripts/prtn-drv-hme-dnld.sh"
        else:
            print(f"[Unknown] No script for: {folder_name}")
            return

        try:
            print(f"[Script] Running {script_path}")
            result = subprocess.run(
                [script_path],
                capture_output=True,  # FIXED: was False
                text=True,
            )

            if result.returncode == 0:
                print(f"✓ {folder_name} script ran successfully")
                print(result.stdout)
            else:
                print(f"✗ {folder_name} script failed (exit {result.returncode})")
                print(result.stderr)

        except subprocess.TimeoutExpired:
            print(f"✗ {folder_name} script timed out")
        except FileNotFoundError:
            print(f"✗ Script not found: {script_path}")
        except Exception as e:
            print(f"✗ Error: {e}")
