import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw


class AboutPage:
    """Simple about / info page."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate

    def build(self):
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
           "\n ProtonDrive Utility App v1.0.1"
           "\n Built with Python + GTK4 + libadwaita"
           "\n Open Sourced & Publicly Avaliable\n"
           "\n This App is attended to help with \n Linux Users to easily upload their data\n securely by default to Proton Drive Cloud.\n"
           "\n this is an UnOfficial Proton Utility \n - it's a utility that helps Proton Users \n to manage their Data through proton drive.\n"
           "\n Businesses/Enterprises can use as \n well Its not a Native App from Proton AG Corp, \n but its directly capitable with Proton-Drive Cli.\n"
           "\n As this app still abides by Proton AG \n and Europe Protection Pricacy Laws. in other \n words this app is a tool not a telemetry collector of any kind \n or things sending back to the developers\n"
           "\n This app is not the gateway to Authenticate with proton.\n only with the native proton-drive cli.\n"
           "\n in order to function properly install \n and copy the proton-drive cli to \n /usr/bin/proton-drive to just get straight \n on using this app. other wise \n you will need to update the \n app source code lies on 'proton-drive cli' \n to your perfered directory\n"
           "\n Released date. 07/03/2026.\n"
        ))
        info.add_css_class("dim-label")
        container.append(info)

        btn_back = Gtk.Button(label="Back to Home")
        btn_back.connect("clicked", lambda *_: self.on_navigate("home"))
        container.append(btn_back)

        return container
