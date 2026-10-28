import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib, GObject
import subprocess
import threading
import os
import json


class AlbumsWindow(Adw.Window):
    """Popup window listing Proton Drive albums as folder-icon tiles."""

    __gsignals__ = {
        "album-opened": (Gio.SignalFlags.RUN_FIRST, None, (str,)),
    }

    def __init__(self, parent_window, cli_binary="proton-drive"):
        super().__init__(
            transient_for=parent_window,
            modal=True,
            title="Proton Drive Albums",
            default_width=720,
            default_height=520,
        )
        self.cli_binary = cli_binary
        self._build_ui()
        self._load_albums()

    # ---------------- UI ----------------

    def _build_ui(self):
        self._toast_overlay = Adw.ToastOverlay()

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL,
                       margin_top=15, margin_bottom=15,
                       margin_start=15, margin_end=15)

        header = Adw.HeaderBar()
        header.set_show_end_title_buttons(True)
        main.append(header)

        self._stack = Gtk.Stack()
        main.append(self._stack)

        # 1. Loading
        spinner = Adw.Spinner()
        spinner.set_margin_top(80)
        spinner.set_valign(Gtk.Align.CENTER)
        spinner.set_halign(Gtk.Align.CENTER)
        self._stack.add_named(spinner, "loading")

        # 2. Albums grid
        scrolled = Gtk.ScrolledWindow(vexpand=True)
        self._flow = Gtk.FlowBox(
            selection_mode=Gtk.SelectionMode.NONE,
            min_children_per_line=3,
            max_children_per_line=6,
            column_spacing=15,
            row_spacing=15,
            homogeneous=True,
        )
        scrolled.set_child(self._flow)
        self._stack.add_named(scrolled, "albums")

        # 3. Empty / error
        self._status = Adw.StatusPage(
            icon_name="folder-symbolic",
            title="No albums found",
        )
        self._stack.add_named(self._status, "empty")

        self._toast_overlay.set_child(main)
        self.set_content(self._toast_overlay)

    # ------------- Album tile -------------

    def _make_album_tile(self, name, count=None):
        """A folder icon + album name, styled like a folder shortcut."""
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                      valign=Gtk.Align.CENTER)
        box.add_css_class("card")
        box.set_margin_top(10); box.set_margin_bottom(10)
        box.set_margin_start(10); box.set_margin_end(10)

        icon = Gtk.Image.new_from_icon_name("folder-symbolic")
        icon.set_pixel_size(64)
        box.append(icon)

        name_label = Gtk.Label(label=name, width_chars=14)
        name_label.set_ellipsize(Pango.EllipsizeMode.END)
        box.append(name_label)

        if count is not None:
            count_label = Gtk.Label(label=f"{count} items")
            count_label.add_css_class("dim-label")
            count_label.add_css_class("caption")
            box.append(count_label)

        btn = Gtk.Button(child=box)
        btn.add_css_class("flat")
        btn.connect("clicked", self._on_album_clicked, name)
        return btn

    # ------------- Data (CLI) -------------

    def _cmd_list_albums(self):
        # TODO: match your CLI's real album command
        return [self.cli_binary, "album", "list", "--json"]

    def _cmd_list_album_files(self, album):
        return [self.cli_binary, "album", "list", album, "--json"]

    def _load_albums(self):
        self._stack.set_visible_child_name("loading")
        threading.Thread(target=self._run_load, daemon=True).start()

    def _run_load(self):
        albums = []
        err = ""
        try:
            result = subprocess.run(
                self._cmd_list_albums(), capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                albums = self._parse_albums(result.stdout)
            else:
                err = result.stderr.strip()[:150] or "Command failed"
        except FileNotFoundError:
            err = f"CLI not found: {self.cli_binary}"
        except subprocess.TimeoutExpired:
            err = "Timed out fetching albums"
        except Exception as e:
            err = str(e)

        GLib.idle_add(self._populate, albums, err)

    def _parse_albums(self, stdout):
        """Parse CLI output into [{'name':..., 'count':...}, ...].
        Handles JSON; falls back to one name per line."""
        try:
            data = json.loads(stdout)
            items = data.get("albums", data) if isinstance(data, dict) else data
            out = []
            for a in items:
                name = a.get("name") or a.get("Name") or str(a)
                count = a.get("count") or a.get("fileCount") or a.get("file_count")
                out.append({"name": name, "count": count})
            return out
        except (json.JSONDecodeError, TypeError, AttributeError):
            return [{"name": line.strip(), "count": None}
                    for line in stdout.splitlines() if line.strip()]

    # ------------- Populate / handlers -------------

    def _populate(self, albums, error):
        if error and not albums:
            self._status.set_title("Couldn't load albums")
            self._status.set_description(error)
            self._stack.set_visible_child_name("empty")
            return
        if not albums:
            self._status.set_title("No albums found")
            self._status.set_description(f"Ran: {' '.join(self._cmd_list_albums())}")
            self._stack.set_visible_child_name("empty")
            return

        # Clear old tiles on reload
        while True:
            child = self._flow.get_first_child()
            if child is None:
                break
            self._flow.remove(child)
            self._flow.remove(child.get_child()) if False else None

        for album in albums:
            self._flow.append(self._make_album_tile(album["name"], album.get("count")))

        self._stack.set_visible_child_name("albums")

    def _on_album_clicked(self, button, album_name):
        """Fetch files inside the clicked album and toast the result."""
        print(f"[Albums] Opening album: {album_name}")
        self.emit("album-opened", album_name)

        def fetch():
            count, err = 0, ""
            try:
                r = subprocess.run(
                    self._cmd_list_album_files(album_name),
                    capture_output=True, text=True, timeout=120,
                )
                if r.returncode == 0:
                    count = len(self._parse_albums(r.stdout))
                else:
                    err = r.stderr.strip()[:150]
            except Exception as e:
                err = str(e)

            msg = err or f"Album '{album_name}': {count} items"
            GLib.idle_add(lambda: self._toast(msg))

        self._toast(f"Opening {album_name}…")
        threading.Thread(target=fetch, daemon=True).start()

    # ------------- Helpers -------------

    def _toast(self, message, timeout=3):
        self._toast_overlay.add_toast(Adw.Toast(title=message, timeout=timeout))

    def refresh(self):
        self._load_albums()
