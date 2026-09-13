import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from ui.home_page import HomePage
from ui.upload_page import UploadPage
from ui.download_page import DownloadPage
from ui.uploader_page import UploaderPage
from ui.downloader_page import DownloaderPage
from ui.settings_page import SettingsPage
from ui.about_page import AboutPage
from gi.repository import Gtk, Adw, Gio


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.set_title("Proton Drive Utility App")
        self.set_default_size(900, 600)

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

        nav_items = [
            ("Home", "home"),
            ("Fixed Upload", "upload"),
            ("Fixed Download", "download"),
            ("Custom Upload", "uploader"),
            ("Custom Download", "downloader"),
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
        self.pages["uploader"] = UploaderPage(on_navigate=self.navigate_to)  # ← FIXED
        self.pages["downloader"] = DownloaderPage(on_navigate=self.navigate_to)
        self.pages["settings"] = SettingsPage(on_navigate=self.navigate_to)
        self.pages["about"] = AboutPage(on_navigate=self.navigate_to)

        for label, key in nav_items:
            row = Gtk.Button(label=label)
            row.set_has_frame(False)
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
