#!/usr/bin/env python3
"""
Album Explorer Page - Browse albums in Proton Drive /photos directory
Displays custom icons for each album
"""

import os
import subprocess
import threading
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib


class AlbumExplorerPage:
    """Page to browse and manage albums stored in Proton Drive."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate
        self._parent_window = None
        self.current_path = "/Albums"
        self.albums = []
        self.selected_album = None

        self.config = {
            "photos_root": "/Albums",
            "cli_binary": "proton-drive",
        }

    def build(self, parent_window=None):
        """Build the album explorer UI."""
        self._parent_window = parent_window

        main_scroll = Gtk.ScrolledWindow()
        main_scroll.set_vexpand(False)
        main_scroll.set_hexpand(False)

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_start=24,
            margin_end=24,
            margin_top=24,
            margin_bottom=24,
        )

        # --- Header Section ---
        header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=16,
        )

        title = Gtk.Label(
            label="<span size='x-large' weight='bold'>🖼️ Album Explorer</span>"
        )
        title.set_use_markup(True)
        title.set_halign(Gtk.Align.START)
        title.set_hexpand(True)
        header_box.append(title)

        refresh_btn = Gtk.Button()
        refresh_btn.set_icon_name("view-refresh-symbolic")
        refresh_btn.add_css_class("flat")
        refresh_btn.set_tooltip_text("Refresh Albums")
        refresh_btn.connect("clicked", self._refresh_albums)
        header_box.append(refresh_btn)

        home_btn = Gtk.Button(label="🏠 Home")
        home_btn.add_css_class("flat")
        home_btn.connect("clicked", self._go_home)
        header_box.append(home_btn)

        container.append(header_box)

        # --- Path Navigation ---
        path_bar = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
        )
        path_bar.set_margin_bottom(12)

        self.path_label = Gtk.Label(
            label=f"📁 {self.current_path}",
            halign=Gtk.Align.START,
            hexpand=True,
        )
        self.path_label.add_css_class("heading")
        path_bar.append(self.path_label)

        container.append(path_bar)

        # --- Status Label ---
        self.status_label = Gtk.Label(
            label="Click refresh to load albums from Proton Drive…",
            halign=Gtk.Align.CENTER,
            margin_top=8,
            margin_bottom=8,
        )
        self.status_label.add_css_class("dim-label")
        container.append(self.status_label)

        # --- Album Grid ---
        self.album_flowbox = Gtk.FlowBox()
        self.album_flowbox.set_vexpand(True)
        self.album_flowbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.album_flowbox.set_min_children_per_line(2)
        self.album_flowbox.set_max_children_per_line(4)
        self.album_flowbox.set_row_spacing(16)
        self.album_flowbox.set_column_spacing(16)
        # ✅ Correct GTK4 signal name
        self.album_flowbox.connect("selected-children-changed", self._on_album_selected)

        container.append(self.album_flowbox)

        # --- Action Buttons ---
        action_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=16,
        )

        self.view_btn = Gtk.Button(label="👁 View Selected Album")
        self.view_btn.add_css_class("suggested-action")
        self.view_btn.set_sensitive(False)
        self.view_btn.connect("clicked", self._view_album)
        action_box.append(self.view_btn)

        self.delete_btn = Gtk.Button(label="🗑 Delete Selected")
        self.delete_btn.add_css_class("destructive-action")
        self.delete_btn.set_sensitive(False)
        self.delete_btn.connect("clicked", self._delete_album)
        action_box.append(self.delete_btn)

        container.append(action_box)

        main_scroll.set_child(container)

        # Load albums automatically when page is built
        self._refresh_albums()

        return main_scroll

    # ===== ALBUM LOADING =====

    def _refresh_albums(self, widget=None):
        """Reload albums from Proton Drive /photos directory."""
        self.status_label.set_text("Loading albums from Proton Drive…")
        self.album_flowbox.remove_all()
        self.view_btn.set_sensitive(False)
        self.delete_btn.set_sensitive(False)

        t = threading.Thread(target=self._load_albums_cli, daemon=True)
        t.start()

    def _load_albums_cli(self):
        """Fetch album list from Proton Drive CLI in background thread."""
        try:
            cli = self._get_cli_path()
            cmd = [cli, "album", "list", self.config["photos_root"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

            if result.returncode == 0:
                albums = self._parse_album_list(result.stdout)
                GLib.idle_add(self._display_albums, albums)
            else:
                error_msg = result.stderr.strip() or "Unknown error"
                GLib.idle_add(self._show_error, f"Failed to load albums: {error_msg}")

        except FileNotFoundError:
            GLib.idle_add(self._show_error,
                "Proton Drive CLI not found.\nInstall from: https://proton.me/drive/download")
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._show_error, "Connection timed out")
        except Exception as e:
            GLib.idle_add(self._show_error, f"Error: {str(e)}")

    def _get_cli_path(self):
        """Find proton-drive CLI binary."""
        candidates = [
            "/usr/bin/proton-drive",
            "/usr/local/bin/proton-drive",
            os.path.expanduser("~/.local/bin/proton-drive"),
        ]
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return "proton-drive"  # Fall back to PATH lookup

    def _parse_album_list(self, output):
        """Parse CLI output into album list."""
        albums = []
        for line in output.strip().split('\n'):
            line = line.strip()
            if not line or line.startswith('total'):
                continue

            parts = line.split()
            if parts:
                name = parts[-1]
                if name in ('.', '..'):
                    continue
                albums.append({
                    "name": name,
                    "path": f"{self.current_path}/{name}",
                    "is_dir": False,
                })
        return albums

    # ===== UI DISPLAY =====

    def _display_albums(self, albums):
        """Display loaded albums in the flowbox on main thread."""
        self.albums = albums
        self.album_flowbox.remove_all()

        if not albums:
            self.status_label.set_text(f"📭 No albums found in {self.current_path}")
            return

        self.status_label.set_text(f"Found {len(albums)} album(s)")

        for album in albums:
            self.album_flowbox.append(self._create_album_widget(album))

    def _create_album_widget(self, album):
        """Create a single album card widget with custom icon."""
        card = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=8,
            margin_start=4,
            margin_end=4,
            margin_top=4,
            margin_bottom=4,
        )
        card.set_size_request(160, 180)
        card.add_css_class("card")

        # Album icon using the icon resolver
        folder_icon = Gtk.Image.new_from_icon_name(self._get_album_icon(album["name"]))
        folder_icon.set_pixel_size(48)
        folder_icon.set_vexpand(True)
        folder_icon.set_valign(Gtk.Align.CENTER)
        card.append(folder_icon)

        # Album name
        name_label = Gtk.Label(
            label=album["name"],
            ellipsize=3,  # PANGO_ELLIPSIZE_MIDDLE
            halign=Gtk.Align.CENTER,
        )
        name_label.add_css_class("caption")
        card.append(name_label)

        # Store album data on widget for retrieval
        card.album_data = album
        return card

    def _get_album_icon(self, name):
        """Resolve album icon by name, with availability-aware fallback."""
        name_lower = name.lower()

        keywords = [
            (("vacation", "travel", "trip"),  "album-vacation-symbolic"),
            (("family", "kids", "children"),  "album-family-symbolic"),
            (("wedding", "engagement"),       "album-wedding-symbolic"),
            (("birthday", "party"),           "album-birthday-symbolic"),
            (("nature", "outdoor"),           "album-nature-symbolic"),
            (("work", "project"),             "album-work-symbolic"),
        ]

        theme = None
        try:
            theme = Gtk.IconTheme.get_for_display(
                self.album_flowbox.get_display()
            ) if self.album_flowbox else None
        except Exception:
            pass  # Silently skip if display not ready yet

        FALLBACK = "folder-pictures-symbolic"

        for keys, icon_name in keywords:
            if any(k in name_lower for k in keys):
                return icon_name  # themed name — GTK resolves it, falling back gracefully

        return FALLBACK

    # ===== USER INTERACTION =====

    def _on_album_selected(self, flowbox):
        """Handle FlowBox selection change."""
        selected = flowbox.get_selected_children()

        if not selected:
            self.selected_album = None
            self.view_btn.set_sensitive(False)
            self.delete_btn.set_sensitive(False)
            self.status_label.set_text("No album selected")
            return

        child = selected[0]
        if hasattr(child.get_child(), 'album_data'):
            self.selected_album = child.get_child().album_data
            self.view_btn.set_sensitive(True)
            self.delete_btn.set_sensitive(True)
            self.status_label.set_text(f"Selected: {self.selected_album['name']}")

    def _view_album(self, widget):
        """View selected album contents."""
        if not self.selected_album:
            return

        print(f"[Album Explorer] Viewing: {self.selected_album['path']}")

        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            self._parent_window.add_toast(
                Adw.Toast(title=f"Opening {self.selected_album['name']}…", timeout=2)
            )

        # TODO: Navigate to album detail view

    def _delete_album(self, widget):
        """Delete selected album (with confirmation)."""
        if not self.selected_album:
            return

        dialog = Adw.MessageDialog(
            transient_for=self._parent_window,
            heading="Delete Album?",
            body=(f"Are you sure you want to delete '{self.selected_album['name']}'?\n\n"
                  "This will permanently remove the album and all photos from Proton Drive."),
        )

        dialog.add_response("cancel", "Cancel")
        dialog.add_response("delete", "Delete")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")
        dialog.set_close_response("cancel")
        dialog.connect("response", self._confirm_delete)
        dialog.present()

    def _confirm_delete(self, dialog, response):
        if response == "delete" and self.selected_album:
            self.status_label.set_text(f"Deleting {self.selected_album['name']}…")
            t = threading.Thread(
                target=self._run_delete,
                args=(self.selected_album,),
                daemon=True,
            )
            t.start()

    def _run_delete(self, album):
        try:
            cli = self._get_cli_path()
            cmd = [cli, "filesystem", "rm", "-r", album["path"]]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                GLib.idle_add(self._show_result, f"✓ Deleted {album['name']}")
                GLib.idle_add(self._refresh_albums)
            else:
                error = result.stderr.strip() or "Unknown error"
                GLib.idle_add(self._show_result, f"✗ Delete failed: {error}")
        except Exception as e:
            GLib.idle_add(self._show_result, f"✗ Error: {str(e)}")

    def _show_result(self, message):
        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            self._parent_window.add_toast(Adw.Toast(title=message, timeout=3))
        self.status_label.set_text(message)

    def _show_error(self, message):
        self.status_label.set_text(f"✗ {message}")

    def _go_home(self, widget):
        if self.on_navigate:
            self.on_navigate("home")
