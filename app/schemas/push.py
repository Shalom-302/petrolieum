from pydantic import BaseModel, Field
from typing import Dict, Optional, Any, Union, List


class PushSubscriptionCreate(BaseModel):
    """Schéma pour créer un nouvel abonnement push"""
    subscription: Union[Dict[str, Any], str] = Field(
        ..., 
        description="Les données de subscription push (peut être un objet JSON ou une chaîne JSON)"
    )
    userAgent: Optional[str] = Field(
        None,
        description="User agent du navigateur"
    )
    deviceType: Optional[str] = Field(
        None,
        description="Type d'appareil (mobile, desktop, tablet, etc.)"
    )
    language: Optional[str] = Field(
        None,
        description="Code de langue préférée de l'utilisateur"
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Tags pour la segmentation des notifications"
    )


class PushSubscriptionResponse(BaseModel):
    """Schéma pour la réponse aux opérations d'abonnement push"""
    id: Optional[str] = Field(None, description="Identifiant de l'abonnement push (null si opération d'unsubscribe)")
    isSubscribed: bool = Field(..., description="Indique si l'utilisateur est abonné aux notifications")
    message: str = Field(..., description="Message de statut de l'opération")


class PushSubscriptionStatus(BaseModel):
    """Schéma pour vérifier le statut d'abonnement aux notifications push"""
    isSubscribed: bool = Field(..., description="Indique si l'utilisateur est abonné aux notifications")
