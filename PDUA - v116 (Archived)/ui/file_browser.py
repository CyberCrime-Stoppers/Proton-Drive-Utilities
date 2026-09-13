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
        header = Adw.HeaderBar()
        self.set_content(self._create_content(header))

    def _create_content(self, header):
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        main_box.append(header)

        path_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        path_bar.set_margin_start(12)
        path_bar.set_margin_end(12)
        path_bar.set_margin_top(8)
        path_bar.set_margin_bottom(8)

        self.btn_back = Gtk.Button(label="← Back")
        self.btn_back.connect("clicked", self._on_back)
        path_bar.append(self.btn_back)

        self.path_label = Gtk.Label(label=self.current_path, halign=Gtk.Align.START)
        self.path_label.set_ellipsize(3)
        self.path_label.set_hexpand(True)
        path_bar.append(self.path_label)

        main_box.append(path_bar)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_hexpand(True)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.listbox.connect("row-selected", self._on_row_selected)

        scrolled.set_child(self.listbox)
        main_box.append(scrolled)

        action_bar = Gtk.ActionBar()
        action_bar.set_margin_start(12)
        action_bar.set_margin_end(12)

        self.btn_upload = Gtk.Button(label="Select")
        self.btn_upload.add_css_class("suggested-action")
        self.btn_upload.connect("clicked", self._on_upload_clicked)
        self.btn_upload.set_sensitive(False)

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

        # Clear existing rows manually (FIXED: remove_all doesn't exist)
        while True:
            child = self.listbox.get_first_child()
            if child is None:
                break
            self.listbox.remove(child)

        try:
            entries = sorted(
                os.listdir(path),
                key=lambda e: (not os.path.isdir(os.path.join(path, e)), e.lower())
            )

            for entry in entries[:200]:
                if entry.startswith('.'):
                    continue

                full_path = os.path.join(path, entry)
                row = self._create_row(entry, full_path, os.path.isdir(full_path))
                self.listbox.append(row)

        except PermissionError:
            error_label = Gtk.Label(label="⛔ Permission Denied")
            self.listbox.append(error_label)

    def _create_row(self, name, full_path, is_dir):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        row.set_margin_start(12)
        row.set_margin_end(12)
        row.set_margin_top(8)
        row.set_margin_bottom(8)

        icon_name = "folder-symbolic" if is_dir else "document-open-symbolic"
        icon = Gtk.Image.new_from_icon_name(icon_name)
        row.append(icon)

        label = Gtk.Label(label=name, halign=Gtk.Align.START)
        label.set_hexpand(True)
        row.append(label)

        list_row = Gtk.ListBoxRow()
        list_row.set_child(row)
        list_row.full_path = full_path
        list_row.is_dir = is_dir

        return list_row

    def _on_row_selected(self, listbox, row):
        if row is None:
            return

        filepath = getattr(row, 'full_path', None)
        is_dir = getattr(row, 'is_dir', False)

        if filepath:
            self.selected_file = filepath
            self.btn_upload.set_sensitive(not is_dir)

            if is_dir:
                self._load_directory(filepath)
        else:
            self.btn_upload.set_sensitive(False)

    def _on_back(self, widget):
        parent = os.path.dirname(self.current_path)
        if parent != self.current_path:
            self._load_directory(parent)

    def _on_upload_clicked(self, widget):
        if self.selected_file:
            print(f"[Upload] Selected: {self.selected_file}")
            self.emit("file-selected", self.selected_file)
            self.destroy()
        else:
            print("[Upload] No file selected")
