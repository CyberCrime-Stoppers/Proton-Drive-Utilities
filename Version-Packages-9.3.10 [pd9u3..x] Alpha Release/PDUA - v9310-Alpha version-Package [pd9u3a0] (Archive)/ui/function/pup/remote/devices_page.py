"""
Devices Root Browser — PDUA
===========================
Wraps FileExplorerPage to browse the /devices drive root.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from ui.function.pup.remote.file_explorer_page import FileExplorerPage


class DevicesPage(FileExplorerPage):
    """Browse /devices folder."""

    def __init__(self, on_navigate):
        super().__init__(
            root="/devices",
            title="Devices",
            on_navigate=on_navigate
        )
