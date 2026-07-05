#!/usr/bin/env python3
"""Proton Drive CLI wrapper for uploading files and folders."""
import subprocess
import shutil
import os
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib


class ProtonDriveUploader:
    """Wraps the proton-drive CLI binary."""

    def __init__(self, binary_path="proton-drive"):
        self.binary = shutil.which(binary_path) or binary_path

    def is_available(self):
        """Check if the proton-drive binary exists on the system."""
        result = subprocess.run(
            [self.binary, "version"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0

    def is_authenticated(self):
        """Check if the user is logged in."""
        result = subprocess.run(
            [self.binary, "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return result.returncode == 0

    def list_remote_folders(self, remote_path="/my-files"):
        """List folders at a given remote path. Returns list of (name, path) tuples."""
        try:
            result = subprocess.run(
                [self.binary, "filesystem", "list", remote_path, "--json"],
                capture_output=False,
                text=True,
                timeout=15
            )
            if result.returncode != 0:
                return []

            import json
            data = json.loads(result.stdout)
            folders = []
            for item in data if isinstance(data, list) else data.get("items", []):
                if item.get("type") == "folder" or item.get("isFolder", False):
                    name = item.get("name", "unknown")
                    path = item.get("path", f"{remote_path}/{name}")
                    folders.append((name, path))
            return folders
        except Exception:
            return [("My Files", "/my-files")]


class UploadProgressDialog(Adw.Window):
    """Shows upload progress with live output from the CLI."""

    def __init__(self, parent_window):
        super().__init__(transient_for=parent_window, modal=True)
        self.set_title("Uploading to Proton Drive")
        self.set_default_size(500, 300)

        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)

        header = Adw.HeaderBar()
        main_box.append(header)

        # Status label
        self.status_label = Gtk.Label(label="Preparing upload...")
        self.status_label.set_margin_top(20)
        self.status_label.set_margin_bottom(10)
        main_box.append(self.status_label)

        # Progress spinner
        self.spinner = Gtk.Spinner()
        self.spinner.set_size_request(48, 48
