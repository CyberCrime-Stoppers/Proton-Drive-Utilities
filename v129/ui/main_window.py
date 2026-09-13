import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
import os
import shutil
import subprocess
import threading
from ui.function.home_page import HomePage
from ui.function.config.proton_settings_page import ProtonSettingsPage
from ui.tree.fixdo.upload_page import UploadPage
from ui.tree.fixdo.download_page import DownloadPage
from ui.tree.cusdo.uploader_page import UploaderPage
from ui.tree.cusdo.downloader_page import DownloaderPage
from ui.tree.down.doc_downloader_page import DocDownloaderPage
from ui.tree.down.dwn_downloader_page import DwnDownloaderPage
from ui.tree.down.pic_downloader_page import PicDownloaderPage
from ui.tree.down.vid_downloader_page import VidDownloaderPage
from ui.tree.down.mus_downloader_page import MusDownloaderPage
from ui.tree.up.doc_uploader_page import DocUploaderPage
from ui.tree.up.dwn_uploader_page import DwnUploaderPage
from ui.tree.up.pic_uploader_page import PicUploaderPage
from ui.tree.up.vid_uploader_page import VidUploaderPage
from ui.tree.up.mus_uploader_page import MusUploaderPage
from ui.function.config.settings_page import SettingsPage
from ui.about_page import AboutPage
from gi.repository import Gtk, Adw, Gio, GLib


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Proton Drive Utility App")
        self.set_default_size(1000, 800)

        # ---- Header Bar with Menu Button ----
        header = Adw.HeaderBar()

        # --- Theme submenu ---
        theme_menu = Gio.Menu()
        theme_menu.append("🌙  Dark Mode", "app.theme-dark")
        theme_menu.append("☀  Light Mode", "app.theme-light")
        theme_menu.append("🖥  System Default", "app.theme-system")

        # --- Main menu with Login at top ---
        menu_model = Gio.Menu()

        login_section = Gio.Menu()
        login_section.append("🔐  Login or Logout…", "app.login")
        menu_model.append_section(None, login_section)
        menu_model.append("New Window", "app.new")
        menu_model.append("📸 Albums", "app.albums")
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

        self.pages = {}
        self.pages["home"] = HomePage(on_navigate=self.navigate_to)
        self.pages["protonsettingspage"] = ProtonSettingsPage(on_navigate=self.navigate_to)
        self.pages["upload"] = UploadPage(on_navigate=self.navigate_to)
        self.pages["download"] = DownloadPage(on_navigate=self.navigate_to)
        self.pages["uploader"] = UploaderPage(on_navigate=self.navigate_to)
        self.pages["downloader"] = DownloaderPage(on_navigate=self.navigate_to)
        self.pages["docuploader"] = DocUploaderPage(on_navigate=self.navigate_to)
        self.pages["dwnuploader"] = DwnUploaderPage(on_navigate=self.navigate_to)
        self.pages["picuploader"] = PicUploaderPage(on_navigate=self.navigate_to)
        self.pages["viduploader"] = VidUploaderPage(on_navigate=self.navigate_to)
        self.pages["musuploader"] = MusUploaderPage(on_navigate=self.navigate_to)
        self.pages["docdownloader"] = DocDownloaderPage(on_navigate=self.navigate_to)
        self.pages["dwndownloader"] = DwnDownloaderPage(on_navigate=self.navigate_to)
        self.pages["picdownloader"] = PicDownloaderPage(on_navigate=self.navigate_to)
        self.pages["viddownloader"] = VidDownloaderPage(on_navigate=self.navigate_to)
        self.pages["musdownloader"] = MusDownloaderPage(on_navigate=self.navigate_to)
        self.pages["settings"] = SettingsPage(on_navigate=self.navigate_to)
        self.pages["about"] = AboutPage(on_navigate=self.navigate_to)

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

        # ---- Toast overlay: wraps everything so add_toast() works ----
        self._toast_overlay = Adw.ToastOverlay()
        self._toast_overlay.set_child(outer)
        self.set_content(self._toast_overlay)

        self.navigate_to("home")

        # ---- Auth gate on startup ----
        self._check_auth_and_navigate()

    def add_toast(self, toast):
        """Public helper so pages can call parent_window.add_toast()."""
        self._toast_overlay.add_toast(toast)

    def _build_sidebar(self):
        """Sidebar with flat items and expandable dropdown groups."""
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.add_css_class("navigation-sidebar")

        # --- Top-level flat items ---
        for label, key in [
            ("🏠  Home", "home"),
            ("🛡️  Proton Settings Page", "protonsettingspage"),
        ]:
            container.append(self._make_nav_button(label, key))

        # --- Expandable groups ---
        groups = [
            ("⬆  Upload to Proton", [
                ("Fixed: Export", "upload"),
                ("Custom Export: Fixed Directory", "uploader"),
                ("Custom Export: Documents", "docuploader"),
                ("Custom Export: Downloads", "dwnuploader"),
                ("Custom Export: Pictures", "picuploader"),
                ("Custom Export: Videos", "viduploader"),
                ("Custom Export: Music", "musuploader"),
            ]),
            ("⬇  Download from Proton", [
                ("Fixed: Import", "download"),
                ("Custom Import: Fixed Directory", "downloader"),
                ("Custom Import: Documents", "docdownloader"),
                ("Custom Import: Downloads", "dwndownloader"),
                ("Custom Import: Pictures", "picdownloader"),
                ("Custom Import: Videos", "viddownloader"),
                ("Custom Import: Music", "musdownloader"),
            ]),
        ]

        for group_label, items in groups:
            expander = Gtk.Expander(label=group_label)
            expander.set_expanded(True)
            expander.add_css_class("sidebar-group")

            inner_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            inner_box.set_margin_start(12)

            for sub_label, sub_key in items:
                inner_box.append(self._make_nav_button(sub_label, sub_key, indent=True))

            expander.set_child(inner_box)
            container.append(expander)

        # --- Bottom flat items ---
        for label, key in [("⚙  Options", "settings"), ("ℹ  About", "about")]:
            container.append(self._make_nav_button(label, key))

        return container

    def _make_nav_button(self, label, page_key, indent=False):
        """Create a single navigation button."""
        btn = Gtk.Button(label=label)
        btn.set_has_frame(False)
        btn.set_halign(Gtk.Align.FILL)
        if indent:
            btn.set_margin_start(12)
        btn.connect("clicked", lambda b, k=page_key: self.navigate_to(k))
        return btn

    def navigate_to(self, page_key):
        """Switch the visible page."""
        self.page_stack.set_visible_child_name(page_key)

    # ===== LOGIN (called from app action + login toast) =====

    def open_login_window(self):
        """Open the login popup window (shared entry point)."""
        from ui.function.pup.auth_window import AuthWindow

        auth_win = AuthWindow(self, on_success=self._on_login_success)
        auth_win.present()

    def _on_login_success(self):
        """Called when the login popup reports success."""
        self.navigate_to("home")
        self.add_toast(Adw.Toast(title="✓ Logged in to Proton Drive"))

    # ===== AUTH GATE =====

    def _check_auth_and_navigate(self):
        """Check CLI auth status on startup, notify if not logged in."""
        cli = self._find_proton_drive_cli()

        if not cli:
            print("[PDUA] proton-drive CLI not found")
            toast = Adw.Toast(
                title="⚠ proton-drive CLI not found — click menu → Login to set up"
            )
            toast.set_timeout(0)  # persistent until dismissed
            self.add_toast(toast)
            return

        threading.Thread(
            target=self._do_auth_check, args=(cli,), daemon=True
        ).start()

    def _find_proton_drive_cli(self):
        """Locate the proton-drive CLI binary."""
        candidates = [
            "/usr/bin/proton-drive",
            "/usr/local/bin/proton-drive",
            os.path.expanduser("~/.local/bin/proton-drive"),
        ]
        for path in candidates:
            if os.path.isfile(path) and os.access(path, os.X_OK):
                return path
        return shutil.which("proton-drive")

    def _do_auth_check(self, cli):
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
        """Persistent toast prompting login, with a Login button."""
        toast = Adw.Toast(
            title="Not logged in — click Login to connect to Proton Drive"
        )
        toast.set_timeout(0)
        toast.set_button_label("Login")
        toast.connect("button-clicked", lambda t: self.open_login_window())
        self.add_toast(toast)
