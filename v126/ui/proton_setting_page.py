import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio
import os

from ui.config_manager import ConfigManager
from ui.file_browser import FileBrowserWindow


class SettingsPage:
    """Settings page where users configure upload destinations."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate
        self.config = ConfigManager.load()
        self._parent_window = None

    def build(self, parent_window=None):
        self._parent_window = parent_window

        # --- Entries ---
        self.entry_remote = Gtk.Entry()
        self.entry_remote.set_text(self.config["proton_drive_remote"])
        self.entry_remote.set_hexpand(True)

        self.entry_docs = Gtk.Entry()
        self.entry_docs.set_text(self.config["local_source_documents"])
        self.entry_docs.set_hexpand(True)

        self.entry_pics = Gtk.Entry()
        self.entry_pics.set_text(self.config["local_source_pictures"])
        self.entry_pics.set_hexpand(True)

        self.entry_cli = Gtk.Entry()
        self.entry_cli.set_text(self.config["cli_binary"])
        self.entry_cli.set_hexpand(True)

        # --- Build rows ---
        def build_row(title, subtitle, child):
            row = Adw.ActionRow()
            row.set_title(title)
            row.set_subtitle(subtitle)
            row.add_suffix(child)
            return row

        remote_row = build_row(
            "Proton Drive Destination",
            "Remote folder path on Drive (e.g. /my-files/Documents)",
            self.entry_remote,
        )

        docs_row = build_row(
            "Local Documents Path",
            "Where to upload Documents from",
            self._build_path_picker(self.entry_docs, "Documents"),
        )

        pics_row = build_row(
            "Local Pictures Path",
            "Where to upload Pictures from",
            self._build_path_picker(self.entry_pics, "Pictures"),
        )

        cli_row = build_row(
            "Proton Drive CLI Binary",
            "Path to the proton-drive executable",
            self.entry_cli,
        )

        # --- Preferences Group ---
        group = Adw.PreferencesGroup()
        group.set_title("Upload Configuration")
        group.set_description("Set where files upload to and from")
        group.add(remote_row)
        group.add(docs_row)
        group.add(pics_row)
        group.add(cli_row)

        # --- Save Button ---
        btn_save = Gtk.Button(label="Save Settings")
        btn_save.add_css_class("suggested-action")
        btn_save.set_size_request(400, -1)
        btn_save.connect("clicked", self._on_save_clicked)

        # --- Layout ---
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=15,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        container.append(group)
        container.append(btn_save)

        return container

    def _build_path_picker(self, entry, label):
        """Create a 'Browse...' button next to a text entry."""
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)

        btn = Gtk.Button(label="Browse…")
        btn.connect("clicked", lambda w: self._pick_folder(entry))
        box.append(btn)

        return box

    def _pick_folder(self, entry):
        """Open the file browser to pick a local folder."""
        if not self._parent_window:
            print("[Settings] No parent window for file browser")
            return

        browser = FileBrowserWindow(self._parent_window)

        def on_selected(window, filepath):
            entry.set_text(filepath)

        browser.connect("file-selected", on_selected)
        browser.present()

    def _on_save_clicked(self, widget):
        """Save all settings to config file."""
        self.config["proton_drive_remote"] = self.entry_remote.get_text()
        self.config["local_source_documents"] = self.entry_docs.get_text()
        self.config["local_source_pictures"] = self.entry_pics.get_text()
        self.config["cli_binary"] = self.entry_cli.get_text()

        success = ConfigManager.save(self.config)

        # Show toast on parent window
        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            msg = "✓ Settings saved!" if success else "✗ Failed to save settings"
            self._parent_window.add_toast(Adw.Toast(title=msg, timeout=3))
