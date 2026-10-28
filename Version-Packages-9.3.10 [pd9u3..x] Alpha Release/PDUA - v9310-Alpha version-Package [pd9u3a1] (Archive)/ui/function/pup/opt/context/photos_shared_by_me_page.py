"""
Photos Shared by Me Root Browser — PDUA
===========================
Wraps FileExplorerPage to browse the /photos-shared-by-me drive root.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from ui.function.pup.remote.file_explorer_page import FileExplorerPage


class PhotosSharedByMePage(FileExplorerPage):
    """Browse /photos-shared-by-me folder."""

    def __init__(self, on_navigate):
        super().__init__(
            root="/photos-shared-by-me",
            title="Photos Shared by Me",
            on_navigate=on_navigate
        )
