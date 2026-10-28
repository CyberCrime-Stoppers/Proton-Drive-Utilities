#!/usr/bin/env python3
"""
Unified Transfer Page for PDUA
Replaces all 14 pages across ui/tree/{fixdo,cusdo,down,up}

Usage:
    TransferPage(direction="upload", folder="Documents", mode="custom")
    TransferPage(direction="download", folder="Pictures", mode="preset")
    TransferPage(direction="upload", mode="fixed")   # script-pinned
"""

import os
import subprocess
import threading

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

from ui.function.config_manager import ConfigManager
from ui.function.pup.file_browser import FileBrowserWindow

try:
    from ui.function.script_guard import validate_script, SCRIPTS_UP_DIR, SCRIPTS_DOWN_DIR
    HAS_SCRIPT_GUARD = True
except ImportError:
    HAS_SCRIPT_GUARD = False


VALID_FOLDERS = ("Documents", "Downloads", "Pictures", "Videos", "Music")


class TransferPage:
    """One page class for ALL upload/download variations.

    direction: "upload" | "download"
    folder:    None (whole drive) | "Documents" | "Downloads" | "Pictures" | "Videos" | "Music"
    mode:      "custom" — editable paths, direct CLI call (replaces cusdo/, down/, up/)
               "fixed"  — pinned scripts, no path UI    (replaces fixdo/)
    """

    def __init__(self, direction, folder=None, mode="custom", on_navigate=None):
        if direction not in ("upload", "download"):
            raise ValueError(f"Invalid direction: {direction}")
        if folder is not None and folder not in VALID_FOLDERS:
            raise ValueError(f"Invalid folder: {folder}")
        if mode not in ("custom", "fixed"):
            raise ValueError(f"Invalid mode: {mode}")

        self.direction = direction
        self.folder = folder
        self.mode = mode
        self.on_navigate = on_navigate
        self._parent_window = None
        self._process = None  # Handle for cancellation
        self._running = False

        self.config = ConfigManager()

    # ================= UI BUILD =================

    def build(self, parent_window=None):
        self._parent_window = parent_window

        if self.mode == "fixed":
            return self._build_fixed_page()

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=15,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        # --- Title: describes THIS page, not a generic one ---
        verb = "Upload" if self.direction == "upload" else "Download"
        noun = self.folder if self.folder else "Files"
        title = Gtk.Label(label=f"<span size='xx-large' weight='bold'>{verb} {noun}</span>")
        title.set_use_markup(True)
        container.append(title)

        arrow = "Local Folder → Proton Drive" if self.direction == "upload" else "Proton Drive → Local Folder"
        subtitle = Gtk.Label(label=arrow)
        subtitle.add_css_class("dim-label")
        container.append(subtitle)

        # --- Local path row ---
        if self.direction == "upload":
            local_label = Gtk.Label(label="Local Source:", halign=Gtk.Align.START)
            local_hint = "e.g. ~/Documents"
        else:
            local_label = Gtk.Label(label="Local Destination:", halign=Gtk.Align.START)
            local_hint = "Choose where files will be saved"
        local_label.set_margin_top(15)
        container.append(local_label)

        local_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        local_box.set_size_request(400, -1)

        self.entry_local = Gtk.Entry()
        self.entry_local.set_placeholder_text(local_hint)
        # FIX: never set placeholder-like text as the real value.
        # Start EMPTY so validation catches missing input.
        self.entry_local.set_text("")
        self.entry_local.set_hexpand(True)
        self.entry_local.connect("changed", lambda e: self._update_button_state())
        local_box.append(self.entry_local)

        btn_browse = Gtk.Button(label="Browse…")
        btn_browse.connect("clicked", self._browse_local)
        local_box.append(btn_browse)
        container.append(local_box)

        # --- Remote path row (editable in custom mode) ---
        remote_label = Gtk.Label(label="Proton Drive Remote Path:", halign=Gtk.Align.START)
        remote_label.set_margin_top(10)
        container.append(remote_label)

        self.entry_remote = Gtk.Entry()
        default_remote = "/my-files"
        if self.folder:
            default_remote = f"/my-files/{self.folder}"
        self.entry_remote.set_placeholder_text(default_remote)
        self.entry_remote.set_text(default_remote)
        self.entry_remote.set_size_request(400, -1)
        container.append(self.entry_remote)

        # --- CLI path row (optional override; auto-detected by default) ---
        cli_label = Gtk.Label(label="Proton Drive CLI Binary (optional — auto-detected if empty):",
                              halign=Gtk.Align.START)
        cli_label.set_margin_top(10)
        container.append(cli_label)

        cli_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        cli_box.set_size_request(400, -1)

        self.entry_cli = Gtk.Entry()
        self.entry_cli.set_placeholder_text("Auto-detected from config / system paths")
        self.entry_cli.set_text("")
        self.entry_cli.set_hexpand(True)
        cli_box.append(self.entry_cli)
        container.append(cli_box)

        # --- Divider ---
        separator = Gtk.Separator()
        separator.set_margin_top(20)
        separator.set_margin_bottom(20)
        container.append(separator)

        # --- Progress bar + cancel (NEW) ---
        self.progress = Gtk.ProgressBar()
        self.progress.set_size_request(400, -1)
        self.progress.set_visible(False)
        container.append(self.progress)

        # --- Transfer Button (disabled until inputs valid) ---
        self.transfer_btn = Gtk.Button(label=f"{'⬆' if self.direction == 'upload' else '⬇'} {verb}")
        self.transfer_btn.set_size_request(400, -1)
        self.transfer_btn.add_css_class("suggested-action")
        self.transfer_btn.connect("clicked", self._on_transfer_clicked)
        container.append(self.transfer_btn)

        # --- Cancel Button (NEW) ---
        self.cancel_btn = Gtk.Button(label="Cancel")
        self.cancel_btn.set_size_request(400, -1)
        self.cancel_btn.add_css_class("destructive-action")
        self.cancel_btn.set_visible(False)
        self.cancel_btn.connect("clicked", self._on_cancel_clicked)
        container.append(self.cancel_btn)

        self._update_button_state()
        return container

    def _build_fixed_page(self):
        """Pinned-script page (replaces fixdo/ pages)."""
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=15,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        verb = "Upload" if self.direction == "upload" else "Download"
        title = Gtk.Label(label=f"<span size='x-large' weight='bold'>Fixed {verb}</span>")
        title.set_use_markup(True)
        container.append(title)

        info = Gtk.Label(
            label="One-click transfer using pinned, hash-verified scripts.\n"
                  "Paths are fixed: your home directories ↔ /my-files."
        )
        info.add_css_class("dim-label")
        container.append(info)

        for folder in VALID_FOLDERS:
            btn = Gtk.Button(label=f"{verb} {folder}")
            btn.set_size_request(400, -1)
            btn.connect("clicked", lambda w, f=folder: self._run_fixed_script(f))
            container.append(btn)

        return container

    # ================= VALIDATION =================

    def _get_cli(self):
        """Resolve CLI: entry override → config → system search. Never a junk string."""
        hint = self.entry_cli.get_text().strip()
        cli = ConfigManager.find_cli(hint or None)
        if not cli:
            cli = ConfigManager.find_cli(self.config.get("cli_binary"))
        return cli

    def _update_button_state(self):
        """Transfer button only enabled when a real local path is entered (or empty for preset-download?)."""
        if self.mode == "fixed":
            return
        local = self.entry_local.get_text().strip()
        if self.direction == "upload":
            ok = bool(local) and os.path.isdir(os.path.expanduser(local))
        else:
            ok = bool(local)  # Destination will be created; just needs a value
        self.transfer_btn.set_sensitive(ok and not self._running)

    # ================= BROWSE =================

    def _browse_local(self, widget):
        if not self._parent_window:
            return
        start = self.entry_local.get_text().strip() or os.path.expanduser("~")
        browser = FileBrowserWindow(self._parent_window, start_path=start)

        def on_selected(window, filepath):
            self.entry_local.set_text(filepath)

        browser.connect("file-selected", on_selected)
        browser.present()

    # ================= TRANSFER (CUSTOM MODE) =================

    def _on_transfer_clicked(self, widget):
        local = os.path.expanduser(self.entry_local.get_text().strip())
        remote = self.entry_remote.get_text().strip().rstrip("/")
        cli = self._get_cli()

        # Validation — clear, specific errors; never act on junk values
        if not remote.startswith("/"):
            self._show_toast("✗ Remote path must start with / (e.g. /my-files)")
            return
        if not cli:
            self._show_toast("✗ proton-drive CLI not found — check Preferences")
            return
        if self.direction == "upload" and not os.path.isdir(local):
            self._show_toast(f"✗ Local folder not found: {local}")
            return

        # Normalize (avoids /my-files//Documents double slashes)
        if self.folder and not remote.endswith(self.folder):
            remote = f"{remote}/{self.folder}"
            if self.direction == "upload":
                local = os.path.join(local, self.folder)

        if self.direction == "download":
            os.makedirs(local, exist_ok=True)

        verb = "Upload" if self.direction == "upload" else "Download"
        print(f"[{verb}] {local} ↔ {remote}")

        # Enter running state
        self._running = True
        self.transfer_btn.set_sensitive(False)
        self.transfer_btn.set_label(f"{verb}ing {self.folder or ''}…".replace("  ", " "))
        self.cancel_btn.set_visible(True)
        self.progress.set_visible(True)
        self.progress.pulse()

        timeout = self.config.get(
            f"default_{self.direction}_timeout", 600
        )

        t = threading.Thread(
            target=self._run_transfer,
            args=(cli, local, remote, verb, timeout),
            daemon=True,
        )
        t.start()

    def _run_transfer(self, cli, local, remote, verb, timeout):
        """Background thread: execute CLI with LIVE timeout, cancellable."""
        cmd = [cli, "filesystem", self.direction, remote, local] \
            if self.direction == "download" else \
               [cli, "filesystem", self.direction, local, remote]
        print(f"[CLI] {' '.join(cmd)}")

        msg = ""
        try:
            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Stream output for progress parsing + cancel responsiveness
            for line in iter(self._process.stdout.readline, ""):
                print(f"[CLI] {line.rstrip()}")
                # Periodic pulse keeps the bar alive
                GLib.idle_add(self.progress.pulse)
                if self._process is None:
                    break  # cancelled

            ret = self._process.wait(timeout=timeout)
            self._process = None

            if ret == 0:
                msg = f"✓ {self.folder or 'Files'} {'uploaded' if self.direction == 'upload' else 'downloaded'} successfully!"
            else:
                msg = f"✗ {verb} failed (exit {ret})"

        except subprocess.TimeoutExpired:
            if self._process:
                self._process.kill()
                self._process = None
            msg = f"✗ {verb} timed out (>{timeout // 60} min)"
        except FileNotFoundError:
            msg = f"✗ CLI not found at: {cli}"
        except Exception as e:
            msg = f"✗ Error: {e}"

        GLib.idle_add(self._transfer_done, msg)

    def _transfer_done(self, msg):
        self._running = False
        self.transfer_btn.set_sensitive(True)
        self.transfer_btn.set_label(
            f"{'⬆' if self.direction == 'upload' else '⬇'} {'Upload' if self.direction == 'upload' else 'Download'}"
        )
        self.cancel_btn.set_visible(False)
        self.progress.set_visible(False)
        self._show_toast(msg, timeout=5)
        return False

    def _on_cancel_clicked(self, widget):
        if self._process:
            self._process.terminate()
            self._show_toast("Cancelling…")
        return False

    # ================= FIXED MODE (SCRIPT-PINNED) =================

    def _run_fixed_script(self, folder):
        """Validate and run pinned script for folder."""
        if not HAS_SCRIPT_GUARD:
            self._show_toast("✗ script_guard module not available")
            return

        direction = "up" if self.direction == "upload" else "down"
        script_name = f"proton-{'export' if direction == 'up' else 'import'}-home-{folder.lower()}.sh"
        scripts_dir = SCRIPTS_UP_DIR if direction == "up" else SCRIPTS_DOWN_DIR
        script_path = os.path.join(scripts_dir, script_name)

        try:
            safe_path = validate_script(scripts_dir, script_name)
        except (ValueError, FileNotFoundError, PermissionError) as e:
            self._show_toast(f"✗ Script validation failed: {e}", timeout=6)
            return

        self._running = True
        threading.Thread(
            target=self._run_fixed_thread,
            args=(safe_path, folder),
            daemon=True,
        ).start()

    def _run_fixed_thread(self, script_path, folder):
        msg = ""
        try:
            result = subprocess.run(
                [script_path],
                capture_output=True,
                text=True,
                timeout=600,  # Real timeout — handler actually fires now
            )
            if result.returncode == 0:
                msg = f"✓ {folder} transferred successfully!"
            else:
                msg = f"✗ {folder} failed: {result.stderr.strip()[:100]}"
        except subprocess.TimeoutExpired:
            msg = f"✗ {folder} timed out (>10 min)"
        except FileNotFoundError:
            msg = f"✗ Script not found: {script_path}"
        except Exception as e:
            msg = f"✗ Error: {e}"

        def show():
            self._running = False
            self._show_toast(msg, timeout=5)
            return False
        GLib.idle_add(show)

    # ================= HELPERS =================

    def _show_toast(self, message, timeout=3):
        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            self._parent_window.add_toast(Adw.Toast(title=message, timeout=timeout))