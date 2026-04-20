"""API Gateway plugin implementation."""

from fastapi import APIRouter, Depends, HTTPException, Request
from app.core.plugins import PluginInfo, BasePlugin
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)

class ApiGatewayPlugin(BasePlugin):
    """Plugin pour l'API Gateway."""
    
    def __init__(self):
        super().__init__(
            name="api_gateway",
            description="API Gateway for external integrations",
            version="0.1.0",
            dependencies=[]
        )
        self.router = APIRouter(prefix="/plugins/api_gateway", tags=["API Gateway"])
        
        # Ajouter des routes ici
        self.router.add_api_route("/health", self.health_check, methods=["GET"])
        self.router.add_api_route("/info", self.get_info, methods=["GET"])
    
    async def health_check(self):
        """Point de terminaison simple pour vérifier la santé du plugin."""
        return {"status": "ok", "plugin": self.name}
    
    async def get_info(self) -> Dict[str, Any]:
        """Retourne des informations sur le plugin."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version
        }

# Créer l'instance du plugin
plugin = ApiGatewayPlugin()

def initialize_plugin(app=None, api_title=None, api_description=None, api_version=None) -> bool:
    """Initialise le plugin.
    
    Args:
        app: L'application FastAPI principale
        api_title: Titre de l'API
        api_description: Description de l'API
        api_version: Version de l'API
    """
    try:
        logger.info(f"Initializing {plugin.name} plugin")
        logger.info(f"API title: {api_title}")
        logger.info(f"API description: {api_description}")
        logger.info(f"API version: {api_version}")
        
        # Stocker les informations d'API
        plugin.api_title = api_title
        plugin.api_description = api_description
        plugin.api_version = api_version
        
        # Intégrer le routeur avec l'app principale si fournie
        if app:
            app.include_router(plugin.router)
            
        return True
    except Exception as e:
        logger.error(f"Error initializing {plugin.name} plugin: {str(e)}")
        return False

def get_plugin_info() -> PluginInfo:
    """Retourne les informations sur le plugin."""
    return PluginInfo(
        name=plugin.name,
        description=plugin.description,
        version=plugin.version,
        router_path="/plugins/api_gateway"
    )

def get_router() -> APIRouter:
    """Retourne le routeur API du plugin."""
    return plugin.router

api_gateway_router = get_router()