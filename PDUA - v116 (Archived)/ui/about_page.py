import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw


class AboutPage:
    """Simple about / info page."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate

    def build(self, parent_window=None):  # ← FIXED
        self._parent_window = parent_window  # ← ADDED

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            valign=Gtk.Align.CENTER,
            halign=Gtk.Align.CENTER,
        )

        title = Gtk.Label(label="<span size='x-large' weight='bold'>About</span>")
        title.set_use_markup(True)
        container.append(title)

        info = Gtk.Label(label=(
           "\n ProtonDrive Utility App v1.1.6"
           "\n Built with Python + GTK4 + libadwaita"
           "\n Open Sourced & Publicly Available\n"
           "\n This App is intended to help Linux Users to easily upload their data\n securely by default to Proton Drive Cloud. \n not limited to the use of a NAS\n"
           "\n This is an Unofficial Proton Utility - It's built as a utility not your typical proton drive for Windows in mind.\n"
           "\n This app abides by Proton AG and Europian Privacy Laws. \n In other words this app is a tool, not a telemetry collector of any kind \n or things sending back to the developers request.\n"
           "\n This app is not the gateway to authenticate with proton.\n only works with the native proton-drive cli.\n"
           "\n In order to function properly install \n and copy the proton-drive cli to \n /usr/bin/proton-drive to get straight \n into using this app. otherwise \n you will need to update the \n app binary source code reference on 'proton-drive cli' \n to your preferred directory.\n"
           "\n Release Date: 07/03/2026.\n"
        ))
        info.add_css_class("dim-label")
        container.append(info)

        btn_back = Gtk.Button(label="Back to Home")
        btn_back.connect("clicked", lambda *_: self.on_navigate("home"))
        container.append(btn_back)

        return container
