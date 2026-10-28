#!/usr/bin/env python3

from __future__ import annotations
import logging
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from ui.function.pup.remote.file_explorer_page import (
    FileExplorerPage,
    _valid_path,
    _valid_name,
)

log = logging.getLogger("pdua.myfiles")


class MyFilesPage(FileExplorerPage):
    """Browses /my-files with a New Folder shortcut."""

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(
            root="/my-files",
            title="My Files",
            on_navigate=on_navigate,
        )
        # Extra header button — inserted after the base header was built.
        self.new_folder_button = Gtk.Button.new_from_icon_name(
            "folder-new-symbolic"
        )
        self.new_folder_button.set_tooltip_text("New Folder")
        self.new_folder_button.connect(
            "clicked", lambda *_: self._prompt_new_folder()
        )
        # Place it left of the Refresh button in the header row
        # (header is the first child of this Gtk.Box).
        header = self.get_first_child()
        if isinstance(header, Gtk.Box):
            header.insert_child_after(
                self.new_folder_button, self.back_button
            )

    def _prompt_new_folder(self):
        """Ask for a name, then create <current_path>/<name>."""
        parent = self.current_path

        def do_it(name):
            try:
                _valid_path(parent)
                name = _valid_name(name)
            except ValueError as exc:
                self._set_status(f"⚠ {exc}", error=True)
                return
            # Reuse the base class's threaded mutation runner + refresh:
            self._run_mutation(["filesystem", "create-folder", parent, name])

        self._ask_text(
            "New Folder",
            f"Creating a folder inside:\n{parent}",
            "Folder name",
            "Create",
            do_it,
        )


if __name__ == "__main__":
    print("Constructing MyFilesPage…")
    page = MyFilesPage()
    assert page.root == "/my-files", f"root wrong: {page.root}"
    assert page.page_title == "My Files"
    assert page.current_path == "/my-files"
    assert hasattr(page, "new_folder_button"), "New Folder button missing"
    print(f"  root        = {page.root}")
    print(f"  title       = {page.page_title}")
    print(f"  current     = {page.current_path}")
    print("  new-folder button present: yes")
    print("SMOKE TEST PASSED (GUI not launched — no display needed)")

