import os
import json

class AppConfig:
    """Manages portable application settings and relative path resolution."""
    SETTINGS_FILE = "settings.json"

    def __init__(self, base_dir=None):
        if not base_dir:
            self.base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.base_dir = os.path.abspath(base_dir)

        self.settings_path = os.path.join(self.base_dir, self.SETTINGS_FILE)
        self.settings = {}
        self.settings = self.load_settings()

    def load_settings(self):
        default_settings = {
            "vault_dir": "data_vault",  # Stored as relative to base_dir for portability
            "auto_open_browser": True,
            "port": 8000
        }
        if os.path.exists(self.settings_path):
            try:
                with open(self.settings_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    default_settings.update(data)
            except Exception:
                pass
        else:
            self.save_settings(default_settings)
        return default_settings

    def save_settings(self, new_settings=None):
        if new_settings is not None:
            self.settings.update(new_settings)
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save settings: {e}")

    def get_vault_path(self):
        v = self.settings.get("vault_dir", "data_vault")
        if os.path.isabs(v):
            p = os.path.abspath(v)
        else:
            p = os.path.abspath(os.path.join(self.base_dir, v))
        
        try:
            os.makedirs(p, exist_ok=True)
        except Exception:
            # Fallback to local data_vault if configured external path is inaccessible
            p = os.path.abspath(os.path.join(self.base_dir, "data_vault"))
            os.makedirs(p, exist_ok=True)
        return p

    def set_vault_path(self, new_path):
        # If inside base_dir, save as relative for maximum portability across machines
        abs_new = os.path.abspath(new_path)
        os.makedirs(abs_new, exist_ok=True)
        try:
            rel = os.path.relpath(abs_new, self.base_dir)
            if not rel.startswith(".."):
                self.settings["vault_dir"] = rel
            else:
                self.settings["vault_dir"] = abs_new
        except Exception:
            self.settings["vault_dir"] = abs_new
        self.save_settings()
        return self.get_vault_path()

config = AppConfig()
