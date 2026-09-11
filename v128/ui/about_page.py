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
           "\n ProtonDrive Utility App v1.2.8"
           "\n Release Date: 07/03/2026."
           "\n It's Unofficial."
           "\n Currently In: Beta."
           "\n Built with Python + GTK4 + libadwaita."
           "\n Open Source & Publicly Available.\n"
           "\n"
           "\n"
           "\n This app is a utility for users who want to use \n the Proton Drive CLI (Command Line Interface) without needing the terminal.\n"
           "\n This app only works with the native proton-drive CLI.\n"
           "\n"
           "\n If you like the app, please share it and enjoy what this project has to offer, give it a like."
           "\n This wouldn't exist or be possible if the Proton AG team \n never released the Proton Drive CLI binary.\n"
           "\n"
           "\n There are many great ways to use this app."
           "\n The Proton AG team is working hard to build the official \n Proton Drive for Linux systems."
           "\n Having a Proton utility app comes with all sorts of benefits:"
           "\n 1. Importing/Exporting in and out of your Proton Drive is just a click of a button."
           "\n 2. A quick way to download everything, rather than using the Proton Drive web interface."
           "\n 3. Flexibility for lower-end hardware."
           "\n 4. The ability to download multiple times, so you know your data is always backed up and safe."
           "\n You can probably think of more amazing uses for this great app.\n"
           "\n"
           "\n Thank you, Proton AG. The community will love and experiment \n with this, developing their own ways of using \n and wanting more flexibility with Proton's services."
           ))
        info.add_css_class("dim-label")
        container.append(info)

        btn_back = Gtk.Button(label="Back to Home")
        btn_back.connect("clicked", lambda *_: self.on_navigate("home"))
        container.append(btn_back)

        return container
