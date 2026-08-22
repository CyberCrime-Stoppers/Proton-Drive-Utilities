import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw
import subprocess
import os
import threading


class DownloadPage:
    """Download page with functional buttons."""

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
            " ''Click on any of these options to import files from your proton drive \nand it will grab your all of your file automaticly to the the directory \non your system *shown below''"
        ))
        info.add_css_class("dim-label")
        container.append(info)

        # --- Button: Download Documents ---
        btn_dcs = Gtk.Button(label="Import into Directory: Documents")
        btn_dcs.set_size_request(400, -1)
        btn_dcs.connect("clicked", lambda w: self._run_script(w, "Documents"))
        container.append(btn_dcs)

        # --- Button: Download Pictures ---
        btn_pcs = Gtk.Button(label="Import into Directory: Pictures")
        btn_pcs.set_size_request(400, -1)
        btn_pcs.connect("clicked", lambda w: self._run_script(w, "Pictures"))
        container.append(btn_pcs)

        # --- Button: Download Videos ---
        btn_vid = Gtk.Button(label="Import into Directory: Videos")
        btn_vid.set_size_request(400, -1)
        btn_vid.connect("clicked", lambda w: self._run_script(w, "Videos"))
        container.append(btn_vid)

        # --- Button: Download Music ---
        btn_mus = Gtk.Button(label="Import into Directory: Music")
        btn_mus.set_size_request(400, -1)
        btn_mus.connect("clicked", lambda w: self._run_script(w, "Music"))
        container.append(btn_mus)

        # --- Button: Download Downloads ---
        btn_dnld = Gtk.Button(label="Import into Directory: Downloads")
        btn_dnld.set_size_request(400, -1)
        btn_dnld.connect("clicked", lambda w: self._run_script(w, "Downloads"))
        container.append(btn_dnld)

        return container

    def _run_script(self, widget, folder_name):
        if folder_name == "Documents":
            script_path = "./scripts/down/prtn-drv-hme-dcs.sh"
        elif folder_name == "Pictures":
            script_path = "./scripts/down/prtn-drv-hme-pcs.sh"
        elif folder_name == "Videos":
            script_path = "./scripts/down/prtn-drv-hme-vid.sh"
        elif folder_name == "Music":
            script_path = "./scripts/down/prtn-drv-hme-mus.sh"
        elif folder_name == "Downloads":
            script_path = "./scripts/down/prtn-drv-hme-dnld.sh"
        else:
            print(f"[Unknown] No script for: {folder_name}")
            return

        print(f"[Script] Running {script_path}")

        t = threading.Thread(
            target=self._execute_script,
            args=(script_path, folder_name),
            daemon=True,
        )
        t.start()

    def _execute_script(self, script_path, folder_name):
        try:
            result = subprocess.run(
                [script_path],
                capture_output=True,  # ← FIXED: was False
                text=True,
            )

            if result.returncode == 0:
                msg = f"✓ {folder_name} downloaded successfully!"
                print(f"[Success] {result.stdout.strip()}")
            else:
                msg = f"✗ {folder_name} download failed: {result.stderr.strip()[:100]}"
                print(f"[Error] {result.stderr.strip()}")

        except FileNotFoundError:
            msg = f"✗ Script not found: {script_path}"
            print(msg)

        except Exception as e:
            msg = f"✗ Error: {e}"
            print(msg)

        def show_result():
            if self._parent_window and hasattr(self._parent_window, "add_toast"):
                self._parent_window.add_toast(Adw.Toast(title=msg, timeout=5))

        from gi.repository import GLib
        GLib.idle_add(show_result)
