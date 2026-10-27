"""
Albums Root Browser — PDUA
===========================
Wraps FileExplorerPage to browse the /albums drive root.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from ui.function.pup.remote.file_explorer_page import FileExplorerPage


class AlbumsPage(FileExplorerPage):
    """Browse /albums folder."""

    def __init__(self, on_navigate):
        super().__init__(
            root="/albums",
            title="Albums",
            on_navigate=on_navigate
        )
