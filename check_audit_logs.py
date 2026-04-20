#!/usr/bin/env python3
"""
Script pour vérifier les entrées d'audit récentes
"""
import sys
from sqlalchemy import create_engine, text
from datetime import datetime, timedelta

def main():
    """Affiche les entrées d'audit les plus récentes"""
    try:
        engine = create_engine('postgresql://postgres:postgres@kaapi-db:5432/kaapi')
        conn = engine.connect()
        
        # Récupérer les 20 entrées les plus récentes
        result = conn.execute(text("""
            SELECT id, user_id, action, resource, details, created_at
            FROM audit_logs
            ORDER BY created_at DESC
            LIMIT 20
        """)).fetchall()
        
        if not result:
            print("Aucune entrée d'audit trouvée")
            return 0
        
        print(f"Dernières entrées d'audit ({len(result)} résultats):")
        print("-" * 80)
        for row in result:
            print(f"ID: {row[0]}, User: {row[1]}, Action: {row[2]}, Resource: {row[3]}")
            print(f"Date: {row[5]}")
            print(f"Détails: {row[4]}")
            print("-" * 80)
        
        return 0
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
