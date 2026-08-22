#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
import subprocess
import threading

from ui.main_window import MainWindow


class PDUA(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.drive.proton.me")

    def do_startup(self):
        Adw.Application.do_startup(self)

        # ---- Register Actions ----
        actions = [
            ("new",       self._on_new),
            ("open",      self._on_open),
            ("quit",      self._on_quit),
            ("settings",  self._on_settings),
            ("about",     self._on_about),
            ("shortcuts", self._on_shortcuts),
            ("theme-dark",   self._on_theme_dark),
            ("theme-light",  self._on_theme_light),
            ("theme-system", self._on_theme_system),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        # ---- Build the Menu Model ----
        menu = Gio.Menu()

        app_section = Gio.Menu()
        app_section.append("New Window", "app.new")
        app_section.append("Preferences", "app.settings")
        menu.append_submenu("Application", app_section)

        shortcuts_section = Gio.Menu()
        shortcuts_section.append("Keyboard Shortcuts", "app.shortcuts")
        menu.append_submenu("Shortcuts", shortcuts_section)

        help_section = Gio.Menu()
        help_section.append("About App", "app.about")
        help_section.append("Quit", "app.quit")
        menu.append_submenu("Help", help_section)

        self.set_menubar(menu)

        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])
        self.set_accels_for_action("app.new", ["<Ctrl>N"])
        self.set_accels_for_action("app.open", ["<Ctrl>O"])
        self.set_accels_for_action("app.settings", ["<Ctrl>comma"])

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(application=self)
        win.present()


    # ----  dark and light user preference options ---

    def _on_theme_dark(self, action, param):
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        print("[Theme] Dark mode")

    def _on_theme_light(self, action, param):
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.FORCE_LIGHT)
        print("[Theme] Light mode")

    def _on_theme_system(self, action, param):
        Adw.StyleManager.get_default().set_color_scheme(Adw.ColorScheme.DEFAULT)
        print("[Theme] System default")

    # ---- Action Callbacks ----

    def _on_new(self, action, param):
        print("[Menu] New Window triggered")
        win = MainWindow(application=self)
        win.present()

    def _on_open(self, action, param):
        print("[Menu] Open File triggered")

        from ui.file_browser import FileBrowserWindow

        parent = self.props.active_window
        if parent:
            browser = FileBrowserWindow(parent)

            def on_file_selected(window, filepath):
                print(f"[Main] Got file from browser: {filepath}")
                self._handle_selected_file(filepath)

            browser.connect("file-selected", on_file_selected)
            browser.present()

    def _on_settings(self, action, param):
        print("[Menu] Settings triggered")
        win = self.props.active_window
        if win:
            win.navigate_to("settings")

    def _on_about(self, action, param):
        print("[Menu] About triggered")
        win = self.props.active_window
        if win:
            win.navigate_to("about")

    def _on_shortcuts(self, action, param):
        print("[Menu] Shortcuts triggered")

    def _on_quit(self, action, param):
        print("[Menu] Quit triggered")
        self.quit()

    # ===== PROTON DRIVE UPLOAD =====

    def _handle_selected_file(self, filepath):
        """Process the selected file via Proton Drive CLI."""
        print(f"[Processing] Received file: {filepath}")

        if not os.path.exists(filepath):
            print(f"✗ Invalid path: {filepath}")
            return

        remote_folder = "/my-files/Uploaded"

        if os.path.isfile(filepath):
            item_type = "file"
        elif os.path.isdir(filepath):
            item_type = "folder"
        else:
            print(f"✗ Unknown path type: {filepath}")
            return

        print(f"→ Uploading {item_type}: {filepath} → {remote_folder}")

        # Toast notification
        win = self.props.active_window
        if win and hasattr(win, "add_toast"):
            win.add_toast(Adw.Toast(title=f"Uploading {item_type}…"))

        # Run in background so GUI doesn't freeze
        t = threading.Thread(
            target=self._upload_via_cli,
            args=(filepath, remote_folder, item_type),
            daemon=True,
        )
        t.start()

    def _upload_via_cli(self, local_path, remote_folder, item_type):
        """Execute proton-drive CLI upload in a background thread."""

        # Locate the binary (try multiple locations)
        cli = "./proton-drive"
        if not os.path.exists(cli):
            cli = "/usr/local/bin/proton-drive"
        if not os.path.exists(cli):
            cli = "/usr/bin/proton-drive"
        if not os.path.exists(cli):
            cli = "proton-drive"  # fallback to PATH lookup

        cmd = [cli, "filesystem", "upload", local_path, remote_folder]
        print(f"[CLI] {' '.join(cmd)}")

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)

            if result.returncode == 0:
                msg = f"✓ Uploaded {item_type} successfully!"
                print(f"[Success] {result.stdout.strip()}")
            else:
                msg = f"✗ Upload failed: {result.stderr.strip()}"
                print(f"[Error] {result.stderr.strip()}")

        except subprocess.TimeoutExpired:
            msg = "✗ Upload timed out (>10 min)"
            print(msg)

        except FileNotFoundError:
            msg = ("✗ proton-drive CLI not found.\n"
                   "Download: https://proton.me/drive/download\n"
                   "Make executable: chmod +x proton-drive\n"
                   "Login once: ./proton-drive auth login")
            print(msg)

        except Exception as e:
            msg = f"✗ Unexpected error: {e}"
            print(msg)

        # Show result toast on main thread
        def show_result():
            win = self.props.active_window
            if win and hasattr(win, "add_toast"):
                win.add_toast(Adw.Toast(title=msg, timeout=5))

        GLib.idle_add(show_result)


def main():
    app = PDUA()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
