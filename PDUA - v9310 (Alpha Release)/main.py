#!/usr/bin/env python3

import os
import sys
import logging

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")

from gi.repository import Gtk, Adw, Gio, GLib, Gdk

# ---- App-wide logging (fixes silent 'pdua' logger) ----
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("pdua")

# ---- Project root on sys.path (so `ui.*` imports work from any CWD) ----
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class PduaApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.auth2portal.pdua",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )

    # --------------------------------------------------
    # ACTIVATE — window creation lives here
    # --------------------------------------------------
    def do_activate(self):
        # Icon theme registration (custom icons from assets/icons)
        try:
            self._register_icons()
        except Exception as e:
            log.warning(f"Icon registration skipped: {e}")

        win = self.props.active_window
        if win is None:
            from ui.main_window import MainWindow
            win = MainWindow(application=self)
        win.present()
        log.info("MainWindow presented")

    # --------------------------------------------------
    # STARTUP — actions registered once
    # --------------------------------------------------
    def do_startup(self):
        Adw.Application.do_startup(self)

        # -- Quit --
        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", lambda a, p: self.quit())
        self.add_action(action)

        # -- New Window --
        action = Gio.SimpleAction.new("new", None)
        action.connect("activate", lambda a, p: self.do_activate())
        self.add_action(action)

        # -- Login / Logout --
        action = Gio.SimpleAction.new("login", None)
        action.connect("activate", self._on_login)
        self.add_action(action)

        # -- Settings --
        action = Gio.SimpleAction.new("settings", None)
        action.connect("activate", self._on_settings)
        self.add_action(action)

        # -- About --
        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self._on_about)
        self.add_action(action)

        # -- Shortcuts --
        action = Gio.SimpleAction.new("shortcuts", None)
        action.connect("activate", self._on_shortcuts)
        self.add_action(action)

        # -- Theme actions (Adw.ColorScheme, NOT gtk-application-prefer-dark-theme) --
        for name, scheme in [
            ("theme-dark",   "force-dark"),
            ("theme-light",  "force-light"),
            ("theme-system", "default"),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect(
                "activate",
                lambda a, p, s=scheme: Adw.StyleManager.get_default().set_color_scheme(
                    getattr(Adw.ColorScheme, s.upper().replace("-", "_"))
                ),
            )
            self.add_action(action)

        # -- Keyboard accelerators --
        self.set_accels_for_action("app.quit", ["<primary>q"])
        self.set_accels_for_action("app.new", ["<primary>n"])
        self.set_accels_for_action("app.settings", ["<primary>comma"])
        self.set_accels_for_action("app.shortcuts", ["<primary>question"])
        self.set_accels_for_action("win.back", ["<Alt>Left"])

        log.info("Actions and accelerators registered")

    # --------------------------------------------------
    # ICON REGISTRATION (was defined but never called)
    # --------------------------------------------------
    def _register_icons(self):
        display = Gdk.Display.get_default()
        if display is None:
            return
        icon_dir = os.path.join(ROOT, "assets", "icons")
        if not os.path.isdir(icon_dir):
            log.debug(f"No custom icon dir at {icon_dir} — skipping")
            return
        from gi.repository import Gtk as _Gtk
        theme = _Gtk.IconTheme.get_for_display(display)
        theme.add_search_path(icon_dir)
        log.info(f"Custom icon search path added: {icon_dir}")

    # --------------------------------------------------
    # ACTION HANDLERS
    # --------------------------------------------------
    def _on_login(self, action, param):
        win = self.props.active_window
        if win and hasattr(win, "open_login_window"):
            win.open_login_window()

    def _on_settings(self, action, param):
        win = self.props.active_window
        if win and hasattr(win, "navigate_to"):
            win.navigate_to("settings")

    def _on_about(self, action, param):
        win = self.props.active_window
        if win and hasattr(win, "navigate_to"):
            win.navigate_to("about")

    def _on_shortcuts(self, action, param):
        builder = Gtk.Builder()
        builder.add_from_string("""
        <interface>
          <object class="GtkShortcutsWindow" id="shortcuts">
            <property name="modal">True</property>
            <child>
              <object class="GtkShortcutsSection">
                <property name="section-name">shortcuts</property>
                <property name="max-height">10</property>
                <child>
                  <object class="GtkShortcutsGroup">
                    <property name="title">General</property>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="accelerator">&lt;Primary&gt;q</property>
                        <property name="title">Quit</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="accelerator">&lt;Primary&gt;n</property>
                        <property name="title">New Window</property>
                      </object>
                    </child>
                    <child>
                      <object class="GtkShortcutsShortcut">
                        <property name="accelerator">&lt;Primary&gt;comma</property>
                        <property name="title">Settings</property>
                      </object>
                    </child>
                  </object>
                </child>
              </object>
            </child>
          </object>
        </interface>
        """)
        shortcuts = builder.get_object("shortcuts")
        shortcuts.set_transient_for(self.props.active_window)
        shortcuts.present()


def main():
    app = PduaApplication()
    # Exit code 0 with no window usually means app.run() returned immediately —
    # this assert catches that class of bug loudly.
    status = app.run(sys.argv[1:])
    if status == 0 and app.props.active_window is None:
        log.error("App exited 0 but no window was ever created!")
    return status


if __name__ == "__main__":
    sys.exit(main())
