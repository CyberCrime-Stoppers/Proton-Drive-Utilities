import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw
import json
import os


CONFIG_DIR = os.path.expanduser("~/.config/protondrive-utilityapp")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")


class SettingsPage:
    """Settings page with persistent config."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate
        self.config = self._load_config()

    def _load_config(self):
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        return {"username": "", "dark_mode": False, "notifications": True}

    def _save_config(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.config, f, indent=2)


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

        header = Gtk.Label(label="<span size='x-large' weight='bold'>Settings</span>")
        header.set_use_markup(True)
        header.set_halign(Gtk.Align.START)
        container.append(header)

        title = Gtk.Label(label="<span size='x-large' weight='bold'>USERNAME</span>")
        title.set_use_markup(True)
        container.append(title)

        info = Gtk.Label(label=("Option to Idetitfy Your Proton Account" ))

        info.add_css_class("dim-label")
        container.append(info)

        # --- Username entry ---
        user_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        user_label = Gtk.Label(label="Enter a Name:")
        user_label.set_xalign(0)
        user_entry = Gtk.Entry()
        user_entry.set_placeholder_text("Type Here")
        user_entry.set_text(self.config.get("passcode", ""))
        user_entry.connect("changed", self._on_username_changed)
        user_box.append(user_label)
        user_box.append(user_entry)
        container.append(user_box)

  # --- Save button ---
        btn_save = Gtk.Button(label="Save Settings")
        btn_save.add_css_class("suggested-action")
        btn_save.connect("clicked", lambda *_: self._save_config())
        container.append(btn_save)

        # --- Back button ---
        btn_back = Gtk.Button(label="Back to Home")
        btn_back.connect("clicked", lambda *_: self.on_navigate("home"))
        container.append(btn_back)


  # --- User Configuration | font size management ---

        fsheader = Gtk.Label(label="<span size='x-large' weight='bold'>Font Size Configuration</span>")
        fsheader.set_use_markup(True)
        fsheader.set_halign(Gtk.Align.START)
        container.append(fsheader)

        fsinfo = Gtk.Label(label=("Choose your font size" ))

        fsinfo.add_css_class("dim-label")
        container.append(fsinfo)

        fsuptitle = Gtk.Label(label="<span size='large' weight='bold'>🔼</span>")
        fsuptitle.set_use_markup(True)
        container.append(fsuptitle)


        fsdntitle = Gtk.Label(label="<span size='large' weight='bold'>🔽</span>")
        fsdntitle.set_use_markup(True)
        container.append(fsdntitle)




        return container

    def _make_row(self, label_text, switch_widget):
        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        lbl = Gtk.Label(label=label_text)
        lbl.set_xalign(0)
        lbl.set_hexpand(True)
        row.append(lbl)
        row.append(switch_widget)
        return row

    def _on_username_changed(self, entry):
        self.config["passcode"] = entry.get_text()


