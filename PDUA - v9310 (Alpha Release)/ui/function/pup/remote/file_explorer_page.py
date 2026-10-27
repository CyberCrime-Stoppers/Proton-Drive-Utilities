#!/usr/bin/env python3
"""
FileExplorerPage — Unified Drive Explorer for PDUA
===================================================
MERGED VERSION: combines BOTH prior implementations.

  From the original file_explorer_page.py:
    * ThumbnailCache integration (spinner -> thumbnail in tiles)
    * PhotoViewerWindow (fullscreen single-photo viewer)
    * _load_token stale-result guard (discards late CLI answers)
    * Card-style tiles with image/folder detection

  From file_explorer_page (2).py:
    * Right-click context menu (Rename / Move / Delete Permanently)
    * Path/name validation (no '..', no '//', no injection)
    * Threaded mutations with auto-refresh after success
    * Back-button history + refresh button
    * Adw.MessageDialog prompts and confirmations

WHERE: ui/function/pup/remote/file_explorer_page.py
REGISTERED AS: self.pages["mydir"] = FileExplorerPage(root="/", ...)
SUBCLASSED BY: my_files_page.py (MyFilesPage, root="/my-files") and the
               other per-root wrappers.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from __future__ import annotations

import logging
import os
import subprocess
import threading

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk, GdkPixbuf, Pango

from ui.function.config_manager import ConfigManager
from ui.function.pup.remote.thumbnail_cache import ThumbnailCache

log = logging.getLogger("pdua.explorer")

CLI_TIMEOUT = 60

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
              ".heic", ".heif", ".tiff"}


# ---------------------------------------------------------------------------
# Validation helpers (module level — also imported by wrapper pages)
# ---------------------------------------------------------------------------

def _valid_path(path):
    """Canonical absolute remote path, or raises ValueError."""
    if not path or not isinstance(path, str) or not path.startswith("/"):
        raise ValueError("Remote paths must be absolute (start with '/').")
    if "//" in path or "\x00" in path:
        raise ValueError("Malformed path.")
    if any(part in (".", "..") for part in path.split("/")):
        raise ValueError("Path may not contain '.' or '..'.")
    return "/" + "/".join(p for p in path.split("/") if p)


def _valid_name(name):
    """Single path component, or raises ValueError."""
    name = (name or "").strip()
    if not name or name in (".", ".."):
        raise ValueError("Name cannot be empty.")
    if "/" in name or "\\" in name or "\x00" in name:
        raise ValueError("Name cannot contain a path separator.")
    if len(name) > 250:
        raise ValueError("Name is too long.")
    return name


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class FileExplorerPage(Gtk.Box):
    """
    Browses any Proton Drive root or folder with thumbnails, a photo
    viewer, and full right-click file management.

    Multiple instances (one per sidebar entry) are safe: each page owns
    its own 'ctx' action group, flowbox, cache handle, and history.
    """

    def __init__(self, root="/", title="Drive Explorer",
                 icon_category="albums", on_navigate=None, **_ignored):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ---- state ----
        self.root = root if root.startswith("/") else "/" + root
        self.page_title = title
        self.title_text = title                      # legacy alias
        self.icon_category = icon_category
        self.on_navigate = on_navigate
        self.current_path = self.root
        self.history = []                            # back-button stack
        self._cli_path = None
        self._actions_ready = False
        self._parent_window = None

        # Stale-result guard: bumped on every navigation; late CLI
        # answers carrying an old token are silently discarded.
        self._load_token = 0

        # Thumbnail cache (scaled-only, TOS-safe; see thumbnail_cache.py)
        try:
            self.cache = ThumbnailCache()
        except Exception as exc:
            log.warning("ThumbnailCache unavailable: %s", exc)
            self.cache = None

        # ---- header row ----
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                         margin_top=12, margin_bottom=6,
                         margin_start=12, margin_end=12)

        self.btn_back = Gtk.Button(label="← Back")
        self.btn_back.set_visible(False)
        self.btn_back.connect("clicked", self._on_back_clicked)
        header.append(self.btn_back)

        self.title_label = Gtk.Label()
        self.title_label.set_halign(Gtk.Align.START)
        self.title_label.set_hexpand(True)
        self.title_label.set_ellipsize(Pango.EllipsizeMode.END)
        header.append(self.title_label)

        self.refresh_button = Gtk.Button.new_from_icon_name(
            "view-refresh-symbolic")
        self.refresh_button.set_tooltip_text("Refresh")
        self.refresh_button.connect(
            "clicked", lambda *_: self.open_folder(self.current_path))
        header.append(self.refresh_button)

        self.append(header)

        # ---- status label ----
        self.status_label = Gtk.Label(label="")
        self.status_label.add_css_class("dim-label")
        self.status_label.set_halign(Gtk.Align.START)
        self.status_label.set_margin_start(12)
        self.status_label.set_margin_bottom(2)
        self.status_label.set_wrap(True)
        self.append(self.status_label)

        # ---- scrolling tile grid ----
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        self.flowbox = Gtk.FlowBox()
        self.flowbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self.flowbox.set_homogeneous(True)
        self.flowbox.set_min_children_per_line(3)
        self.flowbox.set_max_children_per_line(6)
        self.flowbox.set_row_spacing(12)
        self.flowbox.set_column_spacing(12)
        self.flowbox.set_margin_start(12)
        self.flowbox.set_margin_end(12)
        self.flowbox.set_margin_bottom(12)
        scrolled.set_child(self.flowbox)
        self.append(scrolled)

        # ---- context-menu action group (owned by THIS page) ----
        self._register_actions()

        # Load immediately. Children realize when added to the stack —
        # no 'map'/'mapped' signal needed (that GTK4 signal never existed).
        GLib.idle_add(self.open_folder, self.current_path)

    # ------------------------------------------------------------------
    # Stack/window integration adapters
    # ------------------------------------------------------------------

    def build(self, parent_window=None):
        """Adapter required by main_window.py's registration loop."""
        if parent_window is not None:
            self._parent_window = parent_window
        return self

    def _window(self):
        """Best-effort toplevel window for parenting dialogs/viewer."""
        for attr in ("_parent_window", "parent_window", "window", "app_window"):
            w = getattr(self, attr, None)
            if isinstance(w, Gtk.Window):
                return w
        root = self.get_root()
        return root if isinstance(root, Gtk.Window) else None

    def _cli(self):
        """Resolve the Proton Drive CLI once, then cache the result."""
        if self._cli_path is None:
            try:
                self._cli_path = ConfigManager.find_cli(None)
            except Exception as exc:
                log.debug("find_cli unavailable: %s", exc)
        return self._cli_path

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def open_folder(self, remote_path):
        """Load a folder into the view. Also serves the ctx.open action."""
        try:
            remote_path = _valid_path(remote_path)
        except ValueError as exc:
            self._set_status(f"⚠ {exc}", error=True)
            return

        if remote_path != self.current_path:
            self.history.append(self.current_path)
            self.btn_back.set_visible(True)

        self.current_path = remote_path
        self.title_label.set_text(f"{self.page_title} — {remote_path}")
        self._list_folder(remote_path)

    def _on_back_clicked(self, *_):
        if not self.history:
            self.btn_back.set_visible(False)
            return
        prev = self.history.pop()
        self.btn_back.set_visible(bool(self.history))
        # invalidate any in-flight listing for the page we're leaving
        self._load_token += 1
        self.current_path = prev
        self.title_label.set_text(f"{self.page_title} — {prev}")
        self._list_folder(prev)

    # ------------------------------------------------------------------
    # Listing (CLI, background thread, token-guarded)
    # ------------------------------------------------------------------

    def _set_status(self, text, error=False):
        self.status_label.set_text(text)

    def _clear_tiles(self):
        """Manual removal — GTK4 FlowBox has no remove_all()."""
        child = self.flowbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.flowbox.remove(child)
            child = nxt

    def _list_folder(self, remote_path):
        cli = self._cli()
        self._clear_tiles()
        if not cli:
            self._set_status("⚠ Proton Drive CLI not found — set it in Options.",
                             error=True)
            return

        self._load_token += 1
        token = self._load_token
        self._set_status("Loading…")

        def worker():
            ok, entries, err = False, [], "Operation failed."
            try:
                proc = subprocess.run(
                    [cli, "filesystem", "list", remote_path],
                    capture_output=True, text=True, timeout=CLI_TIMEOUT,
                )
                if proc.returncode == 0:
                    ok = True
                    entries = self._parse_listing(proc.stdout or "")
                    err = ""
                else:
                    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
                    err = detail.splitlines()[-1] if detail \
                        else "The CLI reported an error."
            except subprocess.TimeoutExpired:
                err = f"Listing timed out after {CLI_TIMEOUT}s."
            except FileNotFoundError:
                err = "Proton Drive CLI not found."
            except Exception as exc:
                err = f"Listing failed: {exc}"
            GLib.idle_add(self._on_list_done, token, remote_path,
                          ok, entries, err)

        threading.Thread(target=worker, daemon=True, name="pdua-list").start()

    @staticmethod
    def _parse_listing(stdout_text):
        """
        Parse `filesystem list` output into (name, is_folder, is_image).

        Tolerant by design: strips decorations (type prefixes like
        "d "/"- ", leading/trailing slashes, echoed full paths) and flags
        images by extension. Noise lines and duplicates are dropped.
        """
        results = []
        seen = set()
        for raw_line in stdout_text.splitlines():
            line = raw_line.strip()
            if not line or line in (".", ".."):
                continue
            if line.lower().startswith("listing"):     # CLI header line
                continue
            candidate = line
            for prefix in ("d ", "-t ", "dr", "-r", "- ", "dir ", "file "):
                if candidate.lower().startswith(prefix) and len(candidate) > 2:
                    candidate = candidate[2:].strip()
                    break
            is_folder = candidate.endswith("/")
            candidate = candidate.strip("/").strip()
            if "\t" in candidate:                       # column format
                parts = [p for p in candidate.split("\t") if p]
                candidate = parts[-1].strip("/")
            if not candidate:
                continue
            if "/" in candidate:                        # full path echo
                candidate = candidate.rsplit("/", 1)[-1]
            if not candidate or candidate in seen:
                continue
            seen.add(candidate)
            is_image = os.path.splitext(candidate)[1].lower() in IMAGE_EXTS
            results.append((candidate, is_folder, is_image))
        return results

    def _on_list_done(self, token, remote_path, ok, entries, err):
        # Stale-result guard: user may have navigated elsewhere while
        # we fetched. Late answers are silently dropped.
        if token != self._load_token:
            return False
        if remote_path != self.current_path:
            return False
        if not ok:
            self._set_status(f"⚠ {err}", error=True)
            return False
        if not entries:
            self._set_status("No items found.")
            return False
        parent = remote_path.rstrip("/")
        for name, is_folder, is_image in entries[:200]:   # 200-item cap
            item_path = f"{parent}/{name}"                # normalized — no '//'
            self._add_tile(name, item_path, is_folder, is_image)
        self._set_status(f"{len(entries)} item(s).")
        return False

    # ------------------------------------------------------------------
    # Tiles (card style + thumbnails + right-click menu)
    # ------------------------------------------------------------------

    def _add_tile(self, name, remote_path, is_folder, is_image):
        """Create one clickable card tile with menu and thumbnail slot."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("card")
        card.set_valign(Gtk.Align.START)
        card.set_size_request(180, -1)

        # --- image slot: spinner (images) or folder/file icon ---
        img_holder = Gtk.Box()
        img_holder.set_size_request(160, 160)
        img_holder.set_halign(Gtk.Align.CENTER)
        if is_image:
            spinner = Gtk.Spinner()
            spinner.start()
            spinner.set_valign(Gtk.Align.CENTER)
            spinner.set_halign(Gtk.Align.CENTER)
            img_holder.append(spinner)
        else:
            icon_name = ("folder-symbolic" if is_folder
                         else "text-x-generic-symbolic")
            icon = Gtk.Image.new_from_icon_name(icon_name)
            icon.set_pixel_size(64)
            icon.set_valign(Gtk.Align.CENTER)
            icon.set_halign(Gtk.Align.CENTER)
            img_holder.append(icon)
        card.append(img_holder)

        lbl = Gtk.Label(label=name, width_chars=20)
        lbl.set_ellipsize(Pango.EllipsizeMode.END)
        lbl.set_halign(Gtk.Align.START)
        card.append(lbl)

        # Left-click: drill into folders / open images in viewer.
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("released", lambda *_,
                      p=remote_path, f=is_folder, i=is_image:
                      self._on_tile_activated(p, f, i))
        card.add_controller(click)

        # Right-click: context menu (rename / move / delete).
        self._attach_menu(card, remote_path, is_folder)

        self.flowbox.insert(card, -1)

        # Thumbnail load — closure binds this tile's img_holder.
        if is_image and self.cache is not None:
            self.cache.get_async_with_callback(
                remote_path,
                lambda pixbuf, holder=img_holder: self._thumb_ready(pixbuf, holder)
            )

    def _thumb_ready(self, pixbuf, holder):
        """Main thread — swap spinner/icon for the thumbnail (or fallback)."""
        child = holder.get_first_child()
        if child:
            holder.remove(child)
        if pixbuf is not None:
            picture = Gtk.Picture.new_for_pixbuf(pixbuf)
            picture.set_size_request(160, 160)
            picture.set_can_shrink(True)
            holder.append(picture)
        else:
            fallback = Gtk.Image.new_from_icon_name("image-missing-symbolic")
            fallback.set_pixel_size(64)
            fallback.set_valign(Gtk.Align.CENTER)
            fallback.set_halign(Gtk.Align.CENTER)
            holder.append(fallback)
        return False

    def _on_tile_activated(self, remote_path, is_folder, is_image):
        if is_folder:
            self.open_folder(remote_path)
        elif is_image:
            self._open_viewer(remote_path)     # fullscreen photo viewer
        else:
            self._set_status(f"{remote_path.rsplit('/', 1)[-1]} — "
                             "preview/download not implemented for this type.")

    # ------------------------------------------------------------------
    # Photo viewer
    # ------------------------------------------------------------------

    def _open_viewer(self, remote_path):
        if self.cache is None:
            self._set_status("⚠ Thumbnail cache unavailable — cannot preview.")
            return
        viewer = PhotoViewerWindow(self._window(), self.cache, remote_path)
        viewer.present()

    # ------------------------------------------------------------------
    # Context menu — actions owned by this page
    # ------------------------------------------------------------------

    def _register_actions(self):
        """Install the 'ctx' action group on this page. Idempotent."""
        if self._actions_ready:
            return
        group = Gio.SimpleActionGroup()

        def add(name, handler):
            action = Gio.SimpleAction.new(name, GLib.VariantType("s"))
            action.connect("activate", lambda _a, p: handler(p.get_string()))
            group.add_action(action)

        add("open", self._act_open)
        add("rename", self._act_rename)
        add("move", self._act_move)
        add("delete", self._act_delete)

        self.insert_action_group("ctx", group)
        self._actions_ready = True

    def _menu_model(self, remote_path, is_folder):
        def item(label, action, path):
            mi = Gio.MenuItem.new(label, None)
            mi.set_action_and_target_value(action, GLib.Variant("s", path))
            return mi

        menu = Gio.Menu()
        if is_folder:
            menu.append_item(item("Open", "ctx.open", remote_path))
            menu.append_section(None, Gio.Menu())          # separator
        menu.append_item(item("Rename…", "ctx.rename", remote_path))
        menu.append_item(item("Move to…", "ctx.move", remote_path))
        menu.append_section(None, Gio.Menu())              # separator
        menu.append_item(item("Delete Permanently…", "ctx.delete", remote_path))
        return menu

    def _attach_menu(self, tile, remote_path, is_folder):
        popover = Gtk.PopoverMenu.new_from_model(
            self._menu_model(remote_path, is_folder))
        popover.set_parent(tile)
        popover.set_has_arrow(False)

        gesture = Gtk.GestureClick()
        gesture.set_button(3)                # right-click; left-click untouched
        gesture.connect("released", lambda _g, _n, x, y:
                        self._popup_menu(popover, x, y))
        tile.add_controller(gesture)

    @staticmethod
    def _popup_menu(popover, x, y):
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    # -- operation execution -------------------------------------------

    def _run_mutation(self, argv):
        """Validate CLI presence, run mutation async, refresh on success."""
        cli = self._cli()
        if not cli:
            self._set_status("⚠ Proton Drive CLI not found.", error=True)
            return

        self._set_status("Working…")

        def worker():
            ok, message = False, "Operation failed."
            try:
                proc = subprocess.run(
                    [cli, *argv], capture_output=True, text=True,
                    timeout=CLI_TIMEOUT)
                ok = proc.returncode == 0
                detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
                if ok:
                    message = "Done."
                else:
                    lines = [ln.strip() for ln in detail.splitlines()
                             if ln.strip()]
                    message = lines[-1] if lines \
                        else "The CLI reported an error."
            except subprocess.TimeoutExpired:
                message = f"Timed out after {CLI_TIMEOUT}s."
            except Exception as exc:
                message = f"Failed: {exc}"
            GLib.idle_add(self._on_mutation_done, ok, message)

        threading.Thread(target=worker, daemon=True,
                         name="pdua-mutation").start()

    def _on_mutation_done(self, ok, message):
        if ok:
            self._set_status(message)
            self._list_folder(self.current_path)     # refresh the listing
        else:
            self._set_status(f"⚠ {message}", error=True)
        return False

    # -- dialogs ---------------------------------------------------------

    def _ask_text(self, heading, body, placeholder, ok_label, on_ok):
        win = self._window()
        dialog = Adw.MessageDialog(transient_for=win, heading=heading, body=body)
        entry = Gtk.Entry(placeholder_text=placeholder, hexpand=True)
        entry.connect("activate", lambda _e: dialog.response("ok"))
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", ok_label)
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def respond(dlg, resp):
            text = entry.get_text().strip()
            dlg.destroy()
            if resp == "ok" and text:
                on_ok(text)

        dialog.connect("response", respond)
        dialog.present()
        entry.grab_focus()

    def _ask_confirm(self, heading, body, ok_label, on_ok):
        win = self._window()
        dialog = Adw.MessageDialog(transient_for=win, heading=heading, body=body)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", ok_label)
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def respond(dlg, resp):
            dlg.destroy()
            if resp == "ok":
                on_ok()

        dialog.connect("response", respond)
        dialog.present()

    # -- action handlers --------------------------------------------------

    def _act_open(self, remote_path):
        self.open_folder(remote_path)

    def _act_rename(self, remote_path):
        current = remote_path.rsplit("/", 1)[-1]

        def do_it(new_name):
            try:
                _valid_path(remote_path)
                new_name = _valid_name(new_name)
            except ValueError as exc:
                self._set_status(f"⚠ {exc}", error=True)
                return
            self._run_mutation(["filesystem", "rename", remote_path, new_name])

        self._ask_text("Rename", f"Current name: {current}",
                       current, "Rename", do_it)

    def _act_move(self, remote_path):
        def do_it(target):
            try:
                _valid_path(remote_path)
                target = _valid_path(target.rstrip("/") or "/")
                if target == remote_path or target.startswith(remote_path + "/"):
                    raise ValueError("Cannot move an item into itself.")
            except ValueError as exc:
                self._set_status(f"⚠ {exc}", error=True)
                return
            self._run_mutation(["filesystem", "move", remote_path, target])

        self._ask_text(
            "Move to Folder",
            f"Moving:\n{remote_path}\n\nDestination folder (absolute path):",
            "/my-files/", "Move", do_it,
        )

    def _act_delete(self, remote_path):
        name = remote_path.rsplit("/", 1)[-1]

        def do_it():
            try:
                _valid_path(remote_path)
            except ValueError as exc:
                self._set_status(f"⚠ {exc}", error=True)
                return
            self._run_mutation(["filesystem", "delete", remote_path])

        self._ask_confirm(
            "Delete Permanently",
            f'"{name}" will be deleted permanently.\n\nThis cannot be undone.',
            "Delete Permanently", do_it,
        )


# ---------------------------------------------------------------------------
# Fullscreen photo viewer
# ---------------------------------------------------------------------------

class PhotoViewerWindow(Gtk.Window):
    """Window for viewing a single photo at higher resolution."""

    def __init__(self, parent, cache, remote_path):
        super().__init__(transient_for=parent)
        self.set_title(os.path.basename(remote_path))
        self.set_default_size(900, 700)

        # Loading state (cleaned up: no walrus-in-constructor trickery)
        spinner = Gtk.Spinner()
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.set_hexpand(True)
        spinner.set_vexpand(True)
        spinner.start()
        self.set_child(spinner)

        cache.get_async_with_callback(
            remote_path,
            lambda pixbuf: self._full_ready(pixbuf),
            size_px=1024,          # larger than tile thumbnails
        )

    def _full_ready(self, pixbuf):
        if pixbuf is None:
            self.set_child(Gtk.Label(label="⚠ Unable to load image"))
            return False
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(Gtk.Picture.new_for_pixbuf(pixbuf))
        self.set_child(scrolled)
        return False


# ---------------------------------------------------------------------------
# Backwards-compatibility alias
# ---------------------------------------------------------------------------
AlbumExplorerPage = FileExplorerPage


# ---------------------------------------------------------------------------
# Smoke test: python3 -m ui.function.pup.remote.file_explorer_page
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Syntax/import check…")
    page = FileExplorerPage(root="/", title="Smoke Test")
    assert page.current_path == "/"
    print(f"  class OK — constructed, current_path={page.current_path!r}")
    for probe in ["/my-files", "my-files", "/a//b", "/../etc", "/albums"]:
        try:
            _valid_path(probe)
            print(f"  _valid_path({probe!r}) -> accepted")
        except ValueError:
            print(f"  _valid_path({probe!r}) -> rejected")
    for name in ["ok name.txt", "", "a/b", "."]:
        try:
            _valid_name(name)
            print(f"  _valid_name({name!r}) -> accepted")
        except ValueError:
            print(f"  _valid_name({name!r}) -> rejected")
    sample = "listing of /my-files\n  d Documents/\n-r notes.txt\nvacation.jpg\n"
    print(f"  _parse_listing(sample) -> "
          f"{FileExplorerPage._parse_listing(sample)}")
    print("SMOKE TEST PASSED")

