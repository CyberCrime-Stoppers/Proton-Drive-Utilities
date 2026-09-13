#!/usr/bin/env python3
import os
import shutil
import subprocess
import threading
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, GObject

class AuthWindow(Adw.Window):
    """Popup window for Proton Drive CLI authentication (login/logout)."""

    __gsignals__ = {
        'auth-success': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'auth-logout':  (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, parent_window, on_success=None, on_logout=None, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Proton Drive Authentication")
        self.set_transient_for(parent_window)
        self.set_modal(True)
        self.set_default_size(500, 400)

        self._on_success_callback = on_success
        self._on_logout_callback = on_logout
        self._cli_path = self._find_cli()

        self._build_ui()
        self._check_auth_status()

    # ===== CLI DISCOVERY =====

    def _find_cli(self):
        candidates = [
            "/usr/bin/proton-drive",
            "/usr/local/bin/proton-drive",
            os.path.expanduser("~/.local/bin/proton-drive"),
        ]
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        found = shutil.which("proton-drive")
        return found if found else None

    # ===== UI BUILD =====

    def _build_ui(self):
        # Header
        header = Adw.HeaderBar()
        btn_close = Gtk.Button(label="Close")
        btn_close.connect("clicked", lambda w: self.destroy())
        header.pack_start(btn_close)

        # Main content
        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=20,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )

        # Title
        title = Gtk.Label(
            label="<span size='xx-large' weight='bold'>Proton Drive Account</span>"
        )
        title.set_use_markup(True)
        title.set_wrap(True)
        main_box.append(title)

        # Status label
        self.status_label = Gtk.Label(label="Checking authentication…")
        self.status_label.set_wrap(True)
        self.status_label.set_halign(Gtk.Align.CENTER)
        main_box.append(self.status_label)

        # Spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.CENTER)
        main_box.append(self.spinner)

        # --- TWO SEPARATE BUTTONS ---
        btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )

        # Login button (blue)
        self.login_btn = Gtk.Button(label="Login")
        self.login_btn.set_size_request(140, -1)
        self.login_btn.add_css_class("suggested-action")
        self.login_btn.connect("clicked", self._on_login_clicked)
        btn_box.append(self.login_btn)

        # Logout button (red)
        self.logout_btn = Gtk.Button(label="Logout")
        self.logout_btn.set_size_request(140, -1)
        self.logout_btn.add_css_class("destructive-action")
        self.logout_btn.connect("clicked", self._on_logout_clicked)
        btn_box.append(self.logout_btn)

        main_box.append(btn_box)

        # Scrollable log output
        self.scrolled = Gtk.ScrolledWindow()
        self.scrolled.set_min_content_height(100)
        self.scrolled.set_max_content_height(150)
        self.scrolled.set_size_request(450, -1)
        self.scrolled.set_visible(False)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_buffer = self.log_view.get_buffer()
        self.scrolled.set_child(self.log_view)
        main_box.append(self.scrolled)

        # Outer wrapper
        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        outer.append(main_box)

        self.set_content(outer)

    # ===== AUTH STATUS CHECK =====

    def _check_auth_status(self):
        if not self._cli_path:
            self.status_label.set_text(
                "✗ Proton Drive CLI not found.\n"
                "Install: https://proton.me/drive/download\n"
                "Then copy to: /usr/bin/proton-drive"
            )
            self.login_btn.set_sensitive(False)
            self.logout_btn.set_sensitive(False)
            return

        self.spinner.start()
        t = threading.Thread(target=self._do_auth_check, daemon=True)
        t.start()

    def _do_auth_check(self):
        try:
            result = subprocess.run(
                [self._cli_path, "auth", "status"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                GLib.idle_add(self._show_authenticated)
            else:
                GLib.idle_add(self._show_not_authenticated)
        except Exception as e:
            GLib.idle_add(
                self.status_label.set_text,
                f"✗ Error checking auth: {e}"
            )
        finally:
            GLib.idle_add(self.spinner.stop)

    # ===== STATE DISPLAYS =====

    def _show_authenticated(self):
        """User is logged in — enable logout, disable login."""
        self.status_label.set_text("Login in to your Proton Drive Account")
        self.login_btn.set_sensitive(True)
        self.logout_btn.set_sensitive(True)

    def _show_not_authenticated(self):
        """User is not logged in — enable login, disable logout."""
        self.status_label.set_text("Log in or Out")
        self.login_btn.set_sensitive(True)
        self.logout_btn.set_sensitive(True)

    # ===== LOGIN FLOW =====

    def _on_login_clicked(self, widget):
        """Login button clicked."""
        self.login_btn.set_sensitive(False)
        self.logout_btn.set_sensitive(False)
        self.scrolled.set_visible(True)
        self._append_log("Starting Proton Drive login…\n")
        self.spinner.start()
        self.status_label.set_text("Waiting for authentication…")

        t = threading.Thread(target=self._run_login, daemon=True)
        t.start()

    def _run_login(self):
        try:
            cmd = [self._cli_path, "auth", "login"]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            for line in iter(proc.stdout.readline, ""):
                GLib.idle_add(self._append_log, line)

            proc.wait(timeout=120)

            if proc.returncode == 0:
                GLib.idle_add(self._on_login_success)
            else:
                GLib.idle_add(
                    self._on_action_failed,
                    f"Login failed (exit code {proc.returncode})"
                )
        except subprocess.TimeoutExpired:
            GLib.idle_add(self._on_action_failed, "Login timed out (>2 min)")
        except FileNotFoundError:
            GLib.idle_add(self._on_action_failed, "proton-drive CLI not found")
        except Exception as e:
            GLib.idle_add(self._on_action_failed, f"Unexpected error: {e}")

    def _on_login_success(self):
        self.spinner.stop()
        self._append_log("\n✓ Login successful!\n")
        self._show_authenticated()

        if self._on_success_callback:
            self._on_success_callback()

        GLib.timeout_add_seconds(1, self.destroy)

    # ===== LOGOUT FLOW =====

    def _on_logout_clicked(self, widget):
        """Logout button clicked."""
        self.login_btn.set_sensitive(False)
        self.logout_btn.set_sensitive(False)
        self.scrolled.set_visible(True)
        self._append_log("Starting logout…\n")
        self.spinner.start()
        self.status_label.set_text("Logging out…")

        t = threading.Thread(target=self._run_logout, daemon=True)
        t.start()

    def _run_logout(self):
        try:
            result = subprocess.run(
                [self._cli_path, "auth", "logout"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0:
                GLib.idle_add(self._on_logout_success)
            else:
                GLib.idle_add(
                    self._on_action_failed,
                    f"Logout failed: {result.stderr.strip()}"
                )
        except Exception as e:
            GLib.idle_add(self._on_action_failed, f"Logout error: {e}")

    def _on_logout_success(self):
        self.spinner.stop()
        self._append_log("\n✓ Logged out.\n")
        self._show_not_authenticated()

        if self._on_logout_callback:
            self._on_logout_callback()

    # ===== SHARED FAILURE HANDLER =====

    def _on_action_failed(self, message):
        self.spinner.stop()
        self._append_log(f"\n✗ {message}\n")
        self.status_label.set_text(message)
        self.login_btn.set_sensitive(True)
        self.logout_btn.set_sensitive(True)

    # ===== HELPER =====

    def _append_log(self, text):
        end = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end, text)
        mark = self.log_buffer.get_insert()
        self.log_view.scroll_to_mark(mark, 0.0, False, 0, 0)
