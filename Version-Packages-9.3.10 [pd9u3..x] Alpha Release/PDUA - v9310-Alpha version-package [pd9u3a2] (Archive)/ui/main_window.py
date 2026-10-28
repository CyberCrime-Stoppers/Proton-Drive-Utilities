#!/usr/bin/env python3
"""
Main Window for PDUA — v2 architecture
Uses the unified TransferPage + FileExplorerPage registration loops.
Replaces 14 individual page imports with 2 loops.

Version v1.2.11-alpha (Still in testing & Fixes)
"""
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
import os
from gi.repository import Gtk, Adw, Gio, GLib
from ui.function.config_manager import ConfigManager, VERSION
from ui.tree.transfer_page import TransferPage
from ui.function.pup.remote.file_explorer_page import FileExplorerPage
from ui.about_page import AboutPage
from ui.function.pup.opt.context.my_files_page import MyFilesPage
from ui.function.config.auto_sync_setup import AutoSyncSetupPage


# Folder registry — one tuple per page, replacing 10 separate classes
TRANSFER_PAGES = [
    # (page_key,        direction,   folder,        mode)
    ("upload",          "upload",    None,          "fixed"),    # Fixed: Export
    ("download",        "download",  None,          "fixed"),    # Fixed: Import
    ("uploader",        "upload",    None,          "custom"),   # Custom Export (any folder)
    ("downloader",      "download",  None,          "custom"),   # Custom Import (any folder)
    ("docuploader",     "upload",    "Documents",   "custom"),
    ("dwnuploader",     "upload",    "Downloads",   "custom"),
    ("picuploader",     "upload",    "Pictures",    "custom"),
    ("viduploader",     "upload",    "Videos",      "custom"),
    ("musuploader",     "upload",    "Music",       "custom"),
    ("docdownloader",   "download",  "Documents",   "custom"),
    ("dwndownloader",   "download",  "Downloads",   "custom"),
    ("picdownloader",   "download",  "Pictures",    "custom"),
    ("viddownloader",   "download",  "Videos",      "custom"),
    ("musdownloader",   "download",  "Music",       "custom"),
]

class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title(f"Proton Drive Utility App v9.3.10-Alpha \n PDUA")
        self.set_default_size(1000, 800)

        # ---- Header Bar with Menu Button ----
        header = Adw.HeaderBar()

        # --- Theme submenu ---
        theme_menu = Gio.Menu()
        theme_menu.append("🌙  Dark Mode", "app.theme-dark")
        theme_menu.append("☀  Light Mode", "app.theme-light")
        theme_menu.append("🖥  System Default", "app.theme-system")

        # --- Main menu ---
        menu_model = Gio.Menu()
        login_section = Gio.Menu()
        login_section.append("🔐  Login or Logout…", "app.login")
        menu_model.append_section(None, login_section)
        menu_model.append("New Window", "app.new")
        menu_model.append("Preferences", "app.settings")
        menu_model.append_submenu("Appearance", theme_menu)

        help_menu = Gio.Menu()
        help_menu.append("Keyboard Shortcuts", "app.shortcuts")
        help_menu.append("About App", "app.about")
        help_menu.append("Quit", "app.quit")
        menu_model.append_submenu("Help", help_menu)

        menu_button = Gtk.MenuButton()
        menu_button.set_icon_name("open-menu-symbolic")
        menu_button.set_menu_model(menu_model)
        menu_button.set_primary(True)
        header.pack_end(menu_button)

        # ---- Page stack ----
        self.page_stack = Gtk.Stack()
        self.page_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.page_stack.set_hexpand(True)
        self.page_stack.set_vexpand(True)


        # --- Page dict ===
        self.pages = {}

        # --- Standard pages ---
        self.pages["home"] = self._build_home_page()
        self.pages["synccenterpage"] = self._build_sync_center()
        self.pages["mydir"] = FileExplorerPage(
            root="/", title="Drive Explorer", on_navigate=self.navigate_to
        )
        
        self.pages["syncsetup"] = AutoSyncSetupPage(on_navigate=self.navigate_to)

        # --- Pup sub-folders (My Files, Albums, Photos) ---
        self.pages["myfiles"] = FileExplorerPage(
            root="/my-files", title="My Files", on_navigate=self.navigate_to
        )
        self.pages["albums"] = FileExplorerPage(
            root="/albums", title="Albums", on_navigate=self.navigate_to
        )
        self.pages["photos"] = FileExplorerPage(
            root="/photos", title="Photos", on_navigate=self.navigate_to
        )

        # --- Registration LOOP: replaces 14 imports + 14 page constructions ---
        for key, direction, folder, mode in TRANSFER_PAGES:
            self.pages[key] = TransferPage(
                direction=direction, folder=folder, mode=mode,
                on_navigate=self.navigate_to
            )

        # --- Settings & About ---
        self.pages["settings"] = self._build_settings_page()
        self.pages["about"] = AboutPage(on_navigate=self.navigate_to)

        # --- Build stack widgets for all registered pages ---
        for key, page in self.pages.items():
            page_widget = page.build(parent_window=self)
            self.page_stack.add_named(page_widget, key)

        # ---- Sidebar ----
        sidebar = self._build_sidebar()

        scrolled_sidebar = Gtk.ScrolledWindow()
        scrolled_sidebar.set_child(sidebar)
        scrolled_sidebar.set_size_request(220, -1)
        scrolled_sidebar.set_hexpand(False)
        scrolled_sidebar.set_vexpand(True)
        scrolled_sidebar.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)

        separator = Gtk.Separator(orientation=Gtk.Orientation.VERTICAL)

        box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        box.append(scrolled_sidebar)
        box.append(separator)
        box.append(self.page_stack)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        outer.append(header)
        outer.append(box)

        # ---- Toast overlay ----
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(outer)
        self.set_content(self._toast_overlay)

        self.navigate_to("home")

        # ---- Auth gate on startup ----
        self._check_auth_and_navigate()

    # =====================================================
    # Page builders — local imports avoid circular deps
    # =====================================================

    def _build_home_page(self):
        from ui.function.home_page import HomePage
        return HomePage(on_navigate=self.navigate_to)

    def _build_sync_center(self):
        from ui.function.config.sync_center_page import SyncCenterPage
        return SyncCenterPage(on_navigate=self.navigate_to)

    def _build_settings_page(self):
        from ui.function.config.settings_page import SettingsPage
        return SettingsPage(on_navigate=self.navigate_to)

    # =====================================================
    # Sidebar
    # =====================================================

    def _build_sidebar(self):
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.add_css_class("navigation-sidebar")

        # Top-level flat items
        for label, key in [
            ("🏠 Home", "home"),
            ("⚡ Sync Center", "synccenterpage"),
            ("🗃️ File Explorer", "mydir"),
            ("🛞 AutoSync Setup", "syncsetup"),
        ]:
            container.append(self._make_nav_button(label, key))

        # Expandable groups — built FROM THE SAME REGISTRY TABLE
        # (single source of truth: sidebar can never desync from pages)
        groups = [
            ("⬆  Upload to Proton", "upload"),
            ("⬇  Download from Proton", "download"),
        ]

        for group_label, direction in groups:
            group_items = [
                (self._sidebar_label(entry), entry[0])
                for entry in TRANSFER_PAGES if entry[1] == direction
            ]

            expander = Gtk.Expander(label=group_label)
            expander.set_expanded(True)
            expander.add_css_class("sidebar-group")

            inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            inner_box.set_margin_start(12)

            for sub_label, sub_key in group_items:
                inner_box.append(self._make_nav_button(sub_label, sub_key, indent=True))

            expander.set_child(inner_box)
            container.append(expander)

        # Bottom flat items
        for label, key in [("⚙  Options", "settings"), ("ℹ  About", "about")]:
            container.append(self._make_nav_button(label, key))

        return container

    @staticmethod
    def _sidebar_label(entry):
        """Generate a descriptive sidebar label from a TRANSFER_PAGES entry."""
        _, direction, folder, mode = entry
        action = "Export" if direction == "upload" else "Import"
        if mode == "fixed":
            return f"Fixed: {action}"
        if folder is None:
            return f"Custom {action}: Any Folder"
        return f"Custom {action}: {folder}"

    def _make_nav_button(self, label, page_key, indent=False):
        btn = Gtk.Button(label=label)
        btn.set_has_frame(False)
        btn.set_halign(Gtk.Align.FILL)
        if indent:
            btn.set_margin_start(12)
        btn.connect("clicked", lambda b, k=page_key: self.navigate_to(k))
        return btn

    def navigate_to(self, page_key):
        """Switch the visible page, with KeyError protection."""
        if page_key not in self.pages:
            print(f"[Nav] Unknown page: {page_key}")
            return
        self.page_stack.set_visible_child_name(page_key)

    # =====================================================
    # Toast helper
    # =====================================================

    def add_toast(self, toast):
        self._toast_overlay.add_toast(toast)

    # =====================================================
    # LOGIN
    # =====================================================

    def open_login_window(self):
        from ui.function.pup.auth_window import AuthWindow
        auth_win = AuthWindow(self, on_success=self._on_login_success)
        auth_win.present()

    def _on_login_success(self):
        self.navigate_to("home")
        self.add_toast(Adw.Toast(title="✓ Logged in to Proton Drive"))

    # =====================================================
    # AUTH GATE (uses unified config manager)
    # =====================================================

    def _check_auth_and_navigate(self):
        import threading
        import subprocess

        cli = ConfigManager.find_cli(None)

        if not cli:
            print("[PDUA] proton-drive CLI not found")
            toast = Adw.Toast(
                title="⚠ proton-drive CLI not found — click menu → Login to set up"
            )
            toast.set_timeout(0)
            self.add_toast(toast)
            return

        threading.Thread(
            target=self._do_auth_check, args=(cli,), daemon=True
        ).start()

    def _find_proton_drive_cli(self):
        """Retained for backward compat (menu code calls this)."""
        return ConfigManager.find_cli(None)

    def _do_auth_check(self, cli):
        import threading
        import subprocess

        try:
            result = subprocess.run(
                [cli, "auth", "status"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                GLib.idle_add(self._show_login_toast)
        except Exception as e:
            print(f"[PDUA] Auth check error: {e}")

    def _show_login_toast(self):
        toast = Adw.Toast(
            title="Not logged in — click Login to connect to Proton Drive"
        )
        toast.set_timeout(0)
        toast.set_button_label("Login")
        toast.connect("button-clicked", lambda t: self.open_login_window())
        self.add_toast(toast)
