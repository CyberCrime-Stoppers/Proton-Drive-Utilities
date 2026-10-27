#!/usr/bin/env python3

from __future__ import annotations

import logging
import shutil
import subprocess
import threading
from dataclasses import dataclass
from typing import Callable, Iterable, Optional, Sequence

import gi

gi.require_version("GLib", "2.0")
from gi.repository import GLib

log = logging.getLogger("pdua.ops")

QUICK_TIMEOUT = 60      # rename, mkdir, trash, restore, delete
HEAVY_TIMEOUT = 900     # move, copy, empty-trash (server-side, can be slow)
MAX_NAME_LEN = 250

_RESERVED = {"", ".", ".."}


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class OpError(ValueError):
    """Raised when a path or name fails validation."""


def validate_name(name: str) -> str:
    """Validate a single path component (new name, new folder name)."""
    if not isinstance(name, str):
        raise OpError("Name must be text.")
    name = name.strip()
    if name in _RESERVED:
        raise OpError("Name cannot be empty, '.' or '..'.")
    if "/" in name or "\\" in name:
        raise OpError("Name cannot contain a path separator.")
    if "\x00" in name:
        raise OpError("Name contains a null byte.")
    if len(name) > MAX_NAME_LEN:
        raise OpError(f"Name exceeds {MAX_NAME_LEN} characters.")
    return name


def validate_path(path: str) -> str:
    """Validate and canonicalise an absolute remote path."""
    if not isinstance(path, str) or not path:
        raise OpError("Path must be a non-empty string.")
    if "\x00" in path:
        raise OpError("Path contains a null byte.")
    if not path.startswith("/"):
        raise OpError("Remote paths must be absolute (begin with '/').")
    if "//" in path:
        raise OpError("Path contains an empty component ('//').")
    parts = [p for p in path.split("/") if p]
    for p in parts:
        if p in (".", ".."):
            raise OpError("Path may not contain '.' or '..' components.")
    return "/" + "/".join(parts)


def validate_target(source: str, target_parent: str) -> str:
    """Reject moves/copies into the source itself or a descendant of it."""
    src = validate_path(source)
    tgt = validate_path(target_parent)
    if tgt == src:
        raise OpError("Destination is the same as the source.")
    if tgt.startswith(src + "/"):
        raise OpError("Cannot move or copy a folder into itself.")
    return tgt


# ---------------------------------------------------------------------------
# Result object
# ---------------------------------------------------------------------------

@dataclass
class OpResult:
    ok: bool
    op: str
    message: str
    detail: str = ""


# ---------------------------------------------------------------------------
# DriveOps
# ---------------------------------------------------------------------------

class DriveOps:
    """Asynchronous, validated wrappers around the Proton Drive CLI."""

    def __init__(self, cli_path: Optional[str] = None):
        self.cli = cli_path or self._resolve_cli()
        self._busy: set[str] = set()
        self._busy_lock = threading.Lock()

    # -- CLI discovery ------------------------------------------------------

    @staticmethod
    def _resolve_cli() -> Optional[str]:
        try:
            from ui.function.config_manager import ConfigManager
            found = ConfigManager.find_cli(None)
            if found:
                return found
        except Exception as exc:
            log.debug("ConfigManager.find_cli unavailable: %s", exc)
        return shutil.which("proton-drive")

    # -- Public operations --------------------------------------------------
    # Every method takes on_done: Callable[[OpResult], None], invoked on the
    # GTK main thread. on_done may be None for fire-and-forget.

    def create_folder(self, parent: str, name: str, on_done=None):
        try:
            parent = validate_path(parent)
            name = validate_name(name)
        except OpError as exc:
            return self._fail("create-folder", str(exc), on_done)
        self._run_async(
            "create-folder",
            [self.cli, "filesystem", "create-folder", parent, name],
            on_done, QUICK_TIMEOUT, guards=[parent],
        )

    def rename(self, path: str, new_name: str, on_done=None):
        try:
            path = validate_path(path)
            new_name = validate_name(new_name)
        except OpError as exc:
            return self._fail("rename", str(exc), on_done)
        self._run_async(
            "rename",
            [self.cli, "filesystem", "rename", path, new_name],
            on_done, QUICK_TIMEOUT, guards=[path],
        )

    def move(self, sources: Sequence[str], target_parent: str, on_done=None):
        try:
            sources = [validate_path(s) for s in sources]
            if not sources:
                raise OpError("Nothing selected.")
            target_parent = validate_target(sources[0], target_parent)
        except OpError as exc:
            return self._fail("move", str(exc), on_done)
        self._run_async(
            "move",
            [self.cli, "filesystem", "move", *sources, target_parent],
            on_done, HEAVY_TIMEOUT, guards=sources + [target_parent],
        )

    def copy(self, sources: Sequence[str], target_parent: str, on_done=None):
        try:
            sources = [validate_path(s) for s in sources]
            if not sources:
                raise OpError("Nothing selected.")
            target_parent = validate_target(sources[0], target_parent)
        except OpError as exc:
            return self._fail("copy", str(exc), on_done)
        self._run_async(
            "copy",
            [self.cli, "filesystem", "copy", *sources, target_parent],
            on_done, HEAVY_TIMEOUT, guards=sources + [target_parent],
        )

    def trash(self, paths: Iterable[str], on_done=None):
        try:
            paths = [validate_path(p) for p in paths]
            if not paths:
                raise OpError("Nothing selected.")
        except OpError as exc:
            return self._fail("trash", str(exc), on_done)
        self._run_async(
            "trash",
            [self.cli, "filesystem", "trash", *paths],
            on_done, QUICK_TIMEOUT, guards=paths,
        )

    def restore(self, paths: Iterable[str], on_done=None):
        try:
            paths = [validate_path(p) for p in paths]
            if not paths:
                raise OpError("Nothing selected.")
        except OpError as exc:
            return self._fail("restore", str(exc), on_done)
        self._run_async(
            "restore",
            [self.cli, "filesystem", "restore", *paths],
            on_done, QUICK_TIMEOUT, guards=paths,
        )

    def delete(self, paths: Iterable[str], on_done=None):
        """PERMANENT deletion. The UI layer must confirm before calling this."""
        try:
            paths = [validate_path(p) for p in paths]
            if not paths:
                raise OpError("Nothing selected.")
        except OpError as exc:
            return self._fail("delete", str(exc), on_done)
        self._run_async(
            "delete",
            [self.cli, "filesystem", "delete", *paths],
            on_done, QUICK_TIMEOUT, guards=paths,
        )

    def empty_trash(self, on_done=None):
        """PERMANENT. The UI layer must require typed confirmation."""
        self._run_async(
            "empty-trash",
            [self.cli, "filesystem", "empty-trash"],
            on_done, HEAVY_TIMEOUT, guards=["/trash"],
        )

    def open_remote_file(self, remote_path: str, on_done=None):
        """Download to a temp dir and hand the file to the desktop's default app."""
        try:
            remote_path = validate_path(remote_path)
        except OpError as exc:
            return self._fail("open", str(exc), on_done)

        if not self.cli:
            return self._fail("open", "Proton Drive CLI not found.", on_done)

        import os
        import tempfile

        def worker():
            result = None
            try:
                tmpdir = tempfile.mkdtemp(prefix="pdua_open_")
                proc = subprocess.run(
                    [self.cli, "filesystem", "download", remote_path, tmpdir],
                    capture_output=True, text=True, timeout=HEAVY_TIMEOUT,
                )
                if proc.returncode != 0:
                    detail = (proc.stdout or "") + (proc.stderr or "")
                    result = OpResult(False, "open", self._summarise("open", False, detail), detail.strip())
                else:
                    basename = os.path.basename(remote_path.rstrip("/"))
                    local = os.path.join(tmpdir, basename)
                    if not os.path.isfile(local):
                        entries = os.listdir(tmpdir)
                        if entries:
                            local = os.path.join(tmpdir, entries[0])
                        else:
                            raise FileNotFoundError("CLI reported success but wrote no file")
                    result = OpResult(True, "open", f"Opening {basename}…")
                    GLib.idle_add(self._launch_local, local)
            except Exception as exc:
                result = OpResult(False, "open", f"Open failed: {exc}")
            if result is not None:
                log.info("op=open ok=%s msg=%s", result.ok, result.message)
                if on_done:
                    GLib.idle_add(on_done, result)

        threading.Thread(target=worker, daemon=True, name="pdua-op-open").start()

    # -- Internals ----------------------------------------------------------

    @staticmethod
    def _launch_local(local_path: str) -> bool:
        """Hand a downloaded file to the desktop. Runs on the main thread."""
        try:
            gi.require_version("Gtk", "4.0")
            from gi.repository import Gio, Gtk

            gfile = Gio.File.new_for_path(local_path)
            if hasattr(Gtk, "FileLauncher"):          # GTK >= 4.10
                Gtk.FileLauncher.new(gfile).launch(None, None, None)
            else:
                Gio.AppInfo.launch_default_for_uri(gfile.get_uri(), None)
        except Exception as exc:
            log.error("Could not open %s: %s", local_path, exc)
        return False

    def _fail(self, op: str, message: str, on_done):
        result = OpResult(False, op, message)
        log.warning("op=%s rejected: %s", op, message)
        if on_done:
            GLib.idle_add(on_done, result)
        return result

    def _run_async(self, op: str, argv: list, on_done, timeout: int, guards: Optional[list] = None):
        if not self.cli:
            return self._fail(op, "Proton Drive CLI not found — set it in Options.", on_done)

        guards = list(guards or [])
        with self._busy_lock:
            clash = [g for g in guards if g in self._busy]
            if clash:
                return self._fail(op, "Another operation is already running on this item.", on_done)
            self._busy.update(guards)

        def worker():
            result = None
            try:
                proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
                detail = (proc.stdout or "") + (proc.stderr or "")
                ok = proc.returncode == 0
                result = OpResult(ok, op, self._summarise(op, ok, detail), detail.strip())
            except subprocess.TimeoutExpired:
                result = OpResult(False, op, f"{op.replace('-', ' ').capitalize()} timed out after {timeout}s.")
            except FileNotFoundError:
                result = OpResult(False, op, "Proton Drive CLI not found.")
            except Exception as exc:
                result = OpResult(False, op, f"{op.replace('-', ' ').capitalize()} failed: {exc}")
            finally:
                with self._busy_lock:
                    for g in guards:
                        self._busy.discard(g)

            if result is None:
                result = OpResult(False, op, "Operation failed unexpectedly.")

            log.info("op=%s ok=%s msg=%s", op, result.ok, result.message)
            if not result.ok and result.detail:
                log.debug("op=%s detail=%s", op, result.detail)

            if on_done:
                GLib.idle_add(on_done, result)

        threading.Thread(target=worker, daemon=True, name=f"pdua-op-{op}").start()

    @staticmethod
    def _summarise(op: str, ok: bool, detail: str) -> str:
        pretty = op.replace("-", " ").capitalize()
        if ok:
            return f"{pretty} complete."
        lines = [ln.strip() for ln in (detail or "").splitlines() if ln.strip()]
        reason = lines[-1] if lines else "no output from CLI"
        return f"{pretty} failed: {reason}"


# Manual smoke test: python3 -m ui.function.pup.remote.drive_ops
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    ops = DriveOps()
    print(f"CLI resolved to: {ops.cli}")
    for probe in ["", "relative/path", "/a//b", "/../etc", "/ok/path"]:
        try:
            print(f"  validate_path({probe!r}) -> {validate_path(probe)}")
        except OpError as exc:
            print(f"  validate_path({probe!r}) -> REJECTED: {exc}")
    for probe in ["", ".", "..", "a/b", "normal name.txt"]:
        try:
            print(f"  validate_name({probe!r}) -> {validate_name(probe)}")
        except OpError as exc:
            print(f"  validate_name({probe!r}) -> REJECTED: {exc}")
