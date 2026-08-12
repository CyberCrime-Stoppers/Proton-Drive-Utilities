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

        menu_model = Gio.Menu()
        menu_model.append("New Window", "app.new")
        menu_model.append("Upload File/Folder to Proton…", "app.open")
        menu_model.append("Preferences", "app.settings")

        help_menu = Gio.Menu()
        help_menu.append("Keyboard Shortcuts", "app.shortcuts")
        help_menu.append("About My App", "app.about")
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

        # ---- sidebar - Selectable Buttons for users choice with proton cli commands ---
        nav_items = [
            ("Home", "home"),
            ("Default Export", "upload"),
            ("Default Download", "download"),
            ("Custom Export", "uploader"),
            ("Custom Import", "downloader"),
            ("Custom Export: Documents", "dcsuploader"),
            ("Custom Export: Downloads", "dnlduploader"),
            ("Custom Export: Pictures", "pcsuploader"),
            ("Custom Export: Videos", "viduploader"),
            ("Custom Export: Music", "musuploader"),
            ("Custom Import: Documents", "dcsdownloader"),
            ("Custom Import: Downloads", "dnlddownloader"),
            ("Custom Import: Pictures", "pcsdownloader"),
            ("Custom Import: Videos", "viddownloader"),
            ("Custom Import: Music", "musdownloader"),
            ("Settings", "settings"),
            ("About", "about"),
        ]

        self.page_stack = Gtk.Stack()
        self.page_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
        self.page_stack.set_hexpand(True)

        # Add pages (FIXED: correct class names and parent_window)
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

        for label, key in nav_items:
            row = Gtk.Button(label=label)
            row.set_has_frame(True)
            row.set_halign(Gtk.Align.FILL)
            row.connect("clicked", lambda b, k=key: self.navigate_to(k))
            sidebar.append(row)

            page_widget = self.pages[key].build(parent_window=self)  # ← FIXED
            self.page_stack.add_named(page_widget, key)

        # Sidebar in scrolled window
        scrolled_sidebar = Gtk.ScrolledWindow()
        scrolled_sidebar.set_child(sidebar)
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

    def navigate_to(self, page_key):
        """Switch the visible page."""
        self.page_stack.set_visible_child_name(page_key)
