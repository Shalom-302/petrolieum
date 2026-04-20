"""
Module pour la gestion des plugins de l'application.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List, Optional

import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH pour résoudre les imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
class PluginInfo(BaseModel):
    """Informations de base sur un plugin."""
    name: str
    description: str
    version: str
    router_path: Optional[str] = None


class BasePlugin:
    """Classe de base pour tous les plugins."""
    
    def __init__(self, name: str, description: str, version: str, dependencies: List[str] = None):
        """
        Initialise un nouveau plugin.
        
        Args:
            name: Nom unique du plugin
            description: Description du plugin
            version: Version du plugin
            dependencies: Liste des plugins dont dépend ce plugin
        """
        self.name = name
        self.description = description
        self.version = version
        self.dependencies = dependencies or []
        self.router = APIRouter()
        
    def initialize(self) -> bool:
        """Initialise le plugin et configure les routes."""
        return True
