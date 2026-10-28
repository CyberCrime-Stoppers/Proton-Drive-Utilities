if ret == 0:
    msg = "✓ …"
elif self._process is None:          # terminated by Cancel
    msg = "◼ Cancelled"
else:
    msg = f"✗ {verb} failed (exit {ret})"
