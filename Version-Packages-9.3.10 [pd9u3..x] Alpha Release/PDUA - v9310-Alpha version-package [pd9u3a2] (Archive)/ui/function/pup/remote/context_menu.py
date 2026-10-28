#!/usr/bin/env python3
"""
DriveContextMenu — GTK4 right-click menus for PDUA File Explorer
================================================================
FINAL VERSION. Fixes from prior drafts:
  * every action registered with GLib.VariantType("s") — matches the
    detailed action targets used by menu items
  * paths encoded via Gio.MenuItem.set_action_and_target_value +
    GLib.Variant (apostrophes / unicode safe — no string-interpolated
    action names)
  * right-click via GestureClick(button=3) + popover pointing-to cursor
    (a PopoverMenu is NOT an event controller — attach() is the right way)
  * dead confirm-stub duplicates removed

Integration — TWO steps:

1) ONCE per window (MainWindow or explorer page init):
       from ui.function.pup.remote.context_menu import ContextMenus
       ContextMenus.register(window=parent_window,
                             drive_ops=self.drive_ops,
                             refresh=self.reload_listing)

2) PER TILE (inside FileExplorerPage._add_tile):
       ContextMenus.attach(tile=card, remote_path=p, is_folder=flag,
                           open_folder=self.open_folder)

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from __future__ import annotations

import logging
from typing import Callable, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Gtk, Adw, Gio, GLib, Gdk

log = logging.getLogger("pdua.ctx")


# ---------------------------------------------------------------------------
# Toast helper
# ---------------------------------------------------------------------------

def _toast(window, message: str) -> None:
    """Show a toast if window exposes a 'toast_overlay' (Adw.ToastOverlay);
    otherwise just log. Never raises."""
    try:
        overlay = getattr(window, "toast_overlay", None)
        if overlay is not None:
            overlay.add_toast(Adw.Toast.new(message))
            return
    except Exception:
        pass
    log.info("%s", message)


# ---------------------------------------------------------------------------
# Dialogs
# ---------------------------------------------------------------------------

def _entry_dialog(parent_win, heading: str, body: str, placeholder: str,
                  ok_label: str, on_ok: Callable[[str], None]) -> None:
    """Adw.MessageDialog with a text entry; Enter triggers the OK response."""
    dialog = Adw.MessageDialog(transient_for=parent_win, heading=heading, body=body)
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
        if resp == "ok" and text:
            on_ok(text)
        dlg.destroy()

    dialog.connect("response", respond)
    dialog.present()
    entry.grab_focus()


def _typed_confirm_dialog(parent_win, heading: str, body: str,
                          confirm_word: str, ok_label: str,
                          on_confirmed: Callable[[], None]) -> None:
    """Destructive confirmation requiring the user to type confirm_word."""
    dialog = Adw.MessageDialog(transient_for=parent_win, heading=heading, body=body)
    entry = Gtk.Entry(hexpand=True)
    dialog.set_extra_child(entry)
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("ok", ok_label)
    dialog.set_response_appearance("ok", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response("ok")
    dialog.set_close_response("cancel")

    def respond(dlg, resp):
        if resp == "ok":
            if entry.get_text().strip().upper() == confirm_word:
                on_confirmed()
            else:
                _toast(parent_win, "Confirmation text did not match — nothing was done.")
        dlg.destroy()

    dialog.connect("response", respond)
    dialog.present()
    entry.grab_focus()


def prompt_rename(parent_win, remote_path, drive_ops, on_result=None) -> None:
    _entry_dialog(
        parent_win, "Rename",
        f"Current name: {remote_path.rsplit('/', 1)[-1]}\nEnter new name:",
        remote_path.rsplit("/", 1)[-1], "Rename",
        lambda name: drive_ops.rename(remote_path, name, on_result),
    )


def prompt_create_folder(parent_win, parent_path, drive_ops, on_result=None) -> None:
    _entry_dialog(
        parent_win, "New Folder", f"Location: {parent_path}",
        "Folder name", "Create",
        lambda name: drive_ops.create_folder(parent_path, name, on_result),
    )


def prompt_move_or_copy(parent_win, source, drive_ops, mode, on_result=None) -> None:
    pretty = "Move" if mode == "move" else "Copy"
    _entry_dialog(
        parent_win, f"{pretty} to Folder",
        f"{pretty} the following to which folder?\n{source}\n\nExample: /my-files/Documents",
        "/my-files/", pretty,
        lambda target: (
            drive_ops.move([source], target, on_result) if mode == "move"
            else drive_ops.copy([source], target, on_result)
        ),
    )


def confirm_trash(parent_win, paths, drive_ops, on_result=None) -> None:
    n = len(paths)
    dialog = Adw.MessageDialog(
        transient_for=parent_win, heading="Move to Trash",
        body=(f"Move {n} item(s) to Trash?" if n > 1
              else f"Move {paths[0].rsplit('/', 1)[-1]} to Trash?")
        + "\nTrashed items can be restored later.",
    )
    dialog.add_response("cancel", "Cancel")
    dialog.add_response("trash", "Move to Trash")
    dialog.set_response_appearance("trash", Adw.ResponseAppearance.DESTRUCTIVE)
    dialog.set_default_response("trash")
    dialog.set_close_response("cancel")

    def respond(dlg, resp):
        if resp == "trash":
            drive_ops.trash(paths, on_result)
        dlg.destroy()

    dialog.connect("response", respond)
    dialog.present()


def confirm_delete(parent_win, paths, drive_ops, on_result=None) -> None:
    listing = "\n".join(paths[:5]) + ("\n…" if len(paths) > 5 else "")
    _typed_confirm_dialog(
        parent_win, "Delete Permanently",
        f"This CANNOT be undone. {len(paths)} item(s):\n{listing}\n\nType DELETE to confirm.",
        "DELETE", "Delete Permanently",
        lambda: drive_ops.delete(paths, on_result),
    )


def confirm_empty_trash(parent_win, drive_ops, on_result=None) -> None:
    _typed_confirm_dialog(
        parent_win, "Empty Trash",
        "EVERYTHING in Trash will be permanently deleted.\nType EMPTY TRASH to confirm.",
        "EMPTY TRASH", "Empty Trash",
        lambda: drive_ops.empty_trash(on_result),
    )


# ---------------------------------------------------------------------------
# Action group (registered ONCE per window)
# ---------------------------------------------------------------------------

class ContextMenus:
    """Owns the 'ctx' action group and tile attachment."""

    @staticmethod
    def register(window, drive_ops, refresh: Optional[Callable] = None) -> None:
        """
        Install the ctx.* actions on a window. Call ONCE.

        Args:
            window:  Gtk/Adw window owning the actions (used for dialogs/toasts)
            drive_ops: DriveOps instance
            refresh:  callable invoked after a SUCCESSFUL mutation so the
                      explorer reloads its listing (e.g. self.reload_listing)
        """
        group = Gio.SimpleActionGroup()

        def finish(result):
            _toast(window, result.message)
            if result.ok and refresh:
                refresh()
            elif not result.ok:
                log.warning("op failed: %s | %s", result.message, result.detail[:300])

        def add(name: str, handler: Callable[[str], None]) -> None:
            action = Gio.SimpleAction.new(name, GLib.VariantType("s"))
            action.connect("activate", lambda _a, param: handler(param.get_string()))
            group.add_action(action)

        add("open", lambda p: getattr(window, "current_explorer_page", None)
            and getattr(window.current_explorer_page, "open_folder", lambda _p: None)(p))

        add("rename", lambda p: prompt_rename(window, p, drive_ops, finish))
        add("move", lambda p: prompt_move_or_copy(window, p, drive_ops, "move", finish))
        add("copy", lambda p: prompt_move_or_copy(window, p, drive_ops, "copy", finish))
        add("trash", lambda p: confirm_trash(window, [p], drive_ops, finish))
        add("delete", lambda p: confirm_delete(window, [p], drive_ops, finish))
        add("new-folder", lambda p: prompt_create_folder(window, p, drive_ops, finish))
        add("open-file", lambda p: drive_ops.open_remote_file(p, finish))

        window.insert_action_group("ctx", group)
        window._pdua_ctx_state = {"drive_ops": drive_ops}  # kept for attach()

    # -------------------------------------------------------------------

    @staticmethod
    def build_menu(remote_path: str, is_folder: bool) -> Gio.Menu:
        """Build the Gio.Menu for one tile. Paths encoded as GVariant targets."""

        def item(label: str, action_name: str, path: str) -> Gio.MenuItem:
            mi = Gio.MenuItem.new(label, None)
            mi.set_action_and_target_value(action_name, GLib.Variant("s", path))
            return mi

        menu = Gio.Menu()

        if is_folder:
            menu.append_item(item("Open", "ctx.open", remote_path))
            menu.append_item(item("New Folder Here", "ctx.new-folder", remote_path))
            menu.append_section(None, Gio.Menu())  # separator
        else:
            menu.append_item(item("Open", "ctx.open-file", remote_path))

        menu.append_item(item("Rename…", "ctx.rename", remote_path))
        menu.append_item(item("Move to…", "ctx.move", remote_path))
        menu.append_item(item("Copy to…", "ctx.copy", remote_path))
        menu.append_section(None, Gio.Menu())  # separator

        menu.append_item(item("Move to Trash", "ctx.trash", remote_path))
        menu.append_item(item("Delete Permanently…", "ctx.delete", remote_path))

        return menu

    # -------------------------------------------------------------------

    @staticmethod
    def attach(tile: Gtk.Widget, remote_path: str, is_folder: bool,
               open_folder: Optional[Callable[[str], None]] = None) -> None:
        """
        Wire right-click (button 3) onto a tile. If open_folder is provided
        (preferred), left-click navigation stays owned by the page; the
        ctx.open menu action falls back to it via the window's explorer page.
        """
        menu = ContextMenus.build_menu(remote_path, is_folder)
        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(tile)
        popover.set_has_arrow(False)
        popover.set_position(Gtk.PositionType.BOTTOM)

        gesture = Gtk.GestureClick(button=3)

        def on_right_release(g, _n, x, y):
            rect = Gdk.Rectangle()
            rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
            popover.set_pointing_to(rect)
            popover.popup()
            # stash fallback for ctx.open if the page gave us one
            if open_folder is not None:
                ContextMenus._open_fallback = open_folder

        gesture.connect("released", on_right_release)
        tile.add_controller(gesture)

    # fallback holder for ctx.open when page supplies open_folder directly
    _open_fallback: Optional[Callable[[str], None]] = None
