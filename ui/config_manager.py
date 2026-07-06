import json
import os

CONFIG_PATH = os.path.expanduser("~/.config/auth2portal/config.json")

DEFAULT_CONFIG = {
    "proton_drive_remote": "/my-files/Uploaded",
    "local_source_documents": "~/Documents",
    "local_source_pictures": "~/Pictures",
    "cli_binary": "./proton-drive",
}


class ConfigManager:
    @staticmethod
    def load():
        """Load config from disk, falling back to defaults."""
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r") as f:
                    config = json.load(f)
                # Merge with defaults so missing keys still have values
                merged = DEFAULT_CONFIG.copy()
                merged.update(config)
                return merged
        except Exception as e:
            print(f"[Config] Error loading: {e}")
        return DEFAULT_CONFIG.copy()

    @staticmethod
    def save(config):
        """Save config to disk."""
        try:
            os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
            with open(CONFIG_PATH, "w") as f:
                json.dump(config, f, indent=4)
            print(f"[Config] Saved to {CONFIG_PATH}")
            return True
        except Exception as e:
            print(f"[Config] Error saving: {e}")
            return False
