#!/usr/bin/env python3
"""
Proton Settings Page — with BULK Import/Export + Progress Bar
===============================================================
NEW FEATURES (Linus's request):
  - "Import Everything" button (download) — one click, syncs ALL listed folders
  - "Export Everything" button (upload) — one click, syncs ALL listed folders
  - Live progress bar with % and per-folder status text
  - Cancel button to abort mid-operation
  - Buttons disable during operation to prevent double-starts

Each folder listed in the Local Folders / Proton Drive Destinations groups
gets synced: local <-> remote, using the unified TransferPage's runner
so progress/cancel handling stays consistent.
"""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
import os
import threading
import subprocess
from gi.repository import Gtk, Adw, GLib

from ui.function.config_manager import ConfigManager
from ui.function.pup.file_browser import FileBrowserWindow


class SyncCenterPage:
    """Settings page with per-folder config AND one-click bulk import/export."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate
        self.config_manager = ConfigManager()
        self.config = self.config_manager.load()
        self._parent_window = None

        # Bulk-transfer state
        self._transfer_thread = None
        self._cancel_event = threading.Event()
        self._busy = False
        self.cli_path = ConfigManager.find_cli(None)

    def build(self, parent_window=None):
        self._parent_window = parent_window

        # ---------- Entries (same as before) ----------
        self.entry_remote_myfiles = self._make_entry("proton_drive_myfiles_remote")
        self.entry_remote_albums = self._make_entry("proton_drive_albums_remote")
        self.entry_remote_photos = self._make_entry("proton_drive_photos_remote")
        self.entry_remote_trash = self._make_entry("proton_drive_trash_remote")
        self.entry_myfiles = self._make_entry("local_source_myfiles")
        self.entry_albums = self._make_entry("local_source_albums")
        self.entry_photos = self._make_entry("local_source_photos")
        self.entry_trash = self._make_entry("local_source_trash")
        self.entry_cli = Gtk.Entry()
        self.entry_cli.set_text(self.config.get("cli_binary") or "")
        self.entry_cli.set_placeholder_text("Auto-detected if empty")
        self.entry_cli.set_hexpand(True)

        # ---------- GROUP: Bulk Sync Actions (NEW) ----------
        sync_group = Adw.PreferencesGroup()
        sync_group.set_title("Sync Actions")
        sync_group.set_description("One-click transfer of everything listed below")

        # Progress bar
        self.progress_bar = Gtk.ProgressBar()
        self.progress_bar.set_hexpand(True)
        self.progress_bar.set_fraction(0.0)
        self.progress_bar.set_show_text(True)
        self.progress_bar.set_text("Ready")

        progress_row = Adw.ActionRow(title="Progress")
        progress_row.add_suffix(self.progress_bar)
        sync_group.add(progress_row)

        # Status label
        self.status_label = Gtk.Label(label="Idle")
        self.status_label.add_css_class("dim-label")
        self.status_label.set_halign(Gtk.Align.START)
        status_row = Adw.ActionRow(title="Current Operation")
        status_row.add_suffix(self.status_label)
        sync_group.add(status_row)

        # Import + Export buttons (side by side)
        button_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        button_box.set_valign(Gtk.Align.CENTER)
        button_box.set_size_request(340, -1)

        self.btn_import = Gtk.Button(label="⬇  Import (Download)")
        self.btn_import.add_css_class("suggested-action")
        self.btn_import.set_hexpand(True)
        self.btn_import.connect("clicked", self._on_import_clicked)

        self.btn_export = Gtk.Button(label="⬆  Export (Upload)")
        self.btn_export.add_css_class("suggested-action")
        self.btn_export.set_hexpand(True)
        self.btn_export.connect("clicked", self._on_export_clicked)

        self.btn_cancel = Gtk.Button(label="✕  Cancel")
        self.btn_cancel.add_css_class("destructive-action")
        self.btn_cancel.set_sensitive(False)
        self.btn_cancel.connect("clicked", self._on_cancel_clicked)

        button_box.append(self.btn_import)
        button_box.append(self.btn_export)
        button_box.append(self.btn_cancel)

        action_row = Adw.ActionRow(title="Bulk Transfer")
        action_row.set_subtitle("Transfers every folder pair listed in this page's settings")
        action_row.add_suffix(button_box)
        sync_group.add(action_row)

        # ---------- Remote destinations group ----------
        remote_group = Adw.PreferencesGroup()
        remote_group.set_title("Proton Drive Destinations")
        remote_group.set_description("Remote folders on your Proton Drive")
        remote_group.add(self._row("My Files", "e.g. /my-files", self.entry_remote_myfiles))
        remote_group.add(self._row("Albums", "e.g. /albums", self.entry_remote_albums))
        remote_group.add(self._row("Photos", "e.g. /photos", self.entry_remote_photos))
        remote_group.add(self._row("Trash", "e.g. /trash", self.entry_remote_trash))

        # ---------- Local folders group ----------
        local_group = Adw.PreferencesGroup()
        local_group.set_title("Local Folders")
        local_group.set_description("Where files are read from (Export) or saved to (Import)")
        local_group.add(self._row("My Files", "Local folder for general transfers", self._picker_box(self.entry_myfiles)))
        local_group.add(self._row("Albums", "Local folder for album transfers", self._picker_box(self.entry_albums)))
        local_group.add(self._row("Photos", "Local folder for photo transfers", self._picker_box(self.entry_photos)))
        local_group.add(self._row("Trash", "Local folder for trashed items", self._picker_box(self.entry_trash)))

        # ---------- CLI group ----------
        cli_group = Adw.PreferencesGroup()
        cli_group.set_title("Advanced")
        cli_group.add(self._row("Proton Drive CLI Binary", "Leave empty to auto-detect", self.entry_cli))

        # ---------- Save ----------
        btn_save = Gtk.Button(label="Save Settings")
        btn_save.add_css_class("suggested-action")
        btn_save.set_size_request(400, -1)
        btn_save.set_halign(Gtk.Align.CENTER)
        btn_save.connect("clicked", self._on_save_clicked)

        # ---------- Layout ----------
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL, spacing=18,
            margin_top=20, margin_bottom=20, margin_start=20, margin_end=20,
        )
        container.append(sync_group)      # actions FIRST — most-used section on top
        container.append(remote_group)
        container.append(local_group)
        container.append(cli_group)
        container.append(btn_save)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(container)
        return scrolled

    # ================= HELPERS =================

    def _make_entry(self, config_key):
        entry = Gtk.Entry()
        entry.set_text(str(self.config.get(config_key, "")))
        entry.set_hexpand(True)
        return entry

    @staticmethod
    def _row(title, subtitle, suffix_widget):
        row = Adw.ActionRow()
        row.set_title(title)
        row.set_subtitle(subtitle)
        row.add_suffix(suffix_widget)
        return row

    def _picker_box(self, entry):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        box.set_size_request(320, -1)
        entry.set_hexpand(True)
        box.append(entry)
        btn = Gtk.Button(label="Browse…")
        btn.connect("clicked", lambda w: self._pick_folder(entry))
        box.append(btn)
        return box

    def _pick_folder(self, entry):
        if not self._parent_window:
            return
        start = entry.get_text().strip() or None
        browser = FileBrowserWindow(self._parent_window, start_path=start)
        browser.connect("file-selected", lambda w, p: entry.set_text(p))
        browser.present()

    # ================= BULK TRANSFER =================

    def _folder_pairs(self):
        """All configured (local, remote) pairs, skipping empty ones."""
        pairs = []
        for local_entry, remote_entry in [
            (self.entry_myfiles, self.entry_remote_myfiles),
            (self.entry_albums, self.entry_remote_albums),
            (self.entry_photos, self.entry_remote_photos),
            (self.entry_trash, self.entry_remote_trash),
        ]:
            local = os.path.expanduser(local_entry.get_text().strip())
            remote = remote_entry.get_text().strip()
            if local and remote:
                pairs.append((local, remote))
        return pairs

    def _on_import_clicked(self, widget):
        self._start_bulk("download")

    def _on_export_clicked(self, widget):
        self._start_bulk("upload")

    def _on_cancel_clicked(self, widget):
        self._cancel_event.set()
        self.status_label.set_text("Cancelling…")
        self.btn_cancel.set_sensitive(False)

    def _start_bulk(self, direction):
        if self._busy:
            return

        cli = self.entry_cli.get_text().strip() or self.cli_path
        if not cli:
            self._toast("⚠ proton-drive CLI not found — set it in Advanced")
            return

        pairs = self._folder_pairs()
        if not pairs:
            self._toast("⚠ No complete folder pairs configured — set local + remote paths")
            return

        self._busy = True
        self._cancel_event.clear()
        self.btn_import.set_sensitive(False)
        self.btn_export.set_sensitive(False)
        self.btn_cancel.set_sensitive(True)

        verb = "Importing (download)" if direction == "download" else "Exporting (upload)"
        self.status_label.set_text(f"{verb}: starting…")
        self.progress_bar.set_fraction(0.0)

        self._transfer_thread = threading.Thread(
            target=self._bulk_worker,
            args=(cli, direction, pairs),
            daemon=True,
        )
        self._transfer_thread.start()

    def _bulk_worker(self, cli, direction, pairs):
        """Runs in background thread. NEVER touches GTK directly."""
        verb_flag = "download" if direction == "download" else "upload"
        total = len(pairs)
        failures = []

        for index, (local, remote) in enumerate(pairs):
            if self._cancel_event.is_set():
                GLib.idle_add(self._bulk_done, True, failures)
                return

            fraction = index / total
            label = os.path.basename(local.rstrip("/")) or local
            GLib.idle_add(self._update_progress, fraction,
                          f"{verb_flag.title()} {label} ({index + 1}/{total})…")

            cmd = [cli, "filesystem", verb_flag, local, remote]
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=600
                )
                if result.returncode != 0:
                    failures.append(f"{label}: exit {result.returncode}")
            except subprocess.TimeoutExpired:
                failures.append(f"{label}: timed out")
            except Exception as exc:
                failures.append(f"{label}: {exc}")

        GLib.idle_add(self._bulk_done, False, failures)

    # ---- GTK updates via idle_add (thread-safe) ----

    def _update_progress(self, fraction, text):
        self.progress_bar.set_fraction(fraction)
        self.progress_bar.set_text(text)
        self.status_label.set_text(text)
        return False

    def _bulk_done(self, cancelled, failures):
        self._busy = False
        self.btn_import.set_sensitive(True)
        self.btn_export.set_sensitive(True)
        self.btn_cancel.set_sensitive(False)

        if cancelled:
            self.progress_bar.set_fraction(0.0)
            self.progress_bar.set_text("Cancelled")
            self.status_label.set_text("Cancelled")
            self._toast("◼ Bulk transfer cancelled")
        elif failures:
            self.progress_bar.set_text(f"Done — {len(failures)} failed")
            self.status_label.set_text("Completed with errors")
            self._toast(f"✗ Finished with {len(failures)} failures: {'; '.join(failures[:3])}")
        else:
            self.progress_bar.set_fraction(1.0)
            self.progress_bar.set_text("Complete — 100%")
            self.status_label.set_text("All folders synced successfully")
            self._toast("✓ Bulk transfer complete")
        return False

    # ================= SAVE =================

    def _on_save_clicked(self, widget):
        self.config["proton_drive_myfiles_remote"] = self.entry_remote_myfiles.get_text().strip()
        self.config["proton_drive_albums_remote"] = self.entry_remote_albums.get_text().strip()
        self.config["proton_drive_photos_remote"] = self.entry_remote_photos.get_text().strip()
        self.config["proton_drive_trash_remote"] = self.entry_remote_trash.get_text().strip()
        self.config["local_source_myfiles"] = self.entry_myfiles.get_text().strip()
        self.config["local_source_albums"] = self.entry_albums.get_text().strip()
        self.config["local_source_photos"] = self.entry_photos.get_text().strip()
        self.config["local_source_trash"] = self.entry_trash.get_text().strip()
        cli_text = self.entry_cli.get_text().strip()
        self.config["cli_binary"] = cli_text or None

        success = self.config_manager.save(self.config)
        if success:
            self.cli_path = ConfigManager.find_cli(None)
        self._toast("✓ Settings saved" if success else "✗ Failed to save settings")

    def _toast(self, message):
        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            self._parent_window.add_toast(Adw.Toast(title=message, timeout=4))
