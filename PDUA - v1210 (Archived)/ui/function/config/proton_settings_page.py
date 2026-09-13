import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio
import os
from ui.function.config_manager import ConfigManager
from ui.function.pup.file_browser import FileBrowserWindow


class ProtonSettingsPage:
    """Settings page where users configure upload destinations."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate
        self.config = ConfigManager.load()
        self._parent_window = None

    def build(self, parent_window=None):
        self._parent_window = parent_window

        self.entry_remote_myfiles = Gtk.Entry()
        self.entry_remote_myfiles.set_text(self.config["proton_drive_myfiles_remote"])
        self.entry_remote_myfiles.set_hexpand(True)

        self.entry_remote_albums = Gtk.Entry()
        self.entry_remote_albums.set_text(self.config["proton_drive_albums_remote"])
        self.entry_remote_albums.set_hexpand(True)

        self.entry_remote_photos = Gtk.Entry()
        self.entry_remote_photos.set_text(self.config["proton_drive_photos_remote"])
        self.entry_remote_photos.set_hexpand(True)

        self.entry_remote_trash = Gtk.Entry()
        self.entry_remote_trash.set_text(self.config["proton_drive_trash_remote"])
        self.entry_remote_trash.set_hexpand(True)

        # --- Entries ID A/1 --- File Explorer windowing ---

        self.entry_myfiles = Gtk.Entry()
        self.entry_myfiles.set_text(self.config["local_source_myfiles"])
        self.entry_myfiles.set_hexpand(True)

        self.entry_albums = Gtk.Entry()
        self.entry_albums.set_text(self.config["local_source_albums"])
        self.entry_albums.set_hexpand(True)

        self.entry_photos = Gtk.Entry()
        self.entry_photos.set_text(self.config["local_source_photos"])
        self.entry_photos.set_hexpand(True)

        self.entry_trash = Gtk.Entry()
        self.entry_trash.set_text(self.config["local_source_trash"])
        self.entry_trash.set_hexpand(True)

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

    # --- Entries ID A/0 --- Proton Side Panel Sub Directories

        remote_myfiles_row = build_row(
            "Proton Drive Destination",
            "Remote folder path on Drive (e.g. /my-files/Documents)",
            self.entry_remote_myfiles,
        )

        remote_albums_row = build_row(
            "Proton Drive Destination",
            "Remote folder path on Drive (e.g. /album/)",
            self.entry_remote_albums,
        )

        remote_photos_row = build_row(
            "Proton Drive Destination",
            "Remote folder path on Drive (e.g. /album/)",
            self.entry_remote_photos,
        )

        remote_trash_row = build_row(
            "Proton Drive Destination",
            "Remote folder path on Drive (e.g. /trash/)",
            self.entry_remote_trash,
        )

        # --- Entries ID A/1 --- File Explorer windowing

        myfiles_row = build_row(
            "Local Files",
            "Where to upload my phoeos",
            self._build_path_picker(self.entry_myfiles, "/"),
        )

        albums_row = build_row(
            "Local Photos Path",
            "Where to upload my Photos to",
            self._build_path_picker(self.entry_albums, "/"),
        )

        photos_row = build_row(
            "Local Photos Path",
            "Where to upload my Photos to",
            self._build_path_picker(self.entry_photos, "/"),
        )

        # --- Entries ID A/1 --- File Explorer windowing

        trash_row = build_row(
            "Local Pictures Path",
            "Where to upload Pictures from",
            self._build_path_picker(self.entry_trash, "/"),
        )

        cli_row = build_row(
            "Proton Drive CLI Binary",
            "Path to the proton-drive executable",
            self.entry_cli,
        )
        # --- Preferences Group ---
        group = Adw.PreferencesGroup()
        group.set_title("Configure your Proton Drive")
        group.set_description("Set where you want yo upload \n\n My Files | Computers | Photos | Shared | Shared with me | Trash ")
        group.set_halign(Gtk.Align.START)
        group.add(remote_myfiles_row)
        group.add(remote_albums_row)
        group.add(remote_photos_row)
        group.add(remote_trash_row)
        group.add(myfiles_row)
        group.add(albums_row)
        group.add(photos_row)
        group.add(trash_row)
        group.add(cli_row)

        # --- Save Button ---
        btn_save = Gtk.Button(label="Save Settings")
        btn_save.add_css_class("suggested-action")
        btn_save.set_size_request(400, -1)
        btn_save.connect("clicked", self._on_save_clicked)

        # --- Layout ---
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
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
        self.config["proton_drive_myfiles_remote"] = self.entry_remote_myfiles.get_text()
        self.config["proton_drive_albums_remote"] = self.entry_remote_albums.get_text()
        self.config["proton_drive_photos_remote"] = self.entry_remote_photos.get_text()
        self.config["proton_drive_trash_remote"] = self.entry_remote_trash.get_text()
        self.config["local_source_myfiles"] = self.entry_myfiles.get_text()
        self.config["local_source_albums"] = self.entry_albums.get_text()
        self.config["local_source_photos"] = self.entry_photos.get_text()
        self.config["local_source_trash"] = self.entry_trash.get_text()
        self.config["cli_binary"] = self.entry_cli.get_text()
        success = ConfigManager.save(self.config)

        # Show toast on parent window
        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            msg = "✓ Settings saved!" if success else "✗ Failed to save settings"
            self._parent_window.add_toast(Adw.Toast(title=msg, timeout=3))
