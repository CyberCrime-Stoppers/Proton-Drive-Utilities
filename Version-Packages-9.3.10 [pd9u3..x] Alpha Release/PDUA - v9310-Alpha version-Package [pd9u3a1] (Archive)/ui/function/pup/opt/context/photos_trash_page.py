"""
Photos Trash Root Browser — PDUA
===========================
Wraps FileExplorerPage to browse the /photos-trash drive root.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from ui.function.pup.remote.file_explorer_page import FileExplorerPage


class PhotosTrashPage(FileExplorerPage):
    """Browse /photos-trash folder."""

    def __init__(self, on_navigate):
        super().__init__(
            root="/photos-trash",
            title="Photos Trash",
            on_navigate=on_navigate
        )
