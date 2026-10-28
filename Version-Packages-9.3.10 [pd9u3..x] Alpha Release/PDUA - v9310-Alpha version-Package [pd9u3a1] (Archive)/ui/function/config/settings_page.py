#!/usr/bin/env python3
"""
General Settings Page — updated for unified ConfigManager
Fixes:
  - Uses ConfigManager() instance (was calling static methods → crash)
  - Renamed 'passcode' key to 'username' (security fix)
  - Font-size controls are now functional (were decorative before)
  - Save button is now at the end of the form (previously halfway through)
"""

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Adw
from ui.function.config_manager import ConfigManager


class SettingsPage:
    """General settings page using unified ConfigManager."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate
        self.config_manager = ConfigManager()      # ✅ instance
        self.config = self.config_manager.load()
        self._parent_window = None

        # Track font size changes
        self.font_size = self.config.get("font_size", 9)

    def build(self, parent_window=None):
        self._parent_window = parent_window

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=18,
            margin_top=20,
            margin_bottom=20,
            margin_start=20,
            margin_end=20,
        )

        # --- Header ---
        header = Gtk.Label(label="<span size='x-large' weight='bold'>Settings</span>")
        header.set_use_markup(True)
        header.set_halign(Gtk.Align.START)
        container.append(header)

        # --- Username (formerly "passcode") ---
        user_group = Adw.PreferencesGroup()
        user_group.set_title("Account Identity")
        user_group.set_description("Your display name across the app")

        self.user_entry = Gtk.Entry()
        self.user_entry.set_placeholder_text("Enter your name")
        self.user_entry.set_text(self.config.get("username", ""))
        self.user_entry.connect("changed", self._on_username_changed)

        user_row = Adw.ActionRow(title="Display Name")
        user_row.add_suffix(self.user_entry)
        user_group.add(user_row)
        container.append(user_group)

        # --- Appearance ---
        appearance_group = Adw.PreferencesGroup()
        appearance_group.set_title("Appearance")
        appearance_group.set_description("Dark mode and font size")

        # Dark mode toggle
        self.dark_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.dark_switch.set_active(self.config.get("dark_mode", False))
        self.dark_switch.connect("notify::active", self._on_dark_toggled)

        dark_row = Adw.ActionRow(title="Dark Mode", subtitle="Toggle dark theme")
        dark_row.add_suffix(self.dark_switch)
        appearance_group.add(dark_row)

        # Font size controls (FUNCTIONAL now)
        font_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12, margin_top=8)
        
        # Increase button
        btn_increase = Gtk.Button()
        btn_increase.set_icon_name("zoom-in-symbolic")
        btn_increase.add_css_class("circular")
        btn_increase.connect("clicked", lambda w: self._change_font(+1))
        
        # Current size display
        self.font_label = Gtk.Label(label=f"{self.font_size}px")
        self.font_label.set_hexpand(True)
        self.font_label.set_halign(Gtk.Align.CENTER)
        
        # Decrease button
        btn_decrease = Gtk.Button()
        btn_decrease.set_icon_name("zoom-out-symbolic")
        btn_decrease.add_css_class("circular")
        btn_decrease.connect("clicked", lambda w: self._change_font(-1))
        
        font_box.append(btn_decrease)
        font_box.append(self.font_label)
        font_box.append(btn_increase)

        font_row = Adw.ActionRow(title="Font Size", subtitle="Adjust text size")
        font_row.add_suffix(font_box)
        appearance_group.add(font_row)
        container.append(appearance_group)

        # --- Notifications ---
        notify_group = Adw.PreferencesGroup()
        notify_group.set_title("Notifications")

        self.notify_switch = Gtk.Switch(valign=Gtk.Align.CENTER)
        self.notify_switch.set_active(self.config.get("notifications", True))
        self.notify_switch.connect("notify::active", self._on_notify_toggled)

        notify_row = Adw.ActionRow(title="Enable Toast Notifications")
        notify_row.add_suffix(self.notify_switch)
        notify_group.add(notify_row)
        container.append(notify_group)

        # --- Save Button (NOW AT THE END, not middle) ---
        btn_save = Gtk.Button(label="Save Settings")
        btn_save.add_css_class("suggested-action")
        btn_save.set_size_request(400, -1)
        btn_save.set_halign(Gtk.Align.CENTER)
        btn_save.connect("clicked", self._on_save_clicked)
        container.append(btn_save)

        # --- Back Button ---
        btn_back = Gtk.Button(label="Back to Home")
        btn_back.set_halign(Gtk.Align.CENTER)
        btn_back.connect("clicked", lambda *_: self.on_navigate("home"))
        container.append(btn_back)

        return container

    # ================= HANDLERS =================

    def _on_username_changed(self, entry):
        # Defer save until explicit click (avoid rapid writes)
        pass

    def _on_dark_toggled(self, switch, _):
        self.config["dark_mode"] = switch.get_active()
        self.config_manager.save(self.config)

    def _on_notify_toggled(self, switch, _):
        self.config["notifications"] = switch.get_active()
        self.config_manager.save(self.config)

    def _change_font(self, delta):
        self.font_size = max(7, min(14, self.font_size + delta))
        self.font_label.set_text(f"{self.font_size}px")
        self.config["font_size"] = self.font_size
        self.config_manager.save(self.config)

        # Apply CSS to parent window if possible
        if self._parent_window:
            css = f"{{ font-size: {self.font_size}px; }}"
            provider = Gtk.CssProvider()
            provider.load_from_data(css.encode())
            Gtk.StyleContext.add_provider_for_display(
                self._parent_window.get_display(),
                provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )

    def _on_save_clicked(self, widget):
        # Save username immediately
        self.config["username"] = self.user_entry.get_text().strip()
        
        # Save all other tracked changes
        self.config_manager.save(self.config)

        if self._parent_window and hasattr(self._parent_window, "add_toast"):
            self._parent_window.add_toast(
                Adw.Toast(title="✓ Settings saved", timeout=3)
            )
