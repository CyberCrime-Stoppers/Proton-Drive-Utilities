import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw
import subprocess
import webbrowser


class HomePage:
    """Home page with functional buttons."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate

    def build(self, parent_window=None):
        self._parent_window = parent_window

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=15,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        title = Gtk.Label(
            label="<span size='xx-large' font='ital' weight='bold'>\t \nProton Drive Utility App</span>"
        )
        title.set_use_markup(True)
        container.append(title)

        subtitle = Gtk.Label(
            label="<span size='medium' font='serf' weight='bold'>\nUnOfficial Proton Drive Utility\n</span>"
        )
        subtitle.set_use_markup(True)
        subtitle.add_css_class("dim-label")
        container.append(subtitle)

        # --- Button: Open a URL ---
        btn_url = Gtk.Button(label="* Github Page")
        btn_url.set_size_request(400, -1)
        btn_url.connect("clicked", lambda *_: webbrowser.open("https://github.com/CyberCrime-Stoppers/"))
        container.append(btn_url)

        return container
