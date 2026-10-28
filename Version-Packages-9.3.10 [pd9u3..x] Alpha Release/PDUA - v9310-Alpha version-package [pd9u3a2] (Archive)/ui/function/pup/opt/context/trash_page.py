"""
Trash Root Browser — PDUA
===========================
Wraps FileExplorerPage to browse the /trash drive root.

Author: Linus (CyberCrime-Stoppers / CCS)
Version: 9.3.10-Alpha
"""

from ui.function.pup.remote.file_explorer_page import FileExplorerPage


class TrashPage(FileExplorerPage):
    """Browse /trash folder."""

    def __init__(self, on_navigate):
        super().__init__(
            root="/trash",
            title="Trash",
            on_navigate=on_navigate
        )
