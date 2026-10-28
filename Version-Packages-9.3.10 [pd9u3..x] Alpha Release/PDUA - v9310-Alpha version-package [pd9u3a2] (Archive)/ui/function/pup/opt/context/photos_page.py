# Six Root Browser Pages for PDUA
# =============================================
# Modeled on my_files_page.py. Each file below goes in:
#   ui/function/pup/opt/context/   (alongside my_files_page.py)
#
# Registered in main_window.py as:
#   self.pages["photos"]            = PhotosPage(on_navigate=self.navigate_to)
#   self.pages["photossharedwith"]  = PhotosSharedWithMePage(on_navigate=self.navigate_to)
#   self.pages["photostrash"]        = PhotosTrashPage(on_navigate=self.navigate_to)
#   self.pages["sharedby"]           = SharedByMePage(on_navigate=self.navigate_to)
#   self.pages["sharedwith"]         = SharedWithMePage(on_navigate=self.navigate_to)
#   self.pages["trash"]              = TrashPage(on_navigate=self.navigate_to)
#
# Design decisions (recommendations):
#   - WRITABLE roots (photos)          -> "New Folder" button, same as MyFilesPage
#   - SHARED roots (shared-by-me, shared-with-me, photos-shared-*)
#     -> NO mutation buttons; items there are foreign/shared — you
#        browse and view, not create. Kept as plain subclasses.
#   - TRASH roots (trash, photos-trash) -> "Empty Trash…" button with a
#     typed confirmation dialog (destructive, permanent).
#
# All six inherit FileExplorerPage's lazy do_map(), breadcrumbs, viewing,
# editing, sync, context menus automatically.


# =============================================================
# FILE 1 of 6 — photos_page.py
# =============================================================

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

log = logging.getLogger("pdua.photos")


class PhotosPage(FileExplorerPage):
    """Browses /photos with a New Folder shortcut."""

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(
            root="/photos",
            title="Photos",
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
    print("Constructing PhotosPage…")
    page = PhotosPage()
    assert page.root == "/photos", f"root wrong: {page.root}"
    assert page.page_title == "Photos"
    assert page.current_path == "/photos"
    assert hasattr(page, "new_folder_button"), "New Folder button missing"
    print(f"  root        = {page.root}")
    print(f"  title       = {page.page_title}")
    print(f"  current     = {page.current_path}")
    print("  new-folder button present: yes")
    print("SMOKE TEST PASSED (GUI not launched — no display needed)")


# =============================================================
# FILE 2 of 6 — photos_shared_with_me_page.py
# =============================================================

#!/usr/bin/env python3

from __future__ import annotations
import logging
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from ui.function.pup.remote.file_explorer_page import FileExplorerPage

log = logging.getLogger("pdua.photossharedwith")


class PhotosSharedWithMePage(FileExplorerPage):
    """
    Browses /photos-shared-with-me.

    READ-ONLY by design: this root holds photos OTHER people shared
    with you, so no New Folder / mutation toolbar button is offered.
    Rename/move/delete stay available via the per-item context menu
    only if the CLI grants them; nothing here mutates on its own.
    """

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(
            root="/photos-shared-with-me",
            title="Photos Shared with Me",
            on_navigate=on_navigate,
        )


if __name__ == "__main__":
    print("Constructing PhotosSharedWithMePage…")
    page = PhotosSharedWithMePage()
    assert page.root == "/photos-shared-with-me", f"root wrong: {page.root}"
    assert page.page_title == "Photos Shared with Me"
    assert page.current_path == "/photos-shared-with-me"
    print(f"  root        = {page.root}")
    print(f"  title       = {page.page_title}")
    print(f"  current     = {page.current_path}")
    print("SMOKE TEST PASSED (GUI not launched — no display needed)")


# =============================================================
# FILE 3 of 6 — photos_trash_page.py
# =============================================================

#!/usr/bin/env python3

from __future__ import annotations
import logging
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from ui.function.pup.remote.file_explorer_page import FileExplorerPage

log = logging.getLogger("pdua.photostrash")


class PhotosTrashPage(FileExplorerPage):
    """Browses /photos-trash with an Empty Trash shortcut."""

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(
            root="/photos-trash",
            title="Photos Trash",
            on_navigate=on_navigate,
        )
        # Extra header button — destructive, so red styling + confirm.
        self.empty_trash_button = Gtk.Button.new_from_icon_name(
            "user-trash-symbolic"
        )
        self.empty_trash_button.add_css_class("destructive-action")
        self.empty_trash_button.set_tooltip_text("Empty Photos Trash (permanent)")
        self.empty_trash_button.connect(
            "clicked", lambda *_: self._prompt_empty_trash()
        )
        header = self.get_first_child()
        if isinstance(header, Gtk.Box):
            header.insert_child_after(
                self.empty_trash_button, self.refresh_button
            )

    def _prompt_empty_trash(self):
        """Typed confirmation, then run filesystem empty-trash."""
        def do_it():
            self._run_mutation(["filesystem", "empty-trash"])

        self._ask_confirm(
            "Empty Photos Trash",
            "EVERYTHING in Photos Trash will be permanently deleted.\n"
            "This cannot be undone.",
            "Empty Trash",
            do_it,
        )


if __name__ == "__main__":
    print("Constructing PhotosTrashPage…")
    page = PhotosTrashPage()
    assert page.root == "/photos-trash", f"root wrong: {page.root}"
    assert page.page_title == "Photos Trash"
    assert page.current_path == "/photos-trash"
    assert hasattr(page, "empty_trash_button"), "Empty Trash button missing"
    print(f"  root        = {page.root}")
    print(f"  title       = {page.page_title}")
    print(f"  current     = {page.current_path}")
    print("  empty-trash button present: yes")
    print("SMOKE TEST PASSED (GUI not launched — no display needed)")


# =============================================================
# FILE 4 of 6 — shared_by_me_page.py
# =============================================================

#!/usr/bin/env python3

from __future__ import annotations
import logging
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from ui.function.pup.remote.file_explorer_page import FileExplorerPage

log = logging.getLogger("pdua.sharedby")


class SharedByMePage(FileExplorerPage):
    """
    Browses /shared-by-me.

    READ-ONLY by design: this root lists items YOU shared out. Manage
    sharing from the per-item context menu; no folder-creation toolbar
    button here (you create folders in My Files).
    """

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(
            root="/shared-by-me",
            title="Shared by Me",
            on_navigate=on_navigate,
        )


if __name__ == "__main__":
    print("Constructing SharedByMePage…")
    page = SharedByMePage()
    assert page.root == "/shared-by-me", f"root wrong: {page.root}"
    assert page.page_title == "Shared by Me"
    assert page.current_path == "/shared-by-me"
    print(f"  root        = {page.root}")
    print(f"  title       = {page.page_title}")
    print(f"  current     = {page.current_path}")
    print("SMOKE TEST PASSED (GUI not launched — no display needed)")


# =============================================================
# FILE 5 of 6 — shared_with_me_page.py
# =============================================================

#!/usr/bin/env python3

from __future__ import annotations
import logging
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from ui.function.pup.remote.file_explorer_page import FileExplorerPage

log = logging.getLogger("pdua.sharedwith")


class SharedWithMePage(FileExplorerPage):
    """
    Browses /shared-with-me.

    READ-ONLY by design: items other people shared with you. Browse,
    view, sync — no New Folder button for a foreign root.
    """

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(
            root="/shared-with-me",
            title="Shared with Me",
            on_navigate=on_navigate,
        )


if __name__ == "__main__":
    print("Constructing SharedWithMePage…")
    page = SharedWithMePage()
    assert page.root == "/shared-with-me", f"root wrong: {page.root}"
    assert page.page_title == "Shared with Me"
    assert page.current_path == "/shared-with-me"
    print(f"  root        = {page.root}")
    print(f"  title       = {page.page_title}")
    print(f"  current     = {page.current_path}")
    print("SMOKE TEST PASSED (GUI not launched — no display needed)")


# =============================================================
# FILE 6 of 6 — trash_page.py
# =============================================================

#!/usr/bin/env python3

from __future__ import annotations
import logging
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from ui.function.pup.remote.file_explorer_page import FileExplorerPage

log = logging.getLogger("pdua.trash")


class TrashPage(FileExplorerPage):
    """Browses /trash with an Empty Trash shortcut."""

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(
            root="/trash",
            title="Trash",
            on_navigate=on_navigate,
        )
        # Extra header button — destructive, so red styling + confirm.
        self.empty_trash_button = Gtk.Button.new_from_icon_name(
            "user-trash-symbolic"
        )
        self.empty_trash_button.add_css_class("destructive-action")
        self.empty_trash_button.set_tooltip_text("Empty Trash (permanent)")
        self.empty_trash_button.connect(
            "clicked", lambda *_: self._prompt_empty_trash()
        )
        header = self.get_first_child()
        if isinstance(header, Gtk.Box):
            header.insert_child_after(
                self.empty_trash_button, self.refresh_button
            )

    def _prompt_empty_trash(self):
        """Typed confirmation, then run filesystem empty-trash."""
        def do_it():
            self._run_mutation(["filesystem", "empty-trash"])

        self._ask_confirm(
            "Empty Trash",
            "EVERYTHING in Trash will be permanently deleted.\n"
            "This cannot be undone.",
            "Empty Trash",
            do_it,
        )


if __name__ == "__main__":
    print("Constructing TrashPage…")
    page = TrashPage()
    assert page.root == "/trash", f"root wrong: {page.root}"
    assert page.page_title == "Trash"
    assert page.current_path == "/trash"
    assert hasattr(page, "empty_trash_button"), "Empty Trash button missing"
    print(f"  root        = {page.root}")
    print(f"  title       = {page.page_title}")
    print(f"  current     = {page.current_path}")
    print("  empty-trash button present: yes")
    print("SMOKE TEST PASSED (GUI not launched — no display needed)")


# =============================================================
# REGISTRATION SNIPPET for main_window.py
# =============================================================
# Replace the direct FileExplorerPage(...) constructions with these,
# keeping your existing self.pages dict pattern:

'''
from ui.function.pup.opt.context.photos_page import PhotosPage
from ui.function.pup.opt.context.photos_shared_with_me_page import PhotosSharedWithMePage
from ui.function.pup.opt.context.photos_trash_page import PhotosTrashPage
from ui.function.pup.opt.context.shared_by_me_page import SharedByMePage
from ui.function.pup.opt.context.shared_with_me_page import SharedWithMePage
from ui.function.pup.opt.context.trash_page import TrashPage

self.pages["photos"]           = PhotosPage(on_navigate=self.navigate_to)
self.pages["photossharedwith"] = PhotosSharedWithMePage(on_navigate=self.navigate_to)
self.pages["photostrash"]      = PhotosTrashPage(on_navigate=self.navigate_to)
self.pages["sharedby"]         = SharedByMePage(on_navigate=self.navigate_to)
self.pages["sharedwith"]       = SharedWithMePage(on_navigate=self.navigate_to)
self.pages["trash"]            = TrashPage(on_navigate=self.navigate_to)
'''

# Also add sidebar entries in _build_sidebar(), e.g.:
'''
for label, key in [
    ("🏠 Home", "home"),
    ("⚡ Sync Center", "synccenterpage"),
    ("🗃️ File Explorer", "mydir"),
    ("📁 My Files", "myfiles"),
    ("🖼️ Photos", "photos"),
    ("📸 Photos Shared with Me", "photossharedwith"),
    ("🗑️ Photos Trash", "photostrash"),
    ("📤 Shared by Me", "sharedby"),
    ("📥 Shared with Me", "sharedwith"),
    ("🗑️ Trash", "trash"),
    ("🛞 AutoSync Setup", "autosync"),
]:
'''

