#!/usr/bin/env python3
import sys
import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject
from ui.main_window import MainWindow

class PDUA(Adw.Application):
    def __init__(self):
        super().__init__(application_id="com.unixinbox.pdua")

    def do_startup(self):
        Adw.Application.do_startup(self)

        # ---- Register Actions ----
        actions = [
            ("new",           self._on_new),
            ("albums",        self._on_albums),
            ("open",          self._on_open),
            ("quit",          self._on_quit),
            ("settings",      self._on_settings),
            ("about",         self._on_about),
            ("shortcuts",     self._on_shortcuts),
            ("login",         self._on_auth),
            ("theme-dark",    self._on_theme_dark),
            ("theme-light",   self._on_theme_light),
            ("theme-system",  self._on_theme_system),
        ]
        for name, callback in actions:
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)

        # ---- Build the Menu Model ----
        menu = Gio.Menu()

        login_section = Gio.Menu()
        login_section.append("🔐  Login to Proton Drive…", "app.login")
        menu.append_section(None, login_section)

        app_section = Gio.Menu()
        app_section.append("New Window", "app.new")
        app_section.append("📸 Albums", "app.albums")
        app_section.append("Open File…", "app.open")
        app_section.append("Preferences", "app.settings")
        menu.append_submenu("Application", app_section)

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
        self.set_accels_for_action("app.albums", ["<Ctrl>A"])
        self.set_accels_for_action("app.open", ["<Ctrl>O"])
        self.set_accels_for_action("app.settings", ["<Ctrl>comma"])
        self.set_accels_for_action("app.login", ["<Ctrl>L"])

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

    # ---- Albums ----

    def _on_albums(self, action, param):
        print("[Menu] Albums triggered")
        from ui.function.pup.remote.albums_window import AlbumsWindow

        win = self.props.active_window
        if not win:
            return

        # Prefer the CLI found by the window itself, else settings, else PATH
        cli = "proton-drive"
        finder = getattr(win, "_find_proton_drive_cli", None)
        if finder:
            cli = finder() or cli

        albums_win = AlbumsWindow(win, cli_binary=cli)
        albums_win.connect("album-opened",
                           lambda w, name: print(f"[Main] Album opened: {name}"))
        albums_win.present()

    # ---- Login ----

    def _on_auth(self, action, param):
        """Open the login popup window from the dropdown menu."""
        print("[Menu] Login triggered")
        from ui.function.pup.auth_window import AuthWindow

        parent = self.props.active_window
        if parent:
            auth_win = AuthWindow(parent, on_success=parent._on_login_success)
            auth_win.present()

    # ---- Theme ----

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


def main():
    app = PDUA()
    app.run(sys.argv)


if __name__ == "__main__":
    main()
