import asyncio
import uuid
from sqlalchemy.orm import Session, configure_mappers # <--- MODIFIÉ ICI
from sqlalchemy import select # select reste dans sqlalchemy racine
from app.core.db import SessionLocal
# --- IMPORTS MODÈLES (Pour le registre SQLAlchemy) ---
from app.plugins.advanced_auth.models.user import User
from app.plugins.advanced_auth.models.role import Role
from app.models.petro import (
    Organization, Product, Tank, Pump, 
    ProductPriceConfig, Client, Sale, Purchase, StockMovement
)

# Import technique pour éviter l'erreur de registre
try:
    from app.plugins.advanced_auth.models.session import Session as AuthSession
    from app.plugins.advanced_auth.models.mfa import MFAMethod
except:
    pass

from app.plugins.advanced_auth.service import AuthService
from app.plugins.advanced_auth.schemas import UserCreate

async def seed_all():
    configure_mappers() # Force la lecture des relations
    db: Session = SessionLocal()
    auth_service = AuthService(db)
    
    print("--- Démarrage du Seed SEV OIL Multi-tenant ---")

    # 1. CRÉATION DES ORGANISATIONS
    org_configs = [
        {"name": "SEV OIL HUB", "type": "HUB"},
        {"name": "Station Shell Plateau", "type": "STATION"}
    ]
    
    org_map = {}
    for o in org_configs:
        db_org = db.query(Organization).filter(Organization.name == o["name"]).first()
        if not db_org:
            db_org = Organization(name=o["name"], org_type=o["type"])
            db.add(db_org)
            db.commit()
            db.refresh(db_org)
            print(f"Organisation '{o['name']}' créée.")
        org_map[o["type"]] = db_org

    # 2. CRÉATION DES RÔLES
    role_configs = [
        {"name": "boss", "desc": "Propriétaire - Accès total"},
        {"name": "employee", "desc": "Gestionnaire HUB"},
        {"name": "station_operator", "desc": "Gérant Station"}
    ]
    
    role_map = {}
    for r in role_configs:
        db_role = db.query(Role).filter(Role.name == r["name"]).first()
        if not db_role:
            db_role = Role(id=uuid.uuid4(), name=r["name"], description=r["desc"], is_system_role=True)
            db.add(db_role)
            db.commit()
            db.refresh(db_role)
            print(f"Rôle '{r['name']}' créé.")
        role_map[r["name"]] = db_role

    # 3. CRÉATION DES PRODUITS
    product_names = ["Gazole", "Super"]
    prod_map = {}
    for name in product_names:
        db_prod = db.query(Product).filter(Product.name == name).first()
        if not db_prod:
            db_prod = Product(name=name, unit="Litre")
            db.add(db_prod)
            db.commit()
            db.refresh(db_prod)
            print(f"Produit '{name}' créé.")
        prod_map[name] = db_prod

    # 4. CRÉATION DES UTILISATEURS LIÉS AUX ORGS
    users_to_create = [
        {
            "username": "jean_boss", "email": "boss@sevoil.ci", "role": "boss", 
            "org": org_map["HUB"].id, "first": "Jean", "last": "Patron"
        },
        {
            "username": "alice_emp", "email": "employee@sevoil.ci", "role": "employee", 
            "org": org_map["HUB"].id, "first": "Alice", "last": "Gestion"
        },
        {
            "username": "bob_station", "email": "station@sevoil.ci", "role": "station_operator", 
            "org": org_map["STATION"].id, "first": "Bob", "last": "Shell"
        }
    ]

    for u in users_to_create:
        existing = db.query(User).filter(User.email == u["email"]).first()
        if not existing:
            user_data = UserCreate(
                username=u["username"], email=u["email"], first_name=u["first"],
                last_name=u["last"], password="Password123!", role_id=role_map[u["role"]].id
            )
            new_user = await auth_service.register_user(user_data)
            # Liaison manuelle à l'organisation (car le plugin auth ne connaît pas les orgs)
            new_user.organization_id = u["org"]
            db.commit()
            print(f"Utilisateur {u['username']} lié à {u['org']} créé.")

    # 5. CONFIGURATION LOGISTIQUE (Pour la Station Shell)
    # Création d'une Cuve Gazole pour Bob
    station_org_id = org_map["STATION"].id
    db_tank = db.query(Tank).filter(Tank.organization_id == station_org_id).first()
    if not db_tank:
        db_tank = Tank(
            organization_id=station_org_id,
            product_id=prod_map["Gazole"].id,
            name="Cuve Gazole Principal",
            capacity=50000.0,
            current_volume=0.0
        )
        db.add(db_tank)
        db.commit()
        db.refresh(db_tank)
        print("Cuve logistique créée pour la Station.")

        # Création d'une Pompe liée à cette cuve
        db_pump = Pump(tank_id=db_tank.id, name="Pompe N°1", last_index_value=0.0)
        db.add(db_pump)
        db.commit()
        print("Pompe N°1 installée sur la cuve.")

    # 6. CONFIGURATION DES PRIX (La Manigance 400/225/50)
    # Pour le HUB
    hub_config = db.query(ProductPriceConfig).filter(ProductPriceConfig.organization_id == org_map["HUB"].id).first()
    if not hub_config:
        new_config = ProductPriceConfig(
            organization_id=org_map["HUB"].id,
            product_id=prod_map["Gazole"].id,
            purchase_sir_unit=400.0,
            taxes_unit=225.0,
            margin_boss_unit=50.0,
            selling_price_unit=675.0,
            is_active=True
        )
        db.add(new_config)
        db.commit()
        print("Structure de prix 400/225/50 configurée pour le HUB.")

    db.close()
    print("--- Seed Multi-tenant terminé avec succès ---")

if __name__ == "__main__":
    asyncio.run(seed_all())