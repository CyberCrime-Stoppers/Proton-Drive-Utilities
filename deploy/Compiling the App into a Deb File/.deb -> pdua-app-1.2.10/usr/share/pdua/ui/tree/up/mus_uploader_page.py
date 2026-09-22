import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw
import subprocess
import os
import threading


class MusUploaderPage:
    """Custom Uploader Music page with user-configurable paths."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate
        self._parent_window = None

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

        # --- Title ---
        title = Gtk.Label(
            label="<span size='xx-large' font='sans' weight='bold'>Upload Files</span>"
        )
        title.set_use_markup(True)
        container.append(title)

        subtitle = Gtk.Label(
            label="<span size='medium' color='#666666'>From Local Folder to Proton Drive</span>"
        )
        subtitle.set_use_markup(True)
        subtitle.add_css_class("dim-label")
        container.append(subtitle)

        # --- Local Source Path ---
        local_label = Gtk.Label(label="Local Source Folder:")
        local_label.set_halign(Gtk.Align.START)
        local_label.set_margin_top(10)
        container.append(local_label)

        local_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        local_box.set_size_request(400, -1)

        self.entry_local = Gtk.Entry()
        self.entry_local.set_placeholder_text("/")
        self.entry_local.set_text(os.path.expanduser("Click browse to choose a path to Upload into your proton drive"))
        self.entry_local.set_hexpand(True)
        local_box.append(self.entry_local)

        btn_browse = Gtk.Button(label="Browse…")
        btn_browse.connect("clicked", self._browse_local)
        local_box.append(btn_browse)

        container.append(local_box)

        # --- Proton Drive Remote Path ---
        remote_label = Gtk.Label(label="Already set to upload shown below")
        remote_label.set_halign(Gtk.Align.START)
        remote_label.set_margin_top(10)
        container.append(remote_label)

        self.entry_remote = Gtk.Entry()
        self.entry_remote.set_placeholder_text("/my-files/Music")
        self.entry_remote.set_text("/my-files/Music")
        self.entry_remote.set_size_request(400, -1)
        container.append(self.entry_remote)

        # --- CLI Binary Path ---
        cli_label = Gtk.Label(label="Proton Drive CLI Binary:")
        cli_label.set_halign(Gtk.Align.START)
        cli_label.set_margin_top(10)
        container.append(cli_label)

        cli_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cli_box.set_size_request(400, -1)

        self.entry_cli = Gtk.Entry()
        self.entry_cli.set_placeholder_text("/usr/bin/proton-drive")
        self.entry_cli.set_text("/usr/bin/proton-drive")
        self.entry_cli.set_hexpand(True)
        cli_box.append(self.entry_cli)

        btn_browse_cli = Gtk.Button(label="Browse…")
        btn_browse_cli.connect("clicked", self._browse_cli)
        cli_box.append(btn_browse_cli)

        container.append(cli_box)

        # --- Divider ---
        separator = Gtk.Separator()
        separator.set_margin_top(20)
        separator.set_margin_bottom(20)
        container.append(separator)

        upload_label = Gtk.Label(label="You are Uploading to Your Proton Drive")
        upload_label.set_use_markup(True)
        container.append(upload_label)

        info = Gtk.Label(label=(
            "Click Export to upload your files from your chosen directory to Proton Drive."
        ))
        info.add_css_class("dim-label")
        container.append(info)

        # --- Upload Button ---
        btn_custom = Gtk.Button(label="⬆ Export")
        btn_custom.set_size_request(400, -1)
        btn_custom.connect("clicked", lambda w: self._upload(w, "All"))
        container.append(btn_custom)

        return container

    def _browse_local(self, widget):
        """Open file browser to pick local source folder."""
        from ui.function.pup.file_browser import FileBrowserWindow

        if not self._parent_window:
            return

        browser = FileBrowserWindow(self._parent_window)

        def on_selected(window, filepath):
            self.entry_local.set_text(filepath)

        browser.connect("file-selected", on_selected)
        browser.present()

    def _browse_cli(self, widget):
        """Open file browser to pick CLI binary."""
        from ui.function.pup.file_browser import FileBrowserWindow

        if not self._parent_window:
            return

        browser = FileBrowserWindow(self._parent_window)

        def on_selected(window, filepath):
            self.entry_cli.set_text(filepath)

        browser.connect("file-selected", on_selected)
        browser.present()

    def _upload(self, widget, folder_type):
        """Trigger upload from local source to Proton Drive."""

        # Read values from UI entries
        local_base = os.path.expanduser(self.entry_local.get_text().strip())
        remote_base = self.entry_remote.get_text().strip()
        cli_binary = self.entry_cli.get_text().strip()

        # Validate inputs
        if not local_base:
            self._show_toast("✗ Enter a local source path")
            return
        if not remote_base:
            self._show_toast("✗ Enter a Proton Drive remote path")
            return
        if not cli_binary:
            self._show_toast("✗ Enter the CLI binary path")
            return

        # Map folder types
        if folder_type == "Documents":
            local_folder = os.path.join(local_base, "Documents")
            remote_folder = f"{remote_base}/Documents"
        elif folder_type == "Pictures":
            local_folder = os.path.join(local_base, "Pictures")
            remote_folder = f"{remote_base}/Pictures"
        elif folder_type == "All":
            local_folder = local_base
            remote_folder = remote_base
        else:
            print(f"[Unknown] No handler for: {folder_type}")
            return

        # Ensure local source exists
        if not os.path.exists(local_folder):
            self._show_toast(f"✗ Local path not found: {local_folder}")
            return

        print(f"[Upload] {local_folder} → {remote_folder}")

        # Toast: uploading
        self._show_toast(f"Uploading {folder_type}…")

        # Run in background thread
        t = threading.Thread(
            target=self._run_upload,
            args=(cli_binary, local_folder, remote_folder, folder_type),
            daemon=True,
        )
        t.start()

    def _run_upload(self, cli_binary, local_folder, remote_folder, folder_type):
        """Background thread: execute the proton-drive CLI upload."""
        from gi.repository import GLib

        cmd = [cli_binary, "filesystem", "upload", local_folder, remote_folder]
        print(f"[CLI] {' '.join(cmd)}")

        msg = ""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                msg = f"✓ {folder_type} uploaded successfully!"
                print(f"[Success] {result.stdout.strip()}")
            else:
                msg = f"✗ Upload failed: {result.stderr.strip()[:100]}"
                print(f"[Error] {result.stderr.strip()}")

        except FileNotFoundError:
            msg = f"✗ CLI not found at: {cli_binary}"
            print(msg)

        except subprocess.TimeoutExpired:
            msg = "✗ Upload timed out (>10 min)"
            print(msg)

        except Exception as e:
            msg = f"✗ Error: {e}"
            print(msg)

        # Show result toast on main thread
        def show_result():
            self._show_toast(msg, timeout=5)

        GLib.idle_add(show_result)

    def _show_toast(self, message, timeout=3):
        """Helper to show toast on parent window."""
        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            self._parent_window.add_toast(Adw.Toast(title=message, timeout=timeout))
