#!/usr/bin/env python3
import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject


class FileBrowserWindow(Adw.Window):
    """A popup window that browses local files and folders."""

    __gsignals__ = {
        'file-selected': (GObject.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, parent_window, start_path=None, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Local Files")
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_default_size(700, 500)

        self.current_path = start_path or os.path.expanduser("~")
        self.selected_file = None

        self._build_ui()
        self._load_directory(self.current_path)

    def _build_ui(self):
        # --- Header Bar ---
        header = Adw.HeaderBar()
        self.set_content(
            self._create_content(header)
        )

    def _create_content(self, header):
        # Main vertical box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.append(header)

        # Path bar — shows current directory + back button
        path_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        path_bar.set_margin_start(12)
        path_bar.set_margin_end(12)
        path_bar.set_margin_top(8)
        path_bar.set_margin_bottom(8)

        self.btn_back = Gtk.Button(label="← Back")
        self.btn_back.connect("clicked", self._on_back)
        path_bar.append(self.btn_back)

        self.path_label = Gtk.Label(label=self.current_path, halign=Gtk.Align.START)
        self.path_label.set_ellipsize(3)  # PANGO_ELLIPSIZE_MIDDLE
        self.path_label.set_hexpand(True)
        path_bar.append(self.path_label)

        main_box.append(path_bar)

        # --- Scrolled window containing the file list ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        # Use a Gtk.ListView for the file grid
        self.list_model = Gio.ListStore.new(Gio.FileInfo)  # not used directly
        self.selection = Gtk.SingleSelection.new(Gio.ListStore.new(GObject.Object))

        # Instead, we'll use a simpler approach: a ListBox
        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._on_row_selected)

        scrolled.set_child(self.listbox)
        main_box.append(scrolled)

        # --- Bottom action bar ---
        action_bar = Gtk.ActionBar()
        action_bar.set_margin_start(12)
        action_bar.set_margin_end(12)

        self.btn_upload = Gtk.Button(label="Upload Selected")
        self.btn_upload.add_css_class("suggested-action")
        self.btn_upload.connect("clicked", self._on_upload_clicked)

        self.btn_close = Gtk.Button(label="Cancel")
        self.btn_close.connect("clicked", lambda w: self.destroy())

        action_bar.pack_end(self.btn_upload)
        action_bar.pack_start(self.btn_close)
        main_box.append(action_bar)

        return main_box

    def _load_directory(self, path):
        """Load and display files/folders at the given path."""
        self.current_path = path
        self.path_label.set_label(path)

        # Clear existing rows
        self.listbox.remove_all()

        try:
            entries = os.listdir(path)
            # Sort: directories first, then alphabetical
            entries.sort(key=lambda e: (not os.path.isdir(os.path.join(path, e)), e.lower()))

            for entry in entries:
                # Skip hidden files (optional)
                if entry.startswith('.'):
                    continue

                full_path = os.path.join(path, entry)
                row = self._create_row(entry, full_path, os.path.isdir(full_path))
                self.listbox.append(row)

        except PermissionError:
            error_label = Gtk.Label(label="⛔ Permission Denied")
            self.listbox.append(error_label)

    def _create_row(self, name, full_path, is_dir):
        """Create a single row for a file or folder."""
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(8)
        row.set_margin_bottom(8)

        # Icon
        if is_dir:
            icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        else:
            icon = Gtk.Image.new_from_icon_name("document-open-symbolic")

        row.append(icon)

        # Filename label
        label = Gtk.Label(label=name, halign=Gtk.Align.START)
        label.set_hexpand(True)
        row.append(label)

        # Store path data on the row widget for retrieval later
        list_row = Gtk.ListBoxRow()
        list_row.set_child(row)
        list_row.full_path = full_path
        list_row.is_dir = is_dir

        return list_row

    def _on_row_selected(self, listbox, row):
        if row is None:
            return

        self.selected_file = row.full_path

        # If it's a directory, navigate into it
        if row.is_dir:
            self._load_directory(row.full_path)

    def _on_back(self, widget):
        parent = os.path.dirname(self.current_path)
        if parent != self.current_path:  # Not at root
            self._load_directory(parent)

    def _on_upload_clicked(self, widget):
        if self.selected_file:
            print(f"[Upload] Selected: {self.selected_file}")
            # Emit signal so parent app can handle the upload
            self.emit("file-selected", self.selected_file)
            self.destroy()
        else:
            # Show a toast or message
            print("[Upload] No file selected")
