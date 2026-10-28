"""
Photos Shared with Me Root Browser — PDUA
===========================
Wraps FileExplorerPage to browse the /photos-shared-with-me drive root.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from ui.function.pup.remote.file_explorer_page import FileExplorerPage


class PhotosSharedWithMePage(FileExplorerPage):
    """Browse /photos-shared-with-me folder."""

    def __init__(self, on_navigate):
        super().__init__(
            root="/photos-shared-with-me",
            title="Photos Shared with Me",
            on_navigate=on_navigate
        )
