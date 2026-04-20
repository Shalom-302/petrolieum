import importlib
import os
from fastapi import APIRouter, HTTPException
from typing import Dict, List
from fastapi import FastAPI
from pydantic import BaseModel
from app.core.config import settings

# Simple plugin state schema
class PluginStateSchema(BaseModel):
    name: str
    enabled: bool = True
    metadata: Dict = {}

# In-memory reference
LOADED_PLUGINS: Dict[str, PluginStateSchema] = {}

def load_plugins_into_app(app: FastAPI, db=None):
    """
    Scan the `app/plugins/` directory for sub-folders each containing `main.py` with `get_router()`.
    A plugin is considered enabled if it's present in the directory.
    """
    plugins_dir = os.path.join("app", "plugins")
    for folder_name in os.listdir(plugins_dir):
        folder_path = os.path.join(plugins_dir, folder_name)
        if not os.path.isdir(folder_path):
            continue

        main_path = os.path.join(folder_path, "main.py")
        if os.path.isfile(main_path):
            module_str = f"app.plugins.{folder_name}.main"
            try:
                plugin_module = importlib.import_module(module_str)
                if hasattr(plugin_module, "get_router"):
                    router = plugin_module.get_router()
                    prefix = f"{settings.API_PREFIX}/{folder_name}"
                    app.include_router(router, prefix=prefix, tags=[folder_name])
                    print(f"✅ Plugin {folder_name} loaded with router {prefix}")
                    
                    # Populate the memory dictionary
                    LOADED_PLUGINS[folder_name] = PluginStateSchema(name=folder_name, enabled=True)
            except Exception as e:
                print(f"⚠️ Failed to load plugin {folder_name}: {e}")

# We create a router to manage plugin states
plugin_manager_router = APIRouter()

@plugin_manager_router.get("/admin/plugins", response_model=List[PluginStateSchema])
def list_plugins():
    """Return all discovered plugins."""
    return list(LOADED_PLUGINS.values())
