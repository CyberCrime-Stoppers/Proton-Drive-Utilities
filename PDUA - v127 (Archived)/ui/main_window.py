import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from ui.home_page import HomePage
from ui.upload_page import UploadPage
from ui.download_page import DownloadPage
from ui.uploader_page import UploaderPage
from ui.downloader_page import DownloaderPage
from ui.sub.dcs_downloader_page import DcsDownloaderPage
from ui.sub.dnld_downloader_page import DnldDownloaderPage
from ui.sub.pcs_downloader_page import PcsDownloaderPage
from ui.sub.vid_downloader_page import VidDownloaderPage
from ui.sub.mus_downloader_page import MusDownloaderPage
from ui.sub.dcs_uploader_page import DcsUploaderPage
from ui.sub.dnld_uploader_page import DnldUploaderPage
from ui.sub.pcs_uploader_page import PcsUploaderPage
from ui.sub.vid_uploader_page import VidUploaderPage
from ui.sub.mus_uploader_page import MusUploaderPage
from ui.settings_page import SettingsPage
from ui.about_page import AboutPage
from gi.repository import Gtk, Adw, Gio


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

        # ---- Sidebar layout ----
        sidebar = Gtk.ListBox()
        sidebar.set_size_request(200, -1)
        sidebar.set_hexpand(False)
        sidebar.set_vexpand(True)
        sidebar.add_css_class("navigation-sidebar")

        # ---- Build all pages ----
        self.page_stack = Gtk.Stack()
        self.page_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.page_stack.set_hexpand(True)



        self.pages = {}
        self.pages["home"] = HomePage(on_navigate=self.navigate_to)
        self.pages["upload"] = UploadPage(on_navigate=self.navigate_to)
        self.pages["download"] = DownloadPage(on_navigate=self.navigate_to)
        self.pages["uploader"] = UploaderPage(on_navigate=self.navigate_to)
        self.pages["downloader"] = DownloaderPage(on_navigate=self.navigate_to)
        self.pages["dcsuploader"] = DcsUploaderPage(on_navigate=self.navigate_to)
        self.pages["dnlduploader"] = DnldUploaderPage(on_navigate=self.navigate_to)
        self.pages["pcsuploader"] = PcsUploaderPage(on_navigate=self.navigate_to)
        self.pages["viduploader"] = VidUploaderPage(on_navigate=self.navigate_to)
        self.pages["musuploader"] = MusUploaderPage(on_navigate=self.navigate_to)
        self.pages["dcsdownloader"] = DcsDownloaderPage(on_navigate=self.navigate_to)
        self.pages["dnlddownloader"] = DnldDownloaderPage(on_navigate=self.navigate_to)
        self.pages["pcsdownloader"] = PcsDownloaderPage(on_navigate=self.navigate_to)
        self.pages["viddownloader"] = VidDownloaderPage(on_navigate=self.navigate_to)
        self.pages["musdownloader"] = MusDownloaderPage(on_navigate=self.navigate_to)
        self.pages["settings"] = SettingsPage(on_navigate=self.navigate_to)
        self.pages["about"] = AboutPage(on_navigate=self.navigate_to)

        # page widgets
        for key, page in self.pages.items():
            page_widget = page.build(parent_window=self)
            self.page_stack.add_named(page_widget, key)

        # ---- Sidebar with dropdown sections ----
        sidebar = self._build_sidebar()

        # Sidebar in scrolled window
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

        self.set_content(outer)
        self.navigate_to("home")

    def _build_sidebar(self):
        """sidebar with flat items and expandable dropdown groups."""
        container = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        container.add_css_class("navigation-sidebar")

        # --- Top-level flat items ---
        for label, key in [("🏠  Home", "home")]:
            container.append(self._make_nav_button(label, key))

        # --- Expandable groups ---
        groups = [
            ("⬆  Upload to Proton", [
                ("Fixed: Export", "upload"),
                ("Custom Fixed: Export", "uploader"),
                ("Custom Export: Documents", "dcsuploader"),
                ("Custom Export: Downloads", "dnlduploader"),
                ("Custom Export: Pictures", "pcsuploader"),
                ("Custom Export: Videos", "viduploader"),
                ("Custom Export: Music", "musuploader"),
            ]),
            ("⬇  Download from Proton", [
                ("Fixed: Import", "download"),
                ("Custom Fixed: Import", "downloader"),
                ("Custom Import: Documents", "dcsdownloader"),
                ("Custom Import: Downloads", "dnlddownloader"),
                ("Custom Import: Pictures", "pcsdownloader"),
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
                btn = self._make_nav_button(sub_label, sub_key, indent=True)
                inner_box.append(btn)

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

    # ===== LOGIN (dropdown menu action → popup window) =====

    def _on_login(self, action, param):
        """Open the login popup window from the hamburger menu."""
        from ui.login_window import LoginWindow

        login_win = LoginWindow(self, on_success=self._on_login_success)
        login_win.present()

    def _on_login_success(self):
        """Called when the login popup reports success."""
        self.navigate_to("home")
        toast = Adw.Toast(title="✓ Logged in to Proton Drive")
        self.add_toast(toast)

    # ===== AUTH GATE =====

    def _check_auth_and_navigate(self):
        """Check CLI auth status on startup, navigate accordingly."""
        cli = self._find_proton_drive_cli()

        if not cli:
            print("[PDUA] proton-drive CLI not found")
            self.navigate_to("home")
            toast = Adw.Toast(
                title="⚠ proton-drive CLI not found — click menu → Login to set up"
            )
            toast.set_timeout(0)  # persistent until dismissed
            self.add_toast(toast)
            return

        t = threading.Thread(target=self._do_auth_check, args=(cli,), daemon=True)
        t.start()

    def _find_proton_drive_cli(self):
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

    def _do_auth_check(self, cli):
        try:
            result = subprocess.run(
                [cli, "auth", "status"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                GLib.idle_add(self.navigate_to, "home")
            else:
                GLib.idle_add(self._show_login_toast)
        except Exception as e:
            print(f"[PDUA] Auth check error: {e}")
            GLib.idle_add(self.navigate_to, "home")

    def _show_login_toast(self):
        """Show a toast telling the user to log in."""
        self.navigate_to("home")
        toast = Adw.Toast(
            title="Not logged in — click menu → Login to Proton Drive"
        )
        toast.set_timeout(0)
        toast.set_button_label("Login")
        toast.connect("button-clicked", lambda t: self._on_login(None, None))
        self.add_toast(toast)

