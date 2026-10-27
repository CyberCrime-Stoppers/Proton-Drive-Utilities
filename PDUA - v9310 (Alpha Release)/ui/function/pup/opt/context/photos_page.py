"""
Photos Root Browser — PDUA
===========================
Wraps FileExplorerPage to browse the /photos drive root.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from ui.function.pup.remote.file_explorer_page import FileExplorerPage


class PhotosPage(FileExplorerPage):
    """Browse /photos folder."""

    def __init__(self, on_navigate):
        super().__init__(
            root="/photos",
            title="Photos",
            on_navigate=on_navigate
        )
