#!/usr/bin/env python3
"""
Script Guard Module for PDUA
Validates pinned shell scripts before execution:
- Path containment (no traversal outside allowed directory)
- Existence check
- Executable permission
- SHA-256 integrity hash

USAGE:
    from ui.function.script_guard import validate_script, SCRIPTS_UP_DIR, SCRIPTS_DOWN_DIR

    safe_path = validate_script(SCRIPTS_UP_DIR, "proton-export-home-documents.sh")
"""

import os
import stat
import hashlib
from pathlib import Path


# === DIRECTORIES ===
# Relative to this file's location: ui/function/script_guard.py
BASE_DIR = Path(__file__).resolve().parent.parent.parent  # project root
SCRIPTS_UP_DIR = BASE_DIR / "scripts" / "up"
SCRIPTS_DOWN_DIR = BASE_DIR / "scripts" / "down"


# === HASH TABLES (UPDATE THESE WHEN SCRIPTS CHANGE) ===
# Run: sha256sum scripts/up/*.sh scripts/down/*.sh
# Then paste new hashes here

UPLOAD_SCRIPT_HASHES = {
    "proton-export-home-documents.sh":  "ac9962c9e230d928ff72c5f5bb18ff41c0e278ef7e7d50257ab9b14e76d2a046",
    "proton-export-home-pictures.sh":  "07aa8d1cb10e5f14a1f31cb9af18a45ee8c09639ad4b87982e34c7b590fc2a50",
    "proton-export-home-videos.sh":  "6ff6716ecd73bd1d2feac0795cdca782bcd017b0ee339cb4d3cac5d502c02386",
    "proton-export-home-music.sh":  "e4e9fe168e321a28778dc90fe5f06fe6e20f1b3761c9efbe2818f654c61810a2",
    "proton-export-home-downloads.sh": "e242ca129a166dbb81f1b440448f42284af0744f5d1df279630bd932d054e54d",
}

DOWNLOAD_SCRIPT_HASHES = {
    "proton-import-home-documents.sh":  "ea3243788a9fd4dfc34f3e3963bf0105514b2f126c5cdbad37e8c7522e5304ff",
    "proton-import-home-pictures.sh":  "dc684e1c7013c327dfbf2d98d4804e6f51ff7978f31e9639f80e0ffaa8a9899f",
    "proton-import-home-videos.sh":  "a8bf34dc2fd1e0047c9e28ce1592e4b44c254015fff687c56fe5a87f003b4946",
    "proton-import-home-music.sh":  "f845328a9613c9eb1d4f0fb54c215d85eff39ee15383cb42b1a5153fd6892bc1",
    "proton-import-home-downloads.sh": "f2bd0bfc8ae7bde9b754266bba3a6acede53c9547bdd4005902c75729cbfd119",
}


def validate_script(scripts_dir, script_name):
    """
    Validate a pinned script before execution.

    Args:
        scripts_dir: Path object — either SCRIPTS_UP_DIR or SCRIPTS_DOWN_DIR
        script_name: Filename (e.g. "proton-export-home-documents.sh")

    Returns:
        Absolute path to the validated script (safe to execute)

    Raises:
        ValueError: Path traversal attack, integrity check failed
        FileNotFoundError: Script not found
        PermissionError: Script not executable
    """
    scripts_dir = os.path.abspath(scripts_dir)
    script_path = os.path.join(scripts_dir, script_name)
    abs_path = os.path.abspath(script_path)

    # 1. Path traversal protection using commonpath (CORRECT METHOD)
    try:
        common = os.path.commonpath([abs_path, scripts_dir])
        if common != scripts_dir:
            raise ValueError(f"Script path escapes allowed directory: {script_name}")
    except ValueError:
        raise ValueError(f"Invalid path comparison: {script_name}")

    # 2. Existence check
    if not os.path.isfile(abs_path):
        raise FileNotFoundError(f"Script not found: {script_name}")

    # 3. Executable permission check
    mode = os.stat(abs_path).st_mode
    if not (mode & stat.S_IXUSR):
        raise PermissionError(f"Script not executable: {script_name}")

    # 4. SHA-256 integrity check
    expected_hashes = UPLOAD_SCRIPT_HASHES if "export" in script_name else DOWNLOAD_SCRIPT_HASHES
    expected_hash = expected_hashes.get(script_name)

    if expected_hash is None:
        # If hash table not populated, skip hash check (development mode)
        # In production, this should raise an error instead
        pass
    else:
        with open(abs_path, "rb") as f:
            actual_hash = hashlib.sha256(f.read()).hexdigest()

        if actual_hash != expected_hash:
            raise ValueError(
                f"Script integrity check failed for {script_name}\n"
                f"Expected: {expected_hash}\n"
                f"Actual:   {actual_hash}\n"
                f"Update the hash table in script_guard.py after any script change."
            )

    return abs_path


def update_script_hashes():
    """
    Utility function to print new SHA-256 hashes for all scripts.
    Call this when scripts are modified to update the hash tables above.
    Usage in CLI:
        python3 -m ui.function.script_guard --update
    """
    import argparse

    parser = argparse.ArgumentParser(description="Update script hashes for PDUA")
    parser.add_argument("--up", action="store_true", help="Update upload script hashes")
    parser.add_argument("--down", action="store_true", help="Update download script hashes")
    args = parser.parse_args()

    def compute_hashes(directory, output_var):
        print(f"\n# Hashes for {output_var}:")
        for fname in sorted(os.listdir(directory)):
            if fname.endswith(".sh"):
                fpath = os.path.join(directory, fname)
                with open(fpath, "rb") as f:
                    h = hashlib.sha256(f.read()).hexdigest()
                print(f'    "{fname}":  "{h}",')

    if args.up or not (args.up or args.down):
        compute_hashes(SCRIPTS_UP_DIR, "UPLOAD_SCRIPT_HASHES")
    if args.down or not (args.up or args.down):
        compute_hashes(SCRIPTS_DOWN_DIR, "DOWNLOAD_SCRIPT_HASHES")


if __name__ == "__main__":
    update_script_hashes()
