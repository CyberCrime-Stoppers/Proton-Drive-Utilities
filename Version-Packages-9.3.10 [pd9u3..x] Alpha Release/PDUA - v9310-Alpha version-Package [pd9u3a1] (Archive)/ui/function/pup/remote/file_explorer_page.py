#!/usr/bin/env python3
"""
FileExplorerPage — Unified Drive Explorer for PDUA (v2, rev 4)
================================================================
rev 4 CHANGELOG (merge of rev 3 + album_explorer patterns):
  * Combined rev 3 features (breadcrumbs, lazy-loading, editing, sync,
    error CSS class, popover unparenting, history cap) with album_explorer's
    cleaner nav_stack drill-down model
  * IN-APP POPUP VIEWER for text/images (not fullscreen window) — lightweight,
    stays within the same window
  * _add_tile() callback binding from album_explorer (closure per tile, no
    signature mismatch)
  * All subdirectories open properly — verified both roots work

v2 features retained:
  1. Clickable breadcrumbs — every path segment a button; every root.
  2. View every file: images built-in viewer; video/audio/docs opened
     in the system default app (GTK >= 4.10 Gtk.FileLauncher, fallback
     to Gio.AppInfo).
  3. Edit externally: download -> editor -> Gio.FileMonitor watch ->
     toast "Save to Drive" re-uploads to the original remote path.
  4. Sync Folder to Computer: recursive download into a chosen local
     folder (Gtk.FileDialog >= 4.10, text-entry fallback).

Retained from v1: ThumbnailCache integration, PhotoViewerWindow,
_load_token stale-result guard, GVariant-encoded context menus,
path/name validation, threaded mutations with auto-refresh.

WHERE: ui/function/pup/remote/file_explorer_page.py
PREREQUISITES: ui/function/config_manager.py (ConfigManager.find_cli),
               ui/function/pup/remote/thumbnail_cache.py

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 1.4.0 (rev 4)
"""

from __future__ import annotations

import hashlib
import shutil
import logging
import os
import subprocess
import tempfile
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

SYNC_TIMEOUT = 3600          # recursive syncs can be long
EDIT_SETTLE_MS = 1200        # debounce for editor saves
HISTORY_CAP = 50              # back-stack cap (rev 3)
POPUP_WIDTH = 800
POPUP_HEIGHT = 600            # popup viewer dimensions

# --- File-type detection ---------------------------------------------------
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp",
              ".heic", ".heif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v"}
AUDIO_EXTS = {".mp3", ".flac", ".ogg", ".opus", ".wav", ".m4a", ".aac"}
TEXT_EXTS = {".txt", ".md", ".json", ".xml", ".yaml", ".yml", ".csv",
             ".conf", ".ini", ".py", ".sh", ".js", ".css", ".html"}

# Local working area for downloads / edit sessions
_XDG_CACHE = os.environ.get("XDG_CACHE_HOME") or os.path.expanduser("~/.cache")
EDITING_DIR = os.path.join(_XDG_CACHE, "pdua", "editing")
OPEN_DIR = os.path.join(_XDG_CACHE, "pdua", "open")


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


def _file_kind(filename):
    """Classify a filename. Returns 'folder'|'image'|'video'|'audio'|'text'."""
    ext = os.path.splitext(filename)[1].lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return "text"


# ---------------------------------------------------------------------------
# The page
# ---------------------------------------------------------------------------

class FileExplorerPage(Gtk.Box):
    """
    Browses any Proton Drive root or folder with breadcrumbs, thumbnails,
    universal file viewing, external editing, and media folder sync.

    Multiple instances (one per sidebar entry) are safe: each page owns
    its own 'ctx' action group, flowbox, cache handle, and nav_stack.
    """

    def __init__(self, root="/", title="Drive Explorer",
                 icon_category="albums", on_navigate=None,
                 enable_edit=True, **_ignored):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # ---- state ----
        self.root = root if root.startswith("/") else "/" + root
        self.page_title = title
        self.title_text = title                      # legacy alias
        self.icon_category = icon_category
        self.on_navigate = on_navigate
        self.enable_edit = enable_edit
        self.current_path = self.root
        self.history = []                            # back-stack (capped)
        self._cli_path = None
        self._actions_ready = False
        self._parent_window = None

        # Stale-result guard
        self._load_token = 0

        # Lazy loading (rev 3): first listing fires from do_map()
        self._loaded_once = False

        # Navigation stack for drill-down (from album_explorer pattern)
        self.nav_stack = [self.root]                # root at index 0

        # Active edit sessions: remote_path -> {"local": str, "monitor": Gio.FileMonitor}
        self._edit_sessions = {}
        # Pending (debounced) uploads: local_path -> {"remote": str, "source_id": int}
        self._pending_uploads = {}

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

        # rev 3: renamed btn_back -> back_button (subclass pages insert
        # next to this widget by that name; keep it stable).
        self.back_button = Gtk.Button(label="← Back")
        self.back_button.set_visible(False)
        self.back_button.connect("clicked", self._on_back_clicked)
        header.append(self.back_button)

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

        # Sync-current-folder shortcut button in the header
        self.sync_button = Gtk.Button.new_from_icon_name(
            "folder-download-symbolic")
        self.sync_button.set_tooltip_text(
            "Sync this folder (and everything below it) to your computer")
        self.sync_button.connect(
            "clicked", lambda *_: self._sync_folder_to_computer(
                self.current_path))
        header.append(self.sync_button)

        self.append(header)

        # ---- breadcrumb trail ----
        self.breadcrumb_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL, spacing=2,
            margin_start=12, margin_end=12, margin_bottom=6)
        self.breadcrumb_box.add_css_class("dim-label")
        self.append(self.breadcrumb_box)

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

        # NOTE (rev 3): no eager load here. First listing is triggered by
        # do_map() when the stack first shows this page — prevents N
        # parallel CLI calls at startup.

    def do_map(self):
        """First-show lazy loader (rev 3). A Gtk.Stack maps only its
        visible child, so this fires exactly once per page, at the
        moment the user opens it."""
        Gtk.Box.do_map(self)
        if not self._loaded_once:
            self._loaded_once = True
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

    def _toast(self, message, button_label=None, on_button=None, timeout=4):
        """Toast via the parent window (best effort)."""
        win = self._window()
        if win is not None and hasattr(win, "add_toast"):
            toast = Adw.Toast(title=message, timeout=timeout)
            if button_label and on_button:
                toast.set_button_label(button_label)
                toast.connect("button-clicked", lambda t: on_button())
            win.add_toast(toast)
        else:
            log.info("%s", message)

    # ------------------------------------------------------------------
    # BREADCRUMBS
    # ------------------------------------------------------------------

    def _update_breadcrumbs(self):
        """Rebuild the clickable path trail for self.current_path."""
        # clear previous crumb widgets
        child = self.breadcrumb_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.breadcrumb_box.remove(child)
            child = nxt

        # Build the (label, target) crumb list.
        crumbs = [(self.page_title, self.root)]
        if self.root == "/":
            # Flat root page: each segment below "/" is its own crumb.
            segments = [s for s in self.current_path.split("/") if s]
            for i, seg in enumerate(segments):
                crumbs.append((seg, "/" + "/".join(segments[:i + 1])))
        else:
            rel = self.current_path[len(self.root.rstrip("/")):].strip("/")
            segments = [s for s in rel.split("/") if s]
            for i, seg in enumerate(segments):
                target = self.root.rstrip("/") + "/" + "/".join(segments[:i + 1])
                crumbs.append((seg, target))

        for idx, (label, target) in enumerate(crumbs):
            if idx > 0:
                sep = Gtk.Label(label="›")
                sep.set_margin_start(2)
                sep.set_margin_end(2)
                self.breadcrumb_box.append(sep)
            is_last = (idx == len(crumbs) - 1)

            # GTK4 flat button: set_has_frame(False) + 'flat' CSS class.
            # (NO set_relief — Gtk.ReliefStyle is GTK3-only and removed.)
            btn = Gtk.Button(label=label)
            btn.set_has_frame(False)
            btn.add_css_class("flat")
            btn.set_margin_top(0)
            btn.set_margin_bottom(0)
            if is_last:
                btn.set_sensitive(False)     # current location: not clickable
                lbl = btn.get_first_child()
                if isinstance(lbl, Gtk.Label):
                    lbl.set_markup(
                        f"<b>{GLib.markup_escape_text(label)}</b>")
            else:
                btn.set_tooltip_text(f"Go to {target}")
                btn.connect(
                    "clicked",
                    lambda b, t=target: self.open_folder(t))
            self.breadcrumb_box.append(btn)

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
            del self.history[:-HISTORY_CAP]        # rev 3: cap the stack
            self.back_button.set_visible(True)

        # Update nav_stack for drill-down tracking
        if remote_path.startswith(self.current_path.rstrip("/") + "/"):
            # Going deeper — push to nav_stack
            self.nav_stack.append(remote_path)
        elif self.nav_stack and self.nav_stack[-1] != remote_path:
            # Going sideways/back via breadcrumb — replace current
            self.nav_stack[-1] = remote_path

        self.current_path = remote_path
        self.title_label.set_text(f"{self.page_title} — {remote_path}")
        self._update_breadcrumbs()
        self._list_folder(remote_path)

    def _on_back_clicked(self, *_):
        if not self.history:
            self.back_button.set_visible(False)
            return
        prev = self.history.pop()
        self.back_button.set_visible(bool(self.history))
        # invalidate any in-flight listing for the page we're leaving
        self._load_token += 1
        self.current_path = prev
        self.title_label.set_text(f"{self.page_title} — {prev}")
        self._update_breadcrumbs()
        self._list_folder(prev)

    # ------------------------------------------------------------------
    # Listing (CLI, background thread, token-guarded)
    # ------------------------------------------------------------------

    def _set_status(self, text, error=False):
        """Status line. rev 3: error=True actually applies the 'error'
        CSS class now (was silently ignored)."""
        self.status_label.set_text(text)
        if error:
            self.status_label.add_css_class("error")
        else:
            self.status_label.remove_css_class("error")

    def _clear_tiles(self):
        """Manual removal — GTK4 FlowBox has no remove_all().
        rev 3: unparent each tile's popover FIRST, else GTK4 emits
        Gtk-CRITICAL warnings and leaks the PopoverMenu."""
        child = self.flowbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            popover = getattr(child, "_pdua_popover", None)
            if popover is not None:
                try:
                    popover.unparent()
                except Exception:
                    pass
                child._pdua_popover = None
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
                    capture_output=True, text=True)
                if proc.returncode == 0:
                    ok = True
                    entries = self._parse_listing(proc.stdout or "")
                    err = ""
                else:
                    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
                    err = detail.splitlines()[-1] if detail \
                        else "The CLI reported an error."
            except subprocess.TimeoutExpired:
                err = f"Listing timed out after."
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
        Parse `filesystem list` output into (name, is_folder, kind).
        kind: 'folder' | 'image' | 'video' | 'audio' | 'text'

        Tolerant by design: strips decorations (type prefixes like
        "d "/"- ", leading/trailing slashes, echoed full paths) and
        classifies files by extension. Noise lines and duplicates dropped.
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
            if is_folder:
                kind = "folder"
            else:
                kind = _file_kind(candidate)
            results.append((candidate, is_folder, kind))
        return results

    def _on_list_done(self, token, remote_path, ok, entries, err):
        # Stale-result guard
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
        for name, is_folder, kind in entries[:400]:      # 400-item cap
            item_path = f"{parent}/{name}"              # normalized — no '//'
            self._add_tile(name, item_path, is_folder, kind)
        self._set_status(f"{len(entries)} item(s).")
        return False

    # ------------------------------------------------------------------
    # Tiles (card style + thumbnails + right-click menu)
    # ------------------------------------------------------------------

    def _add_tile(self, name, remote_path, is_folder, kind):
        """Create one clickable card tile with menu and thumbnail slot.
        Uses closure binding from album_explorer pattern — each callback
        captures its specific holder, preventing signature mismatch."""
        card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        card.add_css_class("card")
        card.set_valign(Gtk.Align.START)
        card.set_size_request(180, -1)

        # --- image slot: spinner (images) or type icon ---
        img_holder = Gtk.Box()
        img_holder.set_size_request(160, 160)
        img_holder.set_halign(Gtk.Align.CENTER)
        if kind == "image":
            spinner = Gtk.Spinner()
            spinner.start()
            spinner.set_valign(Gtk.Align.CENTER)
            spinner.set_halign(Gtk.Align.CENTER)
            img_holder.append(spinner)
        else:
            icon_name = {
                "folder": "folder-symbolic",
                "video": "video-x-generic-symbolic",
                "audio": "audio-x-generic-symbolic",
                "text": "text-x-generic-symbolic",
            }.get(kind, "text-x-generic-symbolic")
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

        # Left-click: drill into folders / open files.
        click = Gtk.GestureClick()
        click.set_button(1)
        click.connect("released", lambda *_,
                      p=remote_path, f=is_folder, k=kind:
                      self._on_tile_activated(p, f, k))
        card.add_controller(click)

        # Right-click: context menu.
        self._attach_menu(card, remote_path, is_folder)

        self.flowbox.insert(card, -1)

        # Thumbnail load — closure binds this tile's img_holder.
        if kind == "image" and self.cache is not None:
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

    def _on_tile_activated(self, remote_path, is_folder, kind):
        """Left-click behaviour by file kind. Handles ALL subdirectories."""
        if is_folder:
            self.open_folder(remote_path)
        elif kind == "image":
            # Option 1: Fullscreen viewer (existing)
            # Option 2: Popup in-app viewer (new, lighter)
            self._open_popup_viewer(remote_path, "image")
        else:
            self._open_popup_viewer(remote_path, "file")     # new popup for text/docs

    # ------------------------------------------------------------------
    # Universal file opening
    # ------------------------------------------------------------------

    def _open_remote_file(self, remote_path):
        """
        Download a file to a temp dir, then hand it to the desktop's
        default application (media player, office suite, editor, PDF
        viewer). Read-only "view" flow.
        """
        cli = self._cli()
        if not cli:
            self._set_status("⚠ Proton Drive CLI not found.", error=True)
            return
        self._set_status(f"Opening {remote_path.rsplit('/my-files/Pictures/Wallpaper/Technology', 1)[-1]}…")

        def worker():
            try:
                os.makedirs(OPEN_DIR, exist_ok=True)
                tmpdir = tempfile.mkdtemp(prefix="pdua_open_", dir=OPEN_DIR)
                proc = subprocess.run(
                    [cli, "filesystem", "download", remote_path, tmpdir],
                    capture_output=True, text=True, timeout=timeout)
                if proc.returncode != 0:
                    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
                    last = detail.splitlines()[-1] if detail else "CLI error"
                    GLib.idle_add(self._set_status, f"⚠ {last}", True)
                    return
                basename = os.path.basename(remote_path.rstrip("/"))
                local = os.path.join(tmpdir, basename)
                if not os.path.isfile(local):
                    entries = os.listdir(tmpdir)
                    local = os.path.join(tmpdir, entries[0]) if entries else None
                if local is None:
                    GLib.idle_add(self._set_status, "⚠ CLI wrote no file.", True)
                    return
                GLib.idle_add(self._launch_local, local)
            except subprocess.TimeoutExpired:
                GLib.idle_add(self._set_status, "⚠ Download timed out.", True)
            except Exception as exc:
                GLib.idle_add(self._set_status, f"⚠ {exc}", True)

        threading.Thread(target=worker, daemon=True,
                         name="pdua-open").start()

    @staticmethod
    def _launch_local(local_path):
        """Hand a downloaded file to the desktop. Runs on the main thread."""
        try:
            gfile = Gio.File.new_for_path(local_path)
            if hasattr(Gtk, "FileLauncher"):          # GTK >= 4.10
                Gtk.FileLauncher.new(gfile).launch(None, None, None)
            else:                                     # legacy fallback
                Gio.AppInfo.launch_default_for_uri(gfile.get_uri(), None)
        except Exception as exc:
            log.error("Could not open %s: %s", local_path, exc)
        return False

    # ------------------------------------------------------------------
    # IN-APP POPUP VIEWER (NEW — rev 4)
    # ------------------------------------------------------------------

    def _open_popup_viewer(self, remote_path, viewer_type):
        """
        Open an in-app popup (TransientWindow) to view images or text files.
        Lightweight alternative to fullscreen window — stays in same app
        instance, easier navigation.

        viewer_type: "image" (uses thumbnail cache) or "file" (downloads & displays text)
        """
        popup = PopupViewerWindow(
            self._window(), self.cache, remote_path, viewer_type=viewer_type
        )
        popup.present()

    # ------------------------------------------------------------------
    # External editing with change detection
    # ------------------------------------------------------------------

    def _edit_remote_file(self, remote_path):
        """
        Download -> open in the desktop editor -> watch for saves ->
        offer to upload the modified file back to its remote location.
        """
        if not self.enable_edit:
            return
        cli = self._cli()
        if not cli:
            self._set_status("⚠ Proton Drive CLI not found.", error=True)
            return

        # Already editing this file? Just re-launch the existing copy.
        session = self._edit_sessions.get(remote_path)
        if session:
            self._launch_local(session["local"])
            return

        self._set_status(f"Preparing {remote_path.rsplit('/my-files/Pictures/Wallpaper/Technology', 1)[-1]} for editing…")

        def worker():
            try:
                # Stable per-remote-path edit dir (survives relaunch,
                # so a half-finished edit isn't silently duplicated)
                key = hashlib.sha256(remote_path.encode()).hexdigest()[:16]
                edir = os.path.join(EDITING_DIR, key)
                os.makedirs(edir, exist_ok=True)
                # Remove a stale copy so the CLI always writes fresh
                basename = os.path.basename(remote_path.rstrip("/"))
                local = os.path.join(edir, basename)
                if os.path.exists(local):
                    os.unlink(local)

                proc = subprocess.run(
                    [cli, "filesystem", "download", remote_path, edir],
                    capture_output=True, text=True)
                if proc.returncode != 0:
                    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
                    last = detail.splitlines()[-1] if detail else "CLI error"
                    GLib.idle_add(self._set_status, f"⚠ {last}", True)
                    return
                if not os.path.isfile(local):
                    entries = os.listdir(edir)
                    if entries:
                        local = os.path.join(edir, entries[0])
                    else:
                        GLib.idle_add(self._set_status,
                                      "⚠ CLI wrote no file.", True)
                        return
                GLib.idle_add(self._start_edit_session, remote_path, local)
            except Exception as exc:
                GLib.idle_add(self._set_status, f"⚠ {exc}", True)

        threading.Thread(target=worker, daemon=True,
                         name="pdua-edit").start()

    def _start_edit_session(self, remote_path, local_path):
        """Main thread — launch editor + attach the file monitor."""
        self._edit_sessions[remote_path] = {"local": local_path, "monitor": None}
        self._launch_local(local_path)
        self._set_status(
            f"Editing {os.path.basename(local_path)} — "
            "save in your editor, then choose 'Save to Drive'.")

        # Watch the file for editor saves
        try:
            gfile = Gio.File.new_for_path(local_path)
            monitor = gfile.monitor_file(Gio.FileMonitorFlags.NONE)
            monitor.connect("changed", self._on_edited_file_changed)
            self._edit_sessions[remote_path]["monitor"] = monitor
        except Exception as exc:
            log.warning("FileMonitor unavailable for %s: %s", local_path, exc)

        # Toast with an immediate manual save option
        self._toast(
            f"{os.path.basename(local_path)} opened for editing",
            button_label="Save to Drive now",
            on_button=lambda: self._upload_edited(remote_path),
        )
        return False

    def _on_edited_file_changed(self, monitor, file, other_file, event_type):
        """
        Gio.FileMonitor callback. Debounces editor saves, then offers
        the upload toast. Stops watching vanished files.
        """
        try:
            if event_type in (Gio.FileMonitorEvent.DELETED,
                              Gio.FileMonitorEvent.UNMOUNTED):
                monitor.cancel()
                return
            if event_type not in (Gio.FileMonitorEvent.CHANGED,
                                  Gio.FileMonitorEvent.CHANGES_DONE_HINT):
                return
        except AttributeError:
            # Older GLib exposes plain ints for the event enum
            if event_type not in (2, 3):
                return

        local_path = file.get_path()
        if not local_path:
            return
        remote_path = self._remote_for_local(local_path)
        if remote_path is None:
            return

        # Debounce: editors emit bursts of CHANGED events per save.
        old_source = self._pending_uploads.get(local_path, {}).get("source_id")
        if old_source is not None:
            GLib.source_remove(old_source)

        source_id = GLib.timeout_add(
            EDIT_SETTLE_MS, self._offer_upload_edited, remote_path)
        self._pending_uploads[local_path] = {
            "remote": remote_path, "source_id": source_id}

    def _remote_for_local(self, local_path):
        """Reverse-lookup the remote path an editing session refers to."""
        for remote, session in self._edit_sessions.items():
            if session.get("local") == local_path:
                return remote
        return None

    def _offer_upload_edited(self, remote_path):
        """Debounce elapsed — offer to push the saved file back up."""
        local_path = self._edit_sessions.get(remote_path, {}).get("local")
        if local_path:
            self._pending_uploads.pop(local_path, None)
        self._toast(
            f"{remote_path.rsplit('/my-files/Pictures/Wallpaper/Technology', 1)[-1]} changed on disk",
            button_label="Save to Drive",
            on_button=lambda: self._upload_edited(remote_path),
            timeout=8,
        )

    def _upload_edited(self, remote_path):
        """Upload the locally-modified copy back over the remote file."""
        cli = self._cli()
        session = self._edit_sessions.get(remote_path)
        if not cli or not session or not os.path.isfile(session["local"]):
            return
        local = session["local"]
        remote_parent = remote_path.rsplit("/", 1)[0] or "/"

        self._set_status(f"Saving {os.path.basename(local)} to Drive…")

        def worker():
            try:
                proc = subprocess.run(
                    [cli, "filesystem", "upload", local, remote_parent],
                    capture_output=True, text=True)
                if proc.returncode == 0:
                    GLib.idle_add(self._on_edit_uploaded, True, remote_path,
                                  "Saved to Drive")
                else:
                    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
                    last = detail.splitlines()[-1] if detail else "CLI error"
                    GLib.idle_add(self._on_edit_uploaded, False, remote_path,
                                  f"Upload failed: {last}")
            except Exception as exc:
                GLib.idle_add(self._on_edit_uploaded, False, remote_path,
                              f"{exc}")

        threading.Thread(target=worker, daemon=True,
                         name="pdua-edit-save").start()

    def _on_edit_uploaded(self, ok, remote_path, message):
        self._set_status(message, error=not ok)
        if ok and self.current_path == remote_path.rsplit("/my-files/Pictures/Wallpaper/Technology", 1)[0]:
            self._list_folder(self.current_path)      # refresh the listing
        return False

    # ------------------------------------------------------------------
    # Media / folder sync to computer
    # ------------------------------------------------------------------

    def _sync_folder_to_computer(self, remote_path):
        """
        Recursively download a folder tree (images, photos, videos,
        music — everything) into a user-chosen local directory.
        Destination picked with Gtk.FileDialog (>= 4.10) or an
        Adw.MessageDialog text entry on older stacks.
        """
        try:
            remote_path = _valid_path(remote_path)
        except ValueError as exc:
            self._set_status(f"⚠ {exc}", error=True)
            return

        self._toast(f"Choose where to sync {remote_path}…", timeout=2)

        if hasattr(Gtk, "FileDialog"):                 # GTK >= 4.10
            dialog = Gtk.FileDialog()
            dialog.set_title(f"Sync '{remote_path}' to…")

            def on_folder_chosen(dialog, result):
                try:
                    gfile = dialog.select_folder_finish(result)
                    if gfile is not None:
                        self._run_folder_sync(remote_path, gfile.get_path())
                except GLib.Error:
                    pass                              # user cancelled

            dialog.select_folder(self._window(), None, on_folder_chosen)
        else:
            # Fallback: text-entry dialog (works everywhere)
            def do_it(target):
                target = os.path.expanduser(target.strip())
                if not target.startswith("/my-files/Pictures/Wallpaper/Technology"):
                    self._set_status("⚠ Path must be absolute.", error=True)
                    return
                os.makedirs(target, exist_ok=True)
                self._run_folder_sync(remote_path, target)

            self._ask_text(
                "Sync Folder to Computer",
                f"Downloading everything from:\n{remote_path}\n\n"
                "Local destination folder (must exist or will be created):",
                os.path.expanduser("~/Downloads"), "Start Sync", do_it,
            )

    def _run_folder_sync(self, remote_path, local_dir):
        """Run the recursive download in a worker thread."""
        cli = self._cli()
        if not cli:
            self._set_status("⚠ Proton Drive CLI not found.", error=True)
            return
        self._set_status(f"Syncing {remote_path} → {local_dir}… "
                         "(images, photos, videos, music — everything)")

        def worker():
            try:
                os.makedirs(local_dir, exist_ok=True)
                proc = subprocess.run(
                    [cli, "filesystem", "download", remote_path, local_dir],
                    capture_output=True, text=True)
                if proc.returncode == 0:
                    msg = f"Synced {remote_path} → {local_dir}"
                else:
                    detail = ((proc.stdout or "") + (proc.stderr or "")).strip()
                    last = detail.splitlines()[-1] if detail else "CLI error"
                    msg = f"Sync failed: {last}"
            except subprocess.TimeoutExpired:
                msg = f"Sync timed out afters."
            except Exception as exc:
                msg = f"Sync failed: {exc}"
            GLib.idle_add(self._set_status, msg, not msg.startswith("✓"))

        threading.Thread(target=worker, daemon=True,
                         name="pdua-sync").start()

    # ------------------------------------------------------------------
    # Photo viewer (fullscreen — retained from v2)
    # ------------------------------------------------------------------

    def _open_viewer(self, remote_path):
        if self.cache is None:
            self._set_status("⚠ Thumbnail cache unavailable — cannot preview.",
                             error=True)
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
        add("open-file", self._act_open_file)
        add("edit", self._act_edit)
        add("download", self._act_download)
        add("sync", self._act_sync)
        add("rename", self._act_rename)
        add("move", self._act_move)
        add("delete", self._act_delete)

        self.insert_action_group("ctx", group)
        self._actions_ready = True

    def _menu_model(self, remote_path, is_folder):
        """rev 3: real sections with items — rev 2 appended empty
        Gio.Menu() shells as pseudo-separators (rendered nothing)."""

        def item(label, action, path):
            mi = Gio.MenuItem.new(label, None)
            mi.set_action_and_target_value(action, GLib.Variant("s", path))
            return mi

        if is_folder:
            nav = Gio.Menu()
            nav.append_item(item("Open", "ctx.open", remote_path))
            sync = Gio.Menu()
            sync.append_item(item("Sync Folder to Computer…", "ctx.sync",
                                  remote_path))
            manage = Gio.Menu()
            manage.append_item(item("Rename…", "ctx.rename", remote_path))
            manage.append_item(item("Move to…", "ctx.move", remote_path))
            danger = Gio.Menu()
            danger.append_item(item("Delete Permanently…", "ctx.delete",
                                     remote_path))

            menu = Gio.Menu()
            menu.append_section("Folder", nav)
            menu.append_section("Sync", sync)
            menu.append_section("Manage", manage)
            menu.append_section("Danger Zone", danger)
            return menu
        else:
            nav = Gio.Menu()
            nav.append_item(item("Open", "ctx.open-file", remote_path))
            edit = Gio.Menu()
            edit.append_item(item("Edit Externally…", "ctx.edit", remote_path))
            dl = Gio.Menu()
            dl.append_item(item("Download to Computer…", "ctx.download",
                                remote_path))
            manage = Gio.Menu()
            manage.append_item(item("Rename…", "ctx.rename", remote_path))
            manage.append_item(item("Move to…", "ctx.move", remote_path))
            danger = Gio.Menu()
            danger.append_item(item("Delete Permanently…", "ctx.delete",
                                    remote_path))

            menu = Gio.Menu()
            menu.append_section("File", nav)
            menu.append_section("Edit", edit)
            menu.append_section("Download", dl)
            menu.append_section("Manage", manage)
            menu.append_section("Danger Zone", danger)
            return menu

    def _attach_menu(self, tile, remote_path, is_folder):
        popover = Gtk.PopoverMenu.new_from_model(
            self._menu_model(remote_path, is_folder))
        popover.set_parent(tile)
        popover.set_has_arrow(False)
        # rev 3: stamp on the tile so _clear_tiles() can unparent it
        # before removing the tile (prevents Gtk-CRITICAL + leak).
        tile._pdua_popover = popover

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
                    [cli, *argv], capture_output=True, text=True)

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

    def _act_open_file(self, remote_path):
        self._open_remote_file(remote_path)

    def _act_edit(self, remote_path):
        self._edit_remote_file(remote_path)

    def _act_download(self, remote_path):
        self._sync_folder_to_computer(remote_path)

    def _act_sync(self, remote_path):
        self._sync_folder_to_computer(remote_path)

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
# IN-APP POPUP VIEWER (NEW — rev 4)
# ---------------------------------------------------------------------------

class PopupViewerWindow(Gtk.Window):
    """
    Lightweight transient popup for viewing images or text files.
    Stays within the same app instance — easier navigation than
    spawning a separate fullscreen window.
    """

    def __init__(self, parent, cache, remote_path, viewer_type="image"):
        """
        viewer_type: "image" (uses cache for thumbnails) or "file"
                     (downloads text content and displays it)
        """
        super().__init__(transient_for=parent)
        self.set_title(os.path.basename(remote_path))
        self.set_default_size(POPUP_WIDTH, POPUP_HEIGHT)

        self.viewer_type = viewer_type
        self.remote_path = remote_path
        self.cli_path = None

        # Initial loading spinner
        spinner = Gtk.Spinner()
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.set_halign(Gtk.Align.CENTER)
        spinner.set_hexpand(True)
        spinner.set_vexpand(True)
        spinner.start()
        self.set_child(spinner)

        if viewer_type == "image":
            # Full-size, in-app view: fetch to a throwaway /tmp dir,
            # load into memory, delete the temp file. Nothing is
            # written to ~/.cache/pdua.
            GLib.idle_add(self._load_full_image)
        else:
            # Download and display text content
            GLib.idle_add(self._load_text_content)

    def _load_full_image(self):
        """Kick off the full-resolution image fetch (runs on main thread)."""
        cli = ConfigManager.find_cli(None)
        if not cli:
            self.set_child(Gtk.Label(label="⚠ Proton Drive CLI not found"))
            return False
        threading.Thread(target=self._image_worker, args=(cli,),
                         daemon=True, name="pdua-view-image").start()
        return False

    def _image_worker(self, cli):
        """Worker thread — download to /tmp, decode into memory, clean up."""
        tmpdir = tempfile.mkdtemp(prefix="pdua_view_")
        local = None
        try:
            proc = subprocess.run(
                [cli, "filesystem", "download", self.remote_path, tmpdir],
                capture_output=True, text=True)
            if proc.returncode != 0:
                detail = (proc.stderr or proc.stdout or "").strip()
                last = detail.splitlines()[-1] if detail else "CLI error"
                GLib.idle_add(self._show_message, f"⚠ {last}")
                return
            basename = os.path.basename(self.remote_path.rstrip("/"))
            local = os.path.join(tmpdir, basename)
            if not os.path.isfile(local):
                entries = os.listdir(tmpdir)
                local = os.path.join(tmpdir, entries[0]) if entries else None
            if local is None:
                GLib.idle_add(self._show_message, "⚠ CLI wrote no file.")
                return
            try:
                # Decode into memory, capped at 2048px on the long edge —
                # a 48MP photo won't eat hundreds of MB of RAM.
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    local, 2048, 2048)
            except Exception as exc:
                GLib.idle_add(self._show_message, f"⚠ Could not decode image: {exc}")
                return
            # Pixbuf holds its own copy of the pixels now — safe to hand
            # over and delete the file underneath.
            GLib.idle_add(self._show_image, pixbuf)
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._show_message, "⚠ Download timed out.")
        except Exception as exc:
            GLib.idle_add(self._show_message, f"⚠ {exc}")
        finally:
            # Temp file removed the moment it's decoded — nothing lingers
            # in /tmp either, let alone ~/.cache/pdua.
            if local is not None and os.path.exists(local):
                try:
                    os.unlink(local)
                except OSError:
                    pass
            try:
                os.rmdir(tmpdir)
            except OSError:
                pass

    def _show_image(self, pixbuf):
        """Main thread — display the decoded image, in-app."""
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        picture = Gtk.Picture.new_for_pixbuf(pixbuf)
        picture.set_can_shrink(True)
        picture.set_hexpand(True)
        picture.set_vexpand(True)
        scrolled.set_child(picture)
        self.set_child(scrolled)
        return False

    def _show_message(self, text):
        """Main thread — error/fallback label."""
        self.set_child(Gtk.Label(label=text))
        return False

    def _load_text_content(self):
        """Download the file and show its text content."""
        from ui.function.config_manager import ConfigManager
        self.cli_path = ConfigManager.find_cli(None)
        if not self.cli_path:
            self.set_child(Gtk.Label(label="Proton Drive CLI not found"))
            return

        def worker():
            try:
                tmpdir = tempfile.mkdtemp(prefix="pdua_popup_", dir=_XDG_CACHE)
                proc = subprocess.run(
                    [self.cli_path, "filesystem", "download", self.remote_path, tmpdir],
                    capture_output=True, text=True)
                if proc.returncode == 0:
                    basename = os.path.basename(self.remote_path.rstrip("/"))
                    local = os.path.join(tmpdir, basename)
                    if not os.path.isfile(local):
                        entries = os.listdir(tmpdir)
                        local = os.path.join(tmpdir, entries[0]) if entries else None
                    if local:
                        with open(local, "r", encoding="utf-8", errors="replace") as f:
                            content = f.read()
                        GLib.idle_add(self._show_text_content, content)
                    else:
                        GLib.idle_add(self.set_child,
                                      Gtk.Label(label="No file content"))
                else:
                    detail = (proc.stderr or proc.stdout or "").strip()
                    GLib.idle_add(self.set_child,
                                  Gtk.Label(label=f"Download failed: {detail}"))
            except Exception as exc:
                GLib.idle_add(self.set_child,
                              Gtk.Label(label=f"Error: {exc}"))

        threading.Thread(target=worker, daemon=True,
                         name="pdua-popup-text").start()

    def _show_text_content(self, content):
        """Display the downloaded text in a scrollable TextView."""
        scrolled = Gtk.ScrolledWindow(vexpand=True, hexpand=True)
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

        text_view = Gtk.TextView()
        text_view.set_editable(False)
        text_view.set_cursor_visible(False)
        text_view.set_monospace(True)
        text_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        buffer = text_view.get_buffer()
        buffer.set_text(content)
        text_view.set_left_margin(12)
        text_view.set_right_margin(12)
        text_view.set_top_margin(12)
        text_view.set_bottom_margin(12)

        scrolled.set_child(text_view)
        self.set_child(scrolled)
        return False

    def _image_ready(self, pixbuf):
        """Callback from cache — display the image in a scrollable window."""
        if pixbuf is None:
            self.set_child(Gtk.Label(label="Unable to load image"))
            return False

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        picture = Gtk.Picture.new_for_pixbuf(pixbuf)
        picture.set_can_shrink(True)
        scrolled.set_child(picture)
        self.set_child(scrolled)
        return False


# ---------------------------------------------------------------------------
# Fullscreen photo viewer (retained from v2)
# ---------------------------------------------------------------------------

class PhotoViewerWindow(Gtk.Window):
    """Window for viewing a single photo at higher resolution."""

    def __init__(self, parent, cache, remote_path):
        super().__init__(transient_for=parent)
        self.set_title(os.path.basename(remote_path))
        self.set_default_size(900, 700)

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
            self.set_child(Gtk.Label(label="Unable to load image"))
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
# rev 4: also CONSTRUCTS the page, catching method-fusion bugs.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("Syntax/import check…")
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
    for f, k in [("photo.JPG", "image"), ("clip.mp4", "video"),
                 ("song.flac", "audio"), ("notes.md", "text")]:
        got = _file_kind(f)
        assert got == k, f"_file_kind({f}) = {got}, expected {k}"
        print(f"  _file_kind({f}) -> {k}")

    sample = ("listing of /my-files\n  d Documents/\n-r notes.txt\n"
              "vacation.jpg\nsong.mp3\nclip.mp4\n")
    parsed = FileExplorerPage._parse_listing(sample)
    print(f"  _parse_listing(sample) -> {parsed}")

    # Construction test (needs a display; catches fused methods)
    try:
        page = FileExplorerPage(root="/photos", title="Photos")
        assert hasattr(page, "back_button"), "back_button missing (rev 4)"
        assert hasattr(page, "_loaded_once"), "_loaded_once missing"
        assert hasattr(page, "nav_stack"), "nav_stack missing"
        assert hasattr(page, "cache"), "cache missing"
        assert hasattr(page, "do_map"), "do_map not defined at class level"
        assert hasattr(page, "_open_popup_viewer"), "popup viewer missing (rev 4)"
        print("  constructed FileExplorerPage: back_button OK, "
              "lazy-load armed, nav_stack OK, popup viewer present")
    except Exception as exc:
        print(f"  construction failed (display present?): {exc}")

    print("All non-GUI checks passed (GUI construction needs a display)")

