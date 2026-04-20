# app/plugins/advanced_audit/examples.py

"""
Ce fichier contient des exemples d'utilisation de l'auditeur de table.
Pour utiliser ces exemples, importez-les dans votre fichier d'initialisation de l'application.
"""

from .audit_table import TableAuditor
from app.core.db import get_db
from sqlalchemy.orm import Session
from app.models.user import User
from app.models.document import Document
from app.models.workflow import WorkflowInstance

def register_audited_models(auditor: TableAuditor):
    """
    Enregistre les modèles qui doivent être audités automatiquement.
    
    Args:
        auditor: Instance de TableAuditor
    """
    # Audit de la table des utilisateurs avec exclusion des champs sensibles
    auditor.register_model(
        model=User,
        excluded_columns=['password_hash', 'refresh_token', 'reset_token'],
        resource_name='user'
    )
    
    # Audit de la table des documents
    auditor.register_model(
        model=Document,
        resource_name='document'
    )
    
    # Audit des workflows avec inclusion de champs spécifiques uniquement
    auditor.register_model(
        model=WorkflowInstance,
        included_columns=['id', 'workflow_id', 'target_id', 'current_state', 'is_completed'],
        resource_name='workflow'
    )

def example_manual_audit(db: Session, auditor: TableAuditor):
    """
    Exemple d'utilisation manuelle de l'auditeur.
    
    Args:
        db: Session de base de données
        auditor: Instance de TableAuditor
    """
    # Exemple d'audit manuel pour une action de visualisation
    user_id = 1  # ID de l'utilisateur qui effectue l'action
    document_id = 123  # ID du document consulté
    
    auditor.manually_log(
        action='VIEW',
        resource='document',
        object_id=document_id,
        data={
            'viewed_at': '2025-03-27T15:30:00',
            'access_method': 'web_interface'
        },
        user_id=user_id
    )
    
    # Exemple d'audit manuel pour une exportation
    auditor.manually_log(
        action='EXPORT',
        resource='report',
        object_id='quarterly_report_2025_Q1',
        data={
            'format': 'PDF',
            'pages': 42,
            'exported_at': '2025-03-27T16:05:00'
        },
        user_id=user_id
    )

def example_query_specific_audit_logs(db: Session):
    """
    Exemple de requêtes pour récupérer des logs d'audit spécifiques.
    
    Args:
        db: Session de base de données
    """
    from .models import AuditLog
    from sqlalchemy import and_, or_
    
    # Récupérer tous les logs liés aux documents
    document_logs = db.query(AuditLog).filter(
        AuditLog.resource == 'document'
    ).all()
    
    # Récupérer tous les logs de création pour un utilisateur spécifique
    user_creation_logs = db.query(AuditLog).filter(
        and_(
            AuditLog.action == 'CREATE',
            AuditLog.user_id == 1
        )
    ).all()
    
    # Récupérer tous les logs d'un objet spécifique (nécessite une recherche dans le champ details)
    # Note: Ceci est un exemple simplifié, dans un environnement de production, utilisez JSONField si disponible
    target_id = 123
    specific_object_logs = db.query(AuditLog).filter(
        AuditLog.details.contains(f'"id": {target_id}')
    ).all()
    
    return {
        'document_logs': document_logs,
        'user_creation_logs': user_creation_logs,
        'specific_object_logs': specific_object_logs
    }
