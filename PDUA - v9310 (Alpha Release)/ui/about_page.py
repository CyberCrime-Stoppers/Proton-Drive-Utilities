#!/usr/bin/env python3

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, GLib


# ----------------------------------------------------------------------
# Markup helpers — all text is escaped, so no stray &amp; or < can break
# Pango markup.
# ----------------------------------------------------------------------
def _esc(text):
    return GLib.markup_escape_text(text)


def _b(text):
    return "<b>" + _esc(text) + "</b>"


def _i(text):
    return "<i>" + _esc(text) + "</i>"


class AboutPage:
    """About page showing README.md's description of PDUA."""

    def __init__(self, on_navigate=None):
        self.on_navigate = on_navigate

    def build(self, parent_window=None):
        self._parent_window = parent_window

        container = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=20,
            margin_bottom=20,
            margin_start=24,
            margin_end=24,
        )

        # ---------- Page title ----------
        container.append(self._heading("About"))

        # ---------- Intro (README header) ----------
        container.append(self._body(
            "Proton Drive Utility App (PDUA); CyberCrime-Stoppers (CCS). is the one \n"
            "original Founder and the Development of this useful Linux APP."
            "Proudly working &amp; Developing the App for Proton AG Users that want more with \n"
            "their Cloud Drive situations."
        ))

        container.append(Gtk.Separator())

        # ---------- Title + metadata list ----------
        container.append(self._heading("Proton Drive Utility App (PDUA)", large=True))

        meta = [
            "Unofficial",
            "Currently in: " + _i("Beta."),
            "Released Date: " + _i("07/03/2026. [MM/DD/YYYY]"),
            "App Version: " + _i("v1.2.10 - updated: 09/13/2026. [MM/DD/YYYY]"),
            "Language: " + _i("Python | Shell script"),
            "Standard Libraries: " + _i("subprocess | threading | os | shutil | webbrowser | subprocess"),
            "GUI Framework: gi (PyGObject) - " + _i("The bridge to access C libraries (GTK, Adw)."),
            "Module(s): " + _i("GTK4 | Libadwaita"),
            _i("Opened Sourced &amp; Publicly Available."),
        ]
        container.append(self._bullets(meta))

        # ---------- AI vs Human ----------
        container.append(self._subheading("AI vs Human - Developed. [Created By]"))
        container.append(self._body("LLM/AI (%)"))
        container.append(self._quote("pdua (25 %)"))
        container.append(self._body("HUMAN (%)"))
        container.append(self._quote("pdua (75 %)"))

        # ---------- Benefits ----------
        container.append(self._heading(
            "🌟 Lists of benefits on why This App exists and use cases.", large=True
        ))
        container.append(self._body(
            "The Proton AG team is working hard to build the official Proton Drive "
            "for Linux systems."
        ))
        container.append(self._subheading("Having a Proton utility app can have many benifits"))

        benefits = [
            "📤 Importing/Exporting in and out of your Proton Drive is just a click of a button.",
            "⬇️ A quick way to download everything, rather than using the Proton Drive web interface.",
            "💻 Flexibility for lower-end hardware.",
            "🔄 The ability to download multiple times, so you know your data is always backed up and safe.",
        ]
        container.append(self._bullets(benefits))
        container.append(self._quote("💡 You can probably think of more amazing uses for this great app."))
        container.append(self._quote(
            "If and when the Official Proton Drive App has been released by Proton AG "
            "and their team surely many out there would still use this app for the many "
            "benefits listed above. ☝️"
        ))

        # ---------- Feature status ----------
        container.append(self._heading(
            "Features that has been worked on, that are crucial to have.", large=True
        ))
        container.append(self._body("✅ Implemented/Fixed"))
        container.append(self._body("❌ NOT Implemented/Fixed (As of yet)"))

        features = [
            "✅" + _b("Progress Bar:") + " -Importing or Exporting your data in or out of "
            "your Proton cloud drive -should show a progress metor bar to show on how many "
            "queries and speed a second.",

            "❌ " + _b("Album/Photos Caching:") + " -Cached photos are needed to help better "
            "understand on whats in your proton drive. it's your right to access your data "
            "all the way. in which you can better manage what matters.'",

            "❌ " + _b("Preferences/Options:") + " -The Options page or other words Preferences "
            "page in the app needs work, added features n options. like (font size (FS), "
            "AutoDetect Username (ADU), Customizing User Layout (CUL), Auto Importing &amp; "
            "Exporting (AIE), - etc).",

            "❌ " + _b("Few Bug Fixes:") + " -App Detection. (Knowing users are logged in, "
            "Keyboard Shortcuts) adding these features will help alot.",
        ]
        container.append(self._bullets(features))

        # ---------- Acronyms ----------
        container.append(self._subheading(
            "Acronyms shown in Preferences/Options Descritions"
        ))
        acronyms = [
            _b("CUL:") + " Users can change anything like how the UI is viewed and "
            "choose how their apps behave.",

            "FS: Changing the font size user can choose to change size in the side bar "
            "panel, sub-windows, or app pages.",

            _b("AIE:") + " Auto Detect or set a time when you want your data to be imported "
            "or exported in or out of your proton drive.",

            "ADU: After a user logs in to their Proton account, the app should autodetect "
            "their username and then display their username for any reassurance reasons.",
        ]
        container.append(self._bullets(acronyms))

        # ---------- Back ----------
        btn_back = Gtk.Button(label="Back to Home")
        btn_back.set_halign(Gtk.Align.CENTER)
        btn_back.set_margin_top(12)
        btn_back.connect("clicked", lambda *_: self.on_navigate("home"))
        container.append(btn_back)

        # ---------- Scrollable wrapper ----------
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        scrolled.set_child(container)
        return scrolled

    # ================= LABEL BUILDERS =================

    def _heading(self, text, large=False):
        size = "x-large" if not large else "large"
        lbl = Gtk.Label()
        lbl.set_markup(f"<span size='{size}' weight='bold'>{_esc(text)}</span>")
        lbl.set_wrap(True)
        lbl.set_xalign(0.0)
        lbl.set_selectable(True)
        lbl.set_margin_top(8)
        return lbl

    def _subheading(self, text):
        lbl = Gtk.Label()
        lbl.set_markup("<b>" + _esc(text) + "</b>")
        lbl.set_wrap(True)
        lbl.set_xalign(0.0)
        lbl.set_selectable(True)
        lbl.set_margin_top(6)
        return lbl

    def _body(self, markup):
        lbl = Gtk.Label()
        lbl.set_markup(markup)
        lbl.set_wrap(True)
        lbl.set_xalign(0.0)
        lbl.set_selectable(True)
        return lbl

    def _bullets(self, items):
        lines = ["•  " + item for item in items]
        lbl = Gtk.Label()
        lbl.set_markup("\n".join(lines))
        lbl.set_wrap(True)
        lbl.set_xalign(0.0)
        lbl.set_selectable(True)
        lbl.set_margin_start(8)
        return lbl

    def _quote(self, markup):
        lbl = Gtk.Label()
        lbl.set_markup("<i>" + markup + "</i>")
        lbl.set_wrap(True)
        lbl.set_xalign(0.0)
        lbl.set_selectable(True)
        lbl.set_margin_start(16)
        lbl.add_css_class("dim-label")
        return lbl
