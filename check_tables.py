#!/usr/bin/env python3
"""
Script pour vérifier les tables existantes dans la base de données
"""
import sys
from sqlalchemy import create_engine, text

def main():
    """Affiche les tables existantes"""
    try:
        engine = create_engine('postgresql://postgres:postgres@kaapi-db:5432/kaapi')
        conn = engine.connect()
        
        # Récupérer la liste des tables
        result = conn.execute(text("""
            SELECT table_name 
            FROM information_schema.tables
            WHERE table_schema='public'
            ORDER BY table_name
        """)).fetchall()
        
        if not result:
            print("Aucune table trouvée")
            return 0
        
        print(f"Tables dans la base de données ({len(result)} tables) :")
        print("-" * 50)
        for row in result:
            print(row[0])
        
        return 0
    except Exception as e:
        print(f"Erreur: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
