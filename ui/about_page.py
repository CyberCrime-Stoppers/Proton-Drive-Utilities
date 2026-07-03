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
           "ProtonDrive Utility App v1.0.0\n"
           "Built with Python + GTK4 + libadwaita\n"
           "Open Sourced & Publicly Avaliable\n"
           "\n"
           "This App is attended to help with Linux\n Users to easily upload their data\n securely by default to Proton Drive Cloud.\n"
           "\n"
           "this is an UnOfficial Proton Utility - it's a utility that helps Proton Users to manage their Data through proton drive.\n"
           "\n"
           "Businesses/Enterprises can use as well \n Its not a Native App from Proton AG Corp, \n but its directly capitable with Proton-Drive Cli.\n"
           "\n"
           "As this app still abides by Proton AG and Europe Protection Pricacy Laws. \n in other words this app is a tool not a\n telemetry collector of any kind \n or things sending back to the developers\n"
           "\n"
           "This app is not the gateway to Authenticate with proton.\n only with the native proton-drive cli.\n"
           "\n"
           "in order to function properly install and copy the proton-drive cli \n to /usr/bin/proton-drive to \n just get straight on using this app. \n other wise you will need to update the app source code lies on 'proton-drive cli' to your perfered directory"
           "\n"
           "Released date. 07/03/2026."
        ))
        info.add_css_class("dim-label")
        container.append(info)

        btn_back = Gtk.Button(label="Back to Home")
        btn_back.connect("clicked", lambda *_: self.on_navigate("home"))
        container.append(btn_back)

        return container
