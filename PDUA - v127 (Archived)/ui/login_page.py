import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib, Gio
import subprocess
import threading
import os
import shutil


class LoginPage:
    """Login page for PDUA — handles Proton Drive CLI authentication."""

    def __init__(self, on_navigate=None, on_login_success=None):
        self.on_navigate = on_navigate
        self.on_login_success = on_login_success
        self._cli_path = self._find_cli()

    def _find_cli(self):
        """Locate the proton-drive binary."""
        candidates = [
            "/usr/bin/proton-drive",
            "/usr/local/bin/proton-drive",
            os.path.expanduser("~/.local/bin/proton-drive"),
        ]
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path

        # Fall back to PATH
        found = shutil.which("proton-drive")
        return found if found else None

    def build(self):
        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )

        # --- Title ---
        title = Gtk.Label(label="<span size='xx-large' weight='bold'>PDUA - Login</span>")
        title.set_use_markup(True)
        container.append(title)

        subtitle = Gtk.Label(label="Proton Drive Uploader App")
        subtitle.add_css_class("dim-label")
        container.append(subtitle)

        # --- Status Label ---
        self.status_label = Gtk.Label(label="Checking authentication status…")
        self.status_label.set_wrap(True)
        self.status_label.set_halign(Gtk.Align.CENTER)
        container.append(self.status_label)

        # --- Login Button ---
        self.login_btn = Gtk.Button(label="Login to Proton Drive")
        self.login_btn.set_size_request(300, -1)
        self.login_btn.add_css_class("suggested-action")
        self.login_btn.connect("clicked", self._on_login_clicked)
        self.login_btn.set_visible(False)
        container.append(self.login_btn)

        # --- Continue Button (shown after auth) ---
        self.continue_btn = Gtk.Button(label="Continue to PDUA")
        self.continue_btn.set_size_request(300, -1)
        self.continue_btn.add_css_class("suggested-action")
        self.continue_btn.connect("clicked", self._on_continue_clicked)
        self.continue_btn.set_visible(False)
        container.append(self.continue_btn)

        # --- Spinner ---
        self.spinner = Gtk.Spinner()
        self.spinner.set_halign(Gtk.Align.CENTER)
        container.append(self.spinner)

        # --- Output Log (scrollable) ---
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_min_content_height(120)
        scrolled.set_max_content_height(200)
        scrolled.set_hexpand(False)
        scrolled.set_size_request(400, -1)
        scrolled.set_visible(False)

        self.log_view = Gtk.TextView()
        self.log_view.set_editable(False)
        self.log_view.set_cursor_visible(False)
        self.log_view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.log_buffer = self.log_view.get_buffer()
        scrolled.set_child(self.log_view)
        container.append(scrolled)
        self.scrolled = scrolled

        # Start auth check on load
        self._check_auth_status()

        return container

    # ===== AUTH STATUS CHECK =====

    def _check_auth_status(self):
        """Check if proton-drive CLI is already authenticated."""
        if not self._cli_path:
            self.status_label.set_text(
                "✗ Proton Drive CLI not found.\n"
                "Install it from https://proton.me/drive/download"
            )
            return

        self.spinner.start()
        self.spinner.set_visible(True)

        t = threading.Thread(target=self._do_auth_check, daemon=True)
        t.start()

    def _do_auth_check(self):
        """Run auth status check in background thread."""
        try:
            cmd = [self._cli_path, "auth", "status"]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)

            if result.returncode == 0:
                # Already authenticated
                GLib.idle_add(self._show_authenticated_state)
            else:
                # Not logged in
                GLib.idle_add(self._show_not_authenticated_state)

        except subprocess.TimeoutExpired:
            GLib.idle_add(
                self.status_label.set_text,
                "✗ Auth check timed out."
            )
        except Exception as e:
            GLib.idle_add(
                self.status_label.set_text,
                f"✗ Error checking auth: {e}"
            )
        finally:
            GLib.idle_add(self.spinner.stop)
            GLib.idle_add(self.spinner.set_visible, False)

    # ===== STATE DISPLAYS =====

    def _show_authenticated_state(self):
        """UI when user is already logged in."""
        self.status_label.set_text("✓ Authenticated to Proton Drive")
        self.login_btn.set_visible(False)
        self.continue_btn.set_visible(True)

    def _show_not_authenticated_state(self):
        """UI when user needs to log in."""
        self.status_label.set_text("Not logged in. Click below to authenticate.")
        self.login_btn.set_visible(True)
        self.continue_btn.set_visible(False)

    # ===== LOGIN FLOW =====

    def _on_login_clicked(self, widget):
        """Trigger the proton-drive auth login flow."""
        self.login_btn.set_sensitive(False)
        self.scrolled.set_visible(True)
        self._append_log("Starting Proton Drive login…\n")
        self.spinner.start()
        self.spinner.set_visible(True)
        self.status_label.set_text("Waiting for authentication…")

        t = threading.Thread(target=self._do_login, daemon=True)
        t.start()

    def _do_login(self):
        """Run proton-drive auth login in background.

        The CLI will print a URL the user must open in a browser.
        We capture stdout/stderr to display it in the log view.
        """
        try:
            cmd = [self._cli_path, "auth", "login"]
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
            )

            # Stream output line by line
            for line in iter(proc.stdout.readline, ""):
                GLib.idle_add(self._append_log, line)

            proc.wait(timeout=120)

            if proc.returncode == 0:
                GLib.idle_add(self._on_login_success_ui)
            else:
                GLib.idle_add(
                    self._on_login_failed,
                    f"Login failed (exit code {proc.returncode})"
                )

        except subprocess.TimeoutExpired:
            GLib.idle_add(self._on_login_failed, "Login timed out (>2 min)")
        except FileNotFoundError:
            GLib.idle_add(
                self._on_login_failed,
                "proton-drive CLI not found.\n"
                "Download: https://proton.me/drive/download"
            )
        except Exception as e:
            GLib.idle_add(self._on_login_failed, f"Unexpected error: {e}")

    def _on_login_success_ui(self):
        """Called on main thread when login succeeds."""
        self.spinner.stop()
        self.spinner.set_visible(False)
        self._append_log("\n✓ Login successful!\n")
        self.status_label.set_text("✓ Authenticated to Proton Drive")
        self.login_btn.set_visible(False)
        self.continue_btn.set_visible(True)

        if self.on_login_success:
            self.on_login_success()

    def _on_login_failed(self, message):
        """Called on main thread when login fails."""
        self.spinner.stop()
        self.spinner.set_visible(False)
        self._append_log(f"\n✗ {message}\n")
        self.status_label.set_text(message)
        self.login_btn.set_sensitive(True)
        self.login_btn.set_visible(True)
        self.continue_btn.set_visible(False)

    def _on_continue_clicked(self, widget):
        """Navigate to the main PDUA interface."""
        if self.on_navigate:
            self.on_navigate("home")

    # ===== HELPERS =====

    def _append_log(self, text):
        """Append text to the log view (must be called on main thread)."""
        end_iter = self.log_buffer.get_end_iter()
        self.log_buffer.insert(end_iter, text)

        # Auto-scroll to bottom
        mark = self.log_buffer.get_insert()
        self.log_view.scroll_to_mark(mark, 0.0, False, 0, 0)
