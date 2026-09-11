#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib
from ui.main_window import MainWindow

class PDUA(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.unixinbox.pdua")

    def do_startup(self):
        Adw.Application.do_startup(self)

        # ---- Register Actions ----
        actions = [
            ("new",           self._on_new),
            ("open",          self._on_open),
            ("quit",          self._on_quit),
            ("settings",      self._on_settings),
            ("about",         self._on_about),
            ("shortcuts",     self._on_shortcuts),
            ("login",         self._on_auth),           # NEW
            ("theme-dark",    self._on_theme_dark),      # NEW
            ("theme-light",   self._on_theme_light),     # NEW
            ("theme-system",  self._on_theme_system),    # NEW
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        # ---- Build the Menu Model ----
        menu = Gio.Menu()

        # Login at the very top
        login_section = Gio.Menu()
        login_section.append("🔐  Login to Proton Drive…", "app.login")
        menu.append_section(None, login_section)

        app_section = Gio.Menu()
        app_section.append("New Window", "app.new")
        app_section.append("Open File…", "app.open")
        app_section.append("Preferences", "app.settings")
        menu.append_submenu("Application", app_section)

        # Theme submenu
        theme_menu = Gio.Menu()
        theme_menu.append("🌙  Dark Mode", "app.theme-dark")
        theme_menu.append("☀  Light Mode", "app.theme-light")
        theme_menu.append("🖥  System Default", "app.theme-system")
        menu.append_submenu("Appearance", theme_menu)

        shortcuts_section = Gio.Menu()
        shortcuts_section.append("Keyboard Shortcuts", "app.shortcuts")
        menu.append_submenu("Shortcuts", shortcuts_section)

        help_section = Gio.Menu()
        help_section.append("About App", "app.about")
        help_section.append("Quit", "app.quit")
        menu.append_submenu("Help", help_section)

        self.set_menubar(menu)

        # Keyboard shortcuts
        self.set_accels_for_action("app.quit", ["<Ctrl>Q"])
        self.set_accels_for_action("app.new", ["<Ctrl>N"])
        self.set_accels_for_action("app.open", ["<Ctrl>O"])
        self.set_accels_for_action("app.settings", ["<Ctrl>comma"])
        self.set_accels_for_action("app.login", ["<Ctrl>L"])   # NEW

    def do_activate(self):
        win = self.props.active_window
        if not win:
            win = MainWindow(application=self)
        win.present()

    # ---- Action Callbacks ----

    def _on_new(self, action, param):
        print("[Menu] New Window triggered")
        win = MainWindow(application=self)
        win.present()

    def _on_open(self, action, param):
        print("[Menu] Open File triggered")
        from ui.function.pup.file_browser import FileBrowserWindow

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

    # ---- NEW: Login Action ----

    def _on_auth(self, action, param):
        """Open the login popup window from the dropdown menu."""
        print("[Menu] Login triggered")
        from ui.function.pup.auth_window import AuthWindow

        parent = self.props.active_window
        if parent:
            auth_win = AuthWindow(parent, on_success=parent._on_login_success)
            auth_win.present()

    # ---- NEW: Theme Actions ----

    def _on_theme_dark(self, action, param):
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_DARK
        )

    def _on_theme_light(self, action, param):
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.FORCE_LIGHT
        )

    def _on_theme_system(self, action, param):
        Adw.StyleManager.get_default().set_color_scheme(
            Adw.ColorScheme.DEFAULT
        )

    # ===== FILE HANDLING =====

    def _handle_selected_file(self, filepath):
        print(f"[Processing] Received file: {filepath}")

        if os.path.isfile(filepath):
            print(f"✓ Valid file detected: {filepath}")
        elif os.path.isdir(filepath):
            print(f"ℹ Directory selected: {filepath}")
        else:
            print(f"✗ Invalid path: {filepath}")


def main():
    app = PDUA()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
