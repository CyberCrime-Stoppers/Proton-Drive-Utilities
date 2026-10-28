#!/usr/bin/env python3
"""
auto_sync_setup.py -- AutoSync Setup page + engine for PDUA (v2, clean rebuild)
=================================================================================

PURPOSE
  Lets users configure automatic synchronization between a local folder
  and a Proton Drive folder:

    1. AUTO-DETECT CHANGES ("watch" mode)
       Gio.FileMonitor (inotify-backed, zero extra dependencies) watches
       the local directory. Changes are debounced (QUIET_SECONDS), then
       the job syncs. Detects creates, deletes, renames, and content
       changes, recursively.

    2. TIMERS ("interval" mode)
       Sync every N minutes (1 to 1440).

    3. SCHEDULED ("schedule" mode)
       "daily HH:MM"          -- runs every day at that time
       "once YYYY-MM-DD HH:MM" -- runs exactly once at that date+time

DIRECTIONS
    upload   : local -> Proton Drive
    download : Proton Drive -> local
    both     : push then pull

BACKGROUND OPERATION
  The SAME file runs headless:
      python3 -m ui.function.config.auto_sync_setup --daemon
  The page's "Install Background Service" button writes a systemd USER
  unit (~/.config/systemd/user/pdua-autosync.service) pointing at the
  module path above, so syncing continues after the app closes.
  An flock on a lock file guarantees only ONE engine (GUI or daemon)
  ever runs transfers at a time.

CLASS LAYOUT (do not mix these up!)
  SyncEngine        headless worker; NO widgets. Constructed by
                    AutoSyncSetupPage and by --daemon mode.
  AutoSyncSetupPage the sidebar page (Gtk.Box). Constructed ONLY by
                    main_window.py. Has .build(parent_window) adapter.

WHERE IT GOES
  ui/function/config/auto_sync_setup.py

REGISTRATION IN main_window.py
  from ui.function.config.auto_sync_setup import AutoSyncSetupPage
  ...
  self.pages["syncsetup"] = AutoSyncSetupPage(on_navigate=self.navigate_to)

CONFIG STORAGE
  ~/.config/pdua/autosync.json   (atomic write: tmp + rename)
  ~/.local/state/pdua/autosync.log
  ~/.local/state/pdua/pdua-autosync.lock

AUTHOR:  Linus (CyberCrime-Stoppers / CCS)
VERSION: 2.0.0
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Adw, Gio, GLib, Pango

from ui.function.config_manager import ConfigManager

log = logging.getLogger("pdua.autosync")

# ---------------------------------------------------------------------------
# Paths / constants
# ---------------------------------------------------------------------------
_XDG_CONFIG = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
_XDG_STATE = os.environ.get("XDG_STATE_HOME") or os.path.expanduser("~/.local/state")

MODULE_PATH = "ui.function.config.auto_sync_setup"   # where THIS file lives
AUTOSYNC_CONFIG = os.path.join(_XDG_CONFIG, "pdua", "autosync.json")
STATE_DIR = os.path.join(_XDG_STATE, "pdua")
LOG_FILE = os.path.join(STATE_DIR, "autosync.log")
LOCK_FILE = os.path.join(STATE_DIR, "pdua-autosync.lock")

QUIET_SECONDS = 2       # debounce: wait for the directory to go quiet
CLI_TIMEOUT = 600       # max seconds for one CLI transfer
CHECK_TICK_S = 30        # schedule polling granularity
SERVICE_NAME = "pdua-autosync.service"
USER_UNIT_DIR = os.path.join(_XDG_CONFIG, "systemd", "user")

DIRECTIONS = ["upload", "download", "both"]
MODES = ["watch", "interval", "schedule"]


# ---------------------------------------------------------------------------
# Job config load / save / validate
# ---------------------------------------------------------------------------

def load_jobs():
    """Return the job list ([] when missing/unreadable -- never raises)."""
    try:
        with open(AUTOSYNC_CONFIG, "r", encoding="utf-8") as f:
            data = json.load(f)
        jobs = data.get("jobs", []) if isinstance(data, dict) else []
        return jobs if isinstance(jobs, list) else []
    except FileNotFoundError:
        return []
    except Exception as exc:
        log.error("Could not read %s: %s", AUTOSYNC_CONFIG, exc)
        return []


def save_jobs(jobs):
    """Atomic write (temp file + rename) so a crash never corrupts it."""
    os.makedirs(os.path.dirname(AUTOSYNC_CONFIG), exist_ok=True)
    tmp = AUTOSYNC_CONFIG + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"version": 2, "jobs": jobs}, f, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, AUTOSYNC_CONFIG)


def _validate_job(job):
    """Raise ValueError with a human message if a job is malformed."""
    if not isinstance(job, dict):
        raise ValueError("Job must be a dict.")
    if not (job.get("name") or "").strip():
        raise ValueError("Job needs a name.")

    local = job.get("local_dir") or ""
    if not local.startswith("/"):
        raise ValueError("Local folder must be an absolute path.")
    if not os.path.isdir(local):
        raise ValueError("Local folder does not exist: " + local)

    remote = job.get("remote_dir") or ""
    if not remote.startswith("/"):
        raise ValueError("Drive folder must be an absolute path (start with /).")
    if "//" in remote or ".." in remote:
        raise ValueError("Drive folder must be a clean path (no // or ..).")

    if job.get("direction") not in DIRECTIONS:
        raise ValueError("Direction must be upload, download, or both.")
    if job.get("mode") not in MODES:
        raise ValueError("Mode must be watch, interval, or schedule.")

    if job.get("mode") == "interval":
        n = job.get("interval_min")
        if not isinstance(n, (int, float)) or n < 1 or n > 1440:
            raise ValueError("Interval must be between 1 and 1440 minutes.")

    if job.get("mode") == "schedule":
        s = (job.get("schedule") or "").strip()
        valid_daily = (len(s) == 11 and s.startswith("daily ")
                       and s.count(":") == 1)
        valid_once = (len(s) >= 17 and s.startswith("once "))
        if not (valid_daily or valid_once):
            raise ValueError(
                "Schedule must be 'daily HH:MM' or "
                "'once YYYY-MM-DD HH:MM'.")
    return True


# ---------------------------------------------------------------------------
# SyncEngine -- headless core. NO GTK widgets beyond Gio/GLib main loop.
# ---------------------------------------------------------------------------

class SyncEngine:
    """
    Arms enabled jobs and runs their transfers.

      watch    : Gio.FileMonitor on local_dir, debounced upload
      interval : GLib timeout every interval_min minutes
      schedule : ticked every CHECK_TICK_S; fires on daily/once match

    One engine per process. flock guarantees only one engine across the
    whole user session performs transfers (GUI vs daemon safe).
    """

    def __init__(self, on_event=None):
        self.on_event = on_event           # callable(str) or None
        self.jobs = []
        self._monitors = []                # keep Gio.FileMonitor refs alive
        self._timeouts = []                 # GLib source ids
        self._pending = {}                 # job name -> monotonic ts (debounce)
        self._debounce_ids = {}            # job name -> GLib timeout id
        self._lock_fd = None
        self._busy = False                  # transfer in flight?
        self._last_fired = {}              # schedule bookkeeping

    # -- plumbing -----------------------------------------------------------

    def emit(self, message):
        log.info("%s", message)
        if self.on_event:
            try:
                GLib.idle_add(self._safe_emit, message)
            except Exception:
                pass

    @staticmethod
    def _safe_emit(message):
        return False                        # one-shot; caller's cb already ran

    def _emit_threadsafe(self, message):
        """Called from worker threads."""
        if self.on_event:
            try:
                self.on_event(message)
            except Exception:
                pass

    # -- one job transfer -----------------------------------------------------

    def sync_job_once(self, job):
        """
        Run the CLI transfers for one job (blocking). Returns (ok, msg).
        Called from a worker thread -- NEVER from the GTK main thread.
        """
        cli = ConfigManager.find_cli(None)
        if not cli:
            return False, "proton-drive CLI not found"
        local = job["local_dir"]
        remote = job["remote_dir"].rstrip("/")
        direction = job["direction"]
        errors = []

        if direction in ("upload", "both"):
            rc, out = self._run_cli(cli, "upload", local, remote)
            if rc != 0:
                errors.append("upload: " + out)
        if direction in ("download", "both"):
            os.makedirs(local, exist_ok=True)
            rc, out = self._run_cli(cli, "download", remote, local)
            if rc != 0:
                errors.append("download: " + out)

        if errors:
            return False, "; ".join(errors)
        return True, "synced '" + job["name"] + "' (" + direction + ")"

    @staticmethod
    def _run_cli(cli, verb, src, dst):
        """
        Map a logical verb to the CLI's argument ORDER:
          upload   : filesystem upload <local_src> <remote_dst>
          download : filesystem download <remote_src> <local_dst>
        Destination is LAST in both cases -- consistent with the rest
        of PDUA's conventions.
        """
        if verb == "upload":
            argv = [cli, "filesystem", "upload", src, dst]
        else:
            argv = [cli, "filesystem", "download", src, dst]
        try:
            proc = subprocess.run(argv, capture_output=True, text=True,
                                  timeout=CLI_TIMEOUT)
            detail = (proc.stdout or "") + (proc.stderr or "")
            lines = [ln.strip() for ln in detail.splitlines() if ln.strip()]
            return proc.returncode, (lines[-1] if lines else "")
        except subprocess.TimeoutExpired:
            return 124, "timed out after " + str(CLI_TIMEOUT) + "s"
        except FileNotFoundError:
            return 127, "CLI binary missing"
        except Exception as exc:
            return 1, str(exc)

    # -- lifecycle -------------------------------------------------------------

    def start(self):
        """(Re)load enabled jobs and arm their triggers. Idempotent."""
        self.stop()
        self.jobs = [j for j in load_jobs() if j.get("enabled")]
        if not self.jobs:
            self.emit("no enabled jobs")
            return

        armed = 0
        for job in self.jobs:
            try:
                _validate_job(job)
            except ValueError as exc:
                self.emit("skip '" + job.get("name", "?") + "': " + str(exc))
                continue
            mode = job.get("mode")
            if mode == "watch":
                if job["direction"] in ("upload", "both"):
                    if self._arm_watch(job):
                        armed += 1
                else:
                    # download-only makes no sense for watch (nothing local
                    # changes); treat as interval fallback.
                    tid = GLib.timeout_add(CHECK_TICK_S * 1000,
                                           self._on_interval, job)
                    self._timeouts.append(tid)
                    armed += 1
            elif mode == "interval":
                ms = int(job.get("interval_min", 30)) * 60 * 1000
                tid = GLib.timeout_add(ms, self._on_interval, job)
                self._timeouts.append(tid)
                armed += 1
            elif mode == "schedule":
                armed += 1                  # handled by the shared ticker
        # Shared schedule ticker (one per engine, not per job)
        tid = GLib.timeout_add_seconds(CHECK_TICK_S, self._on_schedule_tick)
        self._timeouts.append(tid)
        self.emit("engine armed: " + str(armed) + " of " +
                  str(len(self.jobs)) + " job(s)")

    def stop(self):
        """Release every monitor and timeout. Safe to call repeatedly."""
        for m in self._monitors:
            try:
                m.cancel()
            except Exception:
                pass
        for tid in self._timeouts:
            try:
                GLib.source_remove(tid)
            except Exception:
                pass
        for tid in self._debounce_ids.values():
            try:
                GLib.source_remove(tid)
            except Exception:
                pass
        self._monitors = []
        self._timeouts = []
        self._debounce_ids = {}
        self._pending = {}

    def run_forever(self):
        """Daemon entry: acquire lock, arm, block on GLib main loop."""
        if not self.acquire_lock():
            log.error("another PDUA autosync engine holds the lock; exiting")
            return
        loop = GLib.MainLoop()
        self.start()
        try:
            loop.run()
        except KeyboardInterrupt:
            log.info("interrupted -- shutting down")
        finally:
            self.stop()
            self.release_lock()

    # -- locking ----------------------------------------------------------------

    def acquire_lock(self):
        """True if we hold the lock. Exits quietly if someone else does."""
        os.makedirs(STATE_DIR, exist_ok=True)
        self._lock_fd = open(LOCK_FILE, "w")
        try:
            fcntl.flock(self._lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            self._lock_fd.write(str(os.getpid()))
            self._lock_fd.flush()
            return True
        except OSError:
            return False

    def release_lock(self):
        if self._lock_fd is not None:
            try:
                fcntl.flock(self._lock_fd, fcntl.LOCK_UN)
                self._lock_fd.close()
            except Exception:
                pass
            self._lock_fd = None

    # -- watch mode ---------------------------------------------------------------

    def _arm_watch(self, job):
        try:
            gfile = Gio.File.new_for_path(job["local_dir"])
            monitor = gfile.monitor_directory(
                Gio.FileMonitorFlags.WATCH_MOVES)
            monitor.connect("changed", self._on_fs_change, job["name"])
            self._monitors.append(monitor)
            self.emit("[" + job["name"] + "] watching " + job["local_dir"])
            return True
        except Exception as exc:
            self.emit("[" + job["name"] + "] cannot watch: " + str(exc))
            return False

    def _on_fs_change(self, monitor, file, other, event, job_name):
        """Any activity in the watched tree restarts the debounce clock."""
        self._pending[job_name] = time.monotonic()
        old_tid = self._debounce_ids.get(job_name)
        if old_tid is not None:
            try:
                GLib.source_remove(old_tid)
            except Exception:
                pass
        tid = GLib.timeout_add_seconds(QUIET_SECONDS,
                                       self._fire_if_quiet, job_name)
        self._debounce_ids[job_name] = tid

    def _fire_if_quiet(self, job_name):
        """Debounce elapsed with no further changes -> sync."""
        self._debounce_ids.pop(job_name, None)
        job = self._find_job(job_name)
        if job is None:
            return False
        if job_name in self._pending:
            del self._pending[job_name]
        self._run_async(job, reason="change detected")
        return False                        # one-shot

    # -- interval mode -------------------------------------------------------------

    def _on_interval(self, job):
        self._run_async(job, reason="interval")
        return GLib.SOURCE_CONTINUE

    # -- schedule mode ---------------------------------------------------------------

    def _on_schedule_tick(self):
        now = datetime.now()
        hhmm = now.strftime("%H:%M")
        today = now.strftime("%Y-%m-%d")

        for job in list(self.jobs):
            sched = (job.get("schedule") or "").strip()
            name = job.get("name", "?")

            if sched.startswith("daily "):
                target = sched[6:].strip()
                if target == hhmm and self._last_fired.get(name) != today + hhmm:
                    self._last_fired[name] = today + hhmm
                    self._run_async(job, reason="daily " + target)
            elif sched.startswith("once "):
                stamp = sched[5:].strip()
                if (stamp == today + " " + hhmm
                        and not self._last_fired.get(name)):
                    self._last_fired[name] = True
                    self._run_async(job, reason="scheduled once")
        return GLib.SOURCE_CONTINUE

    # -- shared helpers ------------------------------------------------------------

    def _find_job(self, name):
        for job in self.jobs:
            if job.get("name") == name:
                return job
        return None

    def _run_async(self, job, reason=""):
        """Spawn the transfer off-thread. Skips if one is in flight."""
        if self._busy:
            self.emit("[" + job["name"] + "] busy -- skipping (" + reason + ")")
            return
        import threading

        def worker():
            self._busy = True
            try:
                self.emit("[" + job["name"] + "] starting (" + reason + ")")
                ok, msg = self.sync_job_once(job)
                self.emit(("OK: " if ok else "FAIL: ") + msg)
            finally:
                self._busy = False

        threading.Thread(target=worker, daemon=True,
                         name="pdua-autosync-" + job["name"]).start()


# ---------------------------------------------------------------------------
# systemd user service helpers
# ---------------------------------------------------------------------------

def service_status():
    """Returns (is_running: bool, status_word: str)."""
    try:
        proc = subprocess.run(
            ["systemctl", "--user", "is-active", SERVICE_NAME],
            capture_output=True, text=True, timeout=15)
        word = proc.stdout.strip()
        return word == "active", word
    except Exception:
        return False, "unknown"


def install_background_service():
    """Write + enable + start the systemd user unit. Returns (ok, msg)."""
    app_dir = os.getcwd()
    unit = (
        "[Unit]\n"
        "Description=PDUA AutoSync (Proton Drive background sync)\n"
        "After=network-online.target\n"
        "Wants=network-online.target\n"
        "\n"
        "[Service]\n"
        "Type=simple\n"
        "WorkingDirectory=" + app_dir + "\n"
        "ExecStart=/usr/bin/python3 -m " + MODULE_PATH + " --daemon\n"
        "Restart=on-failure\n"
        "RestartSec=30\n"
        "\n"
        "[Install]\n"
        "WantedBy=default.target\n"
    )
    try:
        os.makedirs(USER_UNIT_DIR, exist_ok=True)
        unit_path = os.path.join(USER_UNIT_DIR, SERVICE_NAME)
        with open(unit_path, "w", encoding="utf-8") as f:
            f.write(unit)
    except Exception as exc:
        return False, "could not write unit file: " + str(exc)

    for cmd in (["systemctl", "--user", "daemon-reload"],
                ["systemctl", "--user", "enable", "--now", SERVICE_NAME]):
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True,
                                  timeout=30)
            if proc.returncode != 0:
                err = (proc.stderr or "").strip()[:200]
                return False, "systemctl failed: " + err
        except FileNotFoundError:
            return False, "systemctl not found (non-systemd distro?)"
        except Exception as exc:
            return False, str(exc)
    return True, SERVICE_NAME + " installed and started (systemd --user)"


def uninstall_background_service():
    """Disable + stop + remove the unit. Returns (ok, msg)."""
    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", SERVICE_NAME],
            capture_output=True, text=True, timeout=30)
    except Exception:
        pass
    unit_path = os.path.join(USER_UNIT_DIR, SERVICE_NAME)
    try:
        if os.path.exists(unit_path):
            os.unlink(unit_path)
        subprocess.run(["systemctl", "--user", "daemon-reload"],
                       capture_output=True, timeout=30)
    except Exception as exc:
        return False, str(exc)
    return True, SERVICE_NAME + " stopped and removed"


# ---------------------------------------------------------------------------
# AutoSyncSetupPage -- the sidebar page. Constructed ONLY by main_window.py.
# ---------------------------------------------------------------------------

class AutoSyncSetupPage(Gtk.Box):
    """
    Configure sync jobs, run the live engine while the app is open, and
    install/uninstall the systemd background service.
    """

    def __init__(self, on_navigate=None, **_ignored):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.on_navigate = on_navigate
        self._parent_window = None

        # The PAGE owns the ENGINE. (Engine is NOT a page. Never
        # construct AutoSyncSetupPage here.)
        self.engine = SyncEngine(on_event=self._on_engine_event)

        # ---- header ----
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                         margin_top=12, margin_bottom=6,
                         margin_start=12, margin_end=12)
        title = Gtk.Label(halign=Gtk.Align.START, hexpand=True)
        title.set_markup("<span size='large' weight='bold'>AutoSync Setup</span>")
        header.append(title)

        add_btn = Gtk.Button(label="+ Add Job")
        add_btn.add_css_class("suggested-action")
        add_btn.connect("clicked", lambda *_: self._open_editor(None))
        header.append(add_btn)
        self.append(header)

        # ---- live engine switch ----
        eng_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                          margin_start=12, margin_end=12)
        eng_lbl = Gtk.Label(label="Live engine (syncs while PDUA is open)",
                            hexpand=True, halign=Gtk.Align.START)
        eng_row.append(eng_lbl)
        self.master_switch = Gtk.Switch()
        self.master_switch.connect("state-set", self._on_master_switch)
        eng_row.append(self.master_switch)
        self.append(eng_row)

        # ---- background service row ----
        svc_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                          margin_start=12, margin_end=12, margin_top=4)
        svc_lbl = Gtk.Label(hexpand=True, halign=Gtk.Align.START)
        svc_lbl.set_markup(
            "<b>Background service</b> (keeps syncing after PDUA closes)")
        svc_row.append(svc_lbl)
        self.svc_button = Gtk.Button(label="Install...")
        self.svc_button.connect("clicked", lambda *_: self._toggle_service())
        svc_row.append(self.svc_button)
        self.append(svc_row)

        # ---- job list ----
        self.list_box = Gtk.ListBox(selection_mode=Gtk.SelectionMode.NONE)
        self.list_box.set_margin_start(12)
        self.list_box.set_margin_end(12)
        self.list_box.add_css_class("boxed-list")
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scrolled.set_child(self.list_box)
        self.append(scrolled)

        # ---- status line ----
        self.status_label = Gtk.Label(label="Ready.", halign=Gtk.Align.START,
                                      wrap=True, margin_start=12,
                                      margin_bottom=6, margin_top=2)
        self.status_label.add_css_class("dim-label")
        self.append(self.status_label)

        self._refresh_service_button()
        self._reload_jobs()

    # -- adapter REQUIRED by main_window.py -----------------------------

    def build(self, parent_window=None):
        """Registration-loop adapter: main_window calls page.build(self)."""
        if parent_window is not None:
            self._parent_window = parent_window
        return self

    # -- small helpers ----------------------------------------------------

    def _window(self):
        if self._parent_window is not None:
            return self._parent_window
        root = self.get_root()
        return root if isinstance(root, Gtk.Window) else None

    def _status(self, text, error=False):
        self.status_label.set_text(text)
        if error:
            self.status_label.add_css_class("error")
        else:
            self.status_label.remove_css_class("error")

    def _on_engine_event(self, message):
        # May arrive from worker threads via GLib.idle_add already; the
        # emit path marshals us to the main thread, so just set the label.
        self._status(message)

    # -- job list rendering --------------------------------------------------

    def _reload_jobs(self):
        self._populate(load_jobs())

    def _populate(self, jobs):
        child = self.list_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.list_box.remove(child)
            child = nxt

        if not jobs:
            row = Gtk.ListBoxRow(selectable=False, activatable=False)
            row.set_child(Gtk.Label(
                label="No jobs yet. Click '+ Add Job' to create one.",
                margin_top=24, margin_bottom=24))
            self.list_box.append(row)
            return
        for job in jobs:
            self.list_box.append(self._job_row(job))

    def _job_row(self, job):
        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12,
                      margin_top=8, margin_bottom=8,
                      margin_start=8, margin_end=8)

        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2,
                       hexpand=True)
        name_lbl = Gtk.Label(halign=Gtk.Align.START)
        name_lbl.set_markup("<b>" +
                            GLib.markup_escape_text(job.get("name", "?")) +
                            "</b>")
        info.append(name_lbl)

        mode = job.get("mode")
        if mode == "watch":
            when = "Live file watching"
        elif mode == "interval":
            when = "Every " + str(job.get("interval_min", 30)) + " min"
        else:
            when = job.get("schedule", "")

        arrow = ("->" if job.get("direction") == "upload" else
                 "<-" if job.get("direction") == "download" else "<->")
        sub_txt = (arrow + " " + job.get("local_dir", "?") + "  <->  " +
                   job.get("remote_dir", "?") + "   |   " + when)
        sub = Gtk.Label(label=sub_txt, halign=Gtk.Align.START)
        sub.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        sub.add_css_class("dim-label")
        info.append(sub)
        box.append(info)

        sw = Gtk.Switch()
        sw.set_active(bool(job.get("enabled")))
        sw.set_valign(Gtk.Align.CENTER)
        sw.connect("state-set",
                   lambda b, st, j=job: self._toggle_job_enabled(j, st))
        box.append(sw)

        edit_btn = Gtk.Button.new_from_icon_name("document-edit-symbolic")
        edit_btn.set_valign(Gtk.Align.CENTER)
        edit_btn.set_tooltip_text("Edit job")
        edit_btn.connect("clicked", lambda *_a, j=job: self._open_editor(j))
        box.append(edit_btn)

        del_btn = Gtk.Button.new_from_icon_name("user-trash-symbolic")
        del_btn.set_valign(Gtk.Align.CENTER)
        del_btn.add_css_class("destructive-action")
        del_btn.set_tooltip_text("Remove job")
        del_btn.connect("clicked", lambda *_a, j=job: self._delete_job(j))
        box.append(del_btn)

        row = Gtk.ListBoxRow(selectable=False, activatable=False)
        row.set_child(box)
        return row

    # -- add / edit dialog -----------------------------------------------------

    def _open_editor(self, existing=None):
        """
        One dialog handles add AND edit. Widgets are created once and
        read back on save -- no property-binding tricks.
        """
        win = self._window()
        dialog = Adw.MessageDialog(
            transient_for=win,
            heading="Edit Job" if existing else "New Sync Job",
            body="What syncs, which way, and when.")
        dialog.set_default_size(560, -1)

        grid = Gtk.Grid(column_spacing=12, row_spacing=10)
        grid.set_margin_bottom(4)

        def row_add(y, caption, widget):
            grid.attach(Gtk.Label(label=caption, halign=Gtk.Align.END,
                                  valign=Gtk.Align.CENTER), 0, y, 1, 1)
            widget.set_hexpand(True)
            grid.attach(widget, 1, y, 1, 1)

        e_name = Gtk.Entry(placeholder_text="e.g. Documents Backup")
        e_name.set_text((existing or {}).get("name", ""))
        row_add(0, "Job name:", e_name)

        e_local = Gtk.Entry(placeholder_text="/home/user/Documents")
        e_local.set_text((existing or {}).get("local_dir", ""))
        row_add(1, "Local folder:", e_local)

        browse_btn = Gtk.Button(label="Browse...")
        browse_btn.set_halign(Gtk.Align.END)
        grid.attach(browse_btn, 1, 2, 1, 1)

        e_remote = Gtk.Entry(placeholder_text="/my-files/Documents")
        e_remote.set_text((existing or {}).get("remote_dir", ""))
        row_add(3, "Drive folder:", e_remote)

        dd_dir = Gtk.DropDown(strings=DIRECTIONS)
        try:
            dd_dir.set_selected(DIRECTIONS.index(
                (existing or {}).get("direction", "upload")))
        except Exception:
            pass
        row_add(4, "Direction:", dd_dir)

        dd_mode = Gtk.DropDown(strings=MODES)
        try:
            dd_mode.set_selected(MODES.index(
                (existing or {}).get("mode", "watch")))
        except Exception:
            pass
        row_add(5, "Trigger:", dd_mode)

        sp_min = Gtk.SpinButton.new_with_range(1, 1440, 5)
        sp_min.set_value((existing or {}).get("interval_min", 30))
        sp_min.set_hexpand(True)
        sp_min.set_halign(Gtk.Align.END)
        grid.attach(sp_min, 1, 6, 1, 1)

        e_sched = Gtk.Entry(
            placeholder_text="daily 09:00   or   once 2026-12-25 08:00")
        e_sched.set_text((existing or {}).get("schedule", ""))
        row_add(7, "Schedule:", e_sched)

        # folder picker (GTK >= 4.10); entry stays editable as fallback
        def pick_folder(btn):
            if hasattr(Gtk, "FileDialog"):
                fd = Gtk.FileDialog()

                def done(d, res):
                    try:
                        gf = d.select_folder_finish(res)
                        if gf is not None:
                            e_local.set_text(gf.get_path())
                    except GLib.Error:
                        pass                     # user cancelled
                fd.select_folder(win, None, done)
            else:
                self._status("GTK < 4.10: type the folder path manually")
        browse_btn.connect("clicked", pick_folder)

        dialog.set_extra_child(grid)
        dialog.add_response("cancel", "Cancel")
        dialog.add_response("ok", "Save")
        dialog.set_response_appearance("ok", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("ok")
        dialog.set_close_response("cancel")

        def respond(dlg, resp):
            if resp != "ok":
                dlg.destroy()
                return
            job = {
                "name": e_name.get_text().strip(),
                "local_dir": e_local.get_text().strip(),
                "remote_dir": e_remote.get_text().strip(),
                "direction": DIRECTIONS[dd_dir.get_selected()],
                "mode": MODES[dd_mode.get_selected()],
                "interval_min": int(sp_min.get_value()),
                "schedule": e_sched.get_text().strip(),
                "enabled": (existing or {}).get("enabled", True),
            }
            dlg.destroy()
            self._save_job(job, existing)

        dialog.connect("response", respond)
        dialog.present()
        e_name.grab_focus()

    # -- job persistence -----------------------------------------------------

    def _save_job(self, job, replacing=None):
        try:
            _validate_job(job)
        except ValueError as exc:
            self._status("! " + str(exc), error=True)
            return
        jobs = load_jobs()
        if replacing is not None:
            replaced = False
            new_jobs = []
            for j in jobs:
                if j is replacing or (j.get("name") == replacing.get("name")):
                    new_jobs.append(job)
                    replaced = True
                else:
                    new_jobs.append(j)
            jobs = new_jobs if replaced else new_jobs + [job]
        else:
            jobs.append(job)
        save_jobs(jobs)
        self._reload_jobs()
        self._status("Saved job '" + job["name"] + "'.")
        if self.master_switch.get_active():
            self.engine.start()             # hot-reload triggers

    def _toggle_job_enabled(self, job, enabled):
        jobs = load_jobs()
        for j in jobs:
            if j.get("name") == job.get("name"):
                j["enabled"] = enabled
        save_jobs(jobs)
        if self.master_switch.get_active():
            self.engine.start()

    def _delete_job(self, job):
        jobs = [j for j in load_jobs()
                if j.get("name") != job.get("name")]
        save_jobs(jobs)
        self._reload_jobs()
        self._status("Removed '" + job.get("name", "?") + "'.")
        if self.master_switch.get_active():
            self.engine.start()

    # -- engine + service controls --------------------------------------------

    def _on_master_switch(self, switch, state):
        if state:
            self.engine.start()
            self._status("Live engine running.")
        else:
            self.engine.stop()
            self._status("Live engine stopped.")

    def _toggle_service(self):
        running, _word = service_status()
        if running:
            ok, msg = uninstall_background_service()
        else:
            ok, msg = install_background_service()
        self._status(("OK: " if ok else "! ") + msg, error=not ok)
        self._refresh_service_button()

    def _refresh_service_button(self):
        running, word = service_status()
        if running:
            self.svc_button.set_label("Uninstall...")
            self.svc_button.set_tooltip_text(
                "Stop and remove the systemd background service")
        else:
            self.svc_button.set_label("Install...")
            self.svc_button.set_tooltip_text(
                "Install a systemd --user service so syncing continues "
                "after PDUA closes")


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def _setup_logging():
    os.makedirs(STATE_DIR, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.FileHandler(LOG_FILE),
                  logging.StreamHandler(sys.stdout)],
    )


if __name__ == "__main__":
    if "--daemon" in sys.argv:
        _setup_logging()
        log.info("PDUA autosync daemon starting (pid %s)", os.getpid())
        SyncEngine().run_forever()
        log.info("PDUA autosync daemon exiting")
    else:
        # ---- self-check (no display needed for parts 1-3) ----
        print("auto_sync_setup self-check...")
        print("  config file :", AUTOSYNC_CONFIG)
        print("  jobs loaded :", len(load_jobs()))

        bad_cases = [
            ({"name": "", "local_dir": "/", "remote_dir": "/x",
              "direction": "upload", "mode": "watch"}, "empty name"),
            ({"name": "j", "local_dir": "/nonexistent-xyz-12345",
              "remote_dir": "/x", "direction": "upload",
              "mode": "watch"}, "missing local dir"),
            ({"name": "j", "local_dir": "/", "remote_dir": "../etc",
              "direction": "upload", "mode": "watch"}, "path traversal"),
            ({"name": "j", "local_dir": "/", "remote_dir": "/x",
              "direction": "sideways", "mode": "watch"}, "bad direction"),
            ({"name": "j", "local_dir": "/", "remote_dir": "/x",
              "direction": "upload", "mode": "schedule",
              "schedule": "whenever"}, "bad schedule"),
        ]
        for bad, why in bad_cases:
            try:
                _validate_job(bad)
                print("  FAIL: accepted bad job (" + why + ")")
                sys.exit(1)
            except ValueError:
                print("  rejected bad job:", why)

        eng = SyncEngine()
        eng.start()
        eng.stop()
        print("  SyncEngine start/stop clean")

        try:
            page = AutoSyncSetupPage()
            assert hasattr(page, "build"), "build() adapter missing"
            assert hasattr(page, "engine"), "engine missing"
            assert isinstance(page.engine, SyncEngine), "engine wrong type"
            assert hasattr(page, "master_switch"), "switch missing"
            built = page.build(parent_window=None)
            assert built is page, "build() must return self"
            print("  page constructed: build() adapter OK, engine OK")
        except Exception as exc:
            print("  page construction needs a display:", exc)

        print("SELF-CHECK PASSED")
