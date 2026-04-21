from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete, and_
from typing import List, Optional, Any, Dict
from app.models.petro import (
    Product, Client, Purchase, PurchaseTax, Sale, 
    StockMovement, Storage, ProductPriceConfig, Tank, Pump
)
from app.schemas.petro import (
    ProductCreate, ClientCreate, PurchaseCreate, SaleCreate, 
    PriceConfigCreate, StorageRead, PurchaseTaxCreate, TankBase, PumpBase
)
from sqlalchemy.orm import selectinload
from typing import Tuple 

# --- 0. HELPERS GÉNÉRIQUES SÉCURISÉS (LE VERROU) ---

async def get_item_by_id_secure(db: AsyncSession, model: Any, item_id: int, org_id: int) -> Optional[Any]:
    """Recherche un item par ID en vérifiant qu'il appartient à l'organisation"""
    stmt = select(model).where(and_(model.id == item_id, model.organization_id == org_id))
    result = await db.execute(stmt)
    return result.scalar_one_or_none()

async def update_item_secure(db: AsyncSession, model: Any, item_id: int, org_id: int, obj_in: Dict[str, Any]) -> Optional[Any]:
    """Mise à jour sécurisée (Patch) filtrée par organisation"""
    stmt = update(model).where(and_(model.id == item_id, model.organization_id == org_id)).values(**obj_in)
    await db.execute(stmt)
    await db.commit()
    return await get_item_by_id_secure(db, model, item_id, org_id)

async def delete_item_secure(db: AsyncSession, model: Any, item_id: int, org_id: int) -> bool:
    """Suppression sécurisée filtrée par organisation"""
    db_obj = await get_item_by_id_secure(db, model, item_id, org_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        return True
    return False


# --- 1. CRUD PRODUITS (GLOBAL - SANS ORG_ID) ---

async def create_product(db: AsyncSession, obj_in: ProductCreate) -> Product:
    db_obj = Product(**obj_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_products(db: AsyncSession, skip: int = 0, limit: int = 100) -> List[Product]:
    result = await db.execute(select(Product).offset(skip).limit(limit))
    return result.scalars().all()

async def update_product(db: AsyncSession, product_id: int, obj_in: Dict[str, Any]) -> Optional[Product]:
    stmt = update(Product).where(Product.id == product_id).values(**obj_in)
    await db.execute(stmt)
    await db.commit()
    return await db.get(Product, product_id)

async def delete_product(db: AsyncSession, product_id: int) -> bool:
    db_obj = await db.get(Product, product_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        return True
    return False


# --- 2. CRUD CLIENTS (ISOLÉ PAR ORG) ---

async def create_client(db: AsyncSession, obj_in: ClientCreate, org_id: int) -> Client:
    db_obj = Client(**obj_in.model_dump(), organization_id=org_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_clients(db: AsyncSession, org_id: int, skip: int = 0, limit: int = 100) -> List[Client]:
    stmt = select(Client).where(Client.organization_id == org_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_client(db: AsyncSession, client_id: int, org_id: int, obj_in: Dict[str, Any]) -> Optional[Client]:
    return await update_item_secure(db, Client, client_id, org_id, obj_in)

async def delete_client(db: AsyncSession, client_id: int, org_id: int) -> bool:
    return await delete_item_secure(db, Client, client_id, org_id)


# --- 3. CRUD ACHATS (PURCHASES - ISOLÉ PAR ORG) ---

async def create_purchase(db: AsyncSession, obj_in: PurchaseCreate, org_id: int) -> Purchase:
    # On exclut les taxes du model_dump pour les gérer manuellement
    purchase_data = obj_in.model_dump(exclude={"taxes"})
    db_obj = Purchase(**purchase_data, organization_id=org_id)
    db.add(db_obj)
    await db.flush() 

    for tax_in in obj_in.taxes:
        db_tax = PurchaseTax(purchase_id=db_obj.id, name=tax_in.name, amount=tax_in.amount)
        db.add(db_tax)
    
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_purchases(db: AsyncSession, org_id: int, skip: int = 0, limit: int = 100) -> List[Purchase]:
    stmt = select(Purchase).where(Purchase.organization_id == org_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_purchase(db: AsyncSession, purchase_id: int, org_id: int, obj_in: Dict[str, Any]) -> Optional[Purchase]:
    return await update_item_secure(db, Purchase, purchase_id, org_id, obj_in)

async def delete_purchase(db: AsyncSession, purchase_id: int, org_id: int) -> bool:
    return await delete_item_secure(db, Purchase, purchase_id, org_id)


# --- 4. CRUD CONFIG PRIX (PLEX - ISOLÉ PAR ORG) ---

async def create_price_config(db: AsyncSession, obj_in: PriceConfigCreate, org_id: int) -> ProductPriceConfig:
    # Désactiver l'ancienne config pour cette org
    await db.execute(
        update(ProductPriceConfig)
        .where(and_(ProductPriceConfig.product_id == obj_in.product_id, ProductPriceConfig.organization_id == org_id))
        .values(is_active=False)
    )
    db_obj = ProductPriceConfig(**obj_in.model_dump(), organization_id=org_id, is_active=True)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_active_price_config(db: AsyncSession, product_id: int, org_id: int) -> Optional[ProductPriceConfig]:
    result = await db.execute(
        select(ProductPriceConfig).where(and_(
            ProductPriceConfig.product_id == product_id,
            ProductPriceConfig.organization_id == org_id,
            ProductPriceConfig.is_active == True
        ))
    )
    return result.scalar_one_or_none()


# --- 5. CRUD VENTES (SALES - ISOLÉ PAR ORG) ---

async def create_sale(db: AsyncSession, obj_in: SaleCreate, org_id: int) -> Sale:
    db_obj = Sale(**obj_in.model_dump(), organization_id=org_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_sales(db: AsyncSession, org_id: int, skip: int = 0, limit: int = 100) -> List[Sale]:
    stmt = select(Sale).where(Sale.organization_id == org_id).offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_sale(db: AsyncSession, sale_id: int, org_id: int, obj_in: Dict[str, Any]) -> Optional[Sale]:
    return await update_item_secure(db, Sale, sale_id, org_id, obj_in)

async def delete_sale(db: AsyncSession, sale_id: int, org_id: int) -> bool:
    return await delete_item_secure(db, Sale, sale_id, org_id)


# --- 6. CRUD STOCK MOVEMENTS & LOGISTIQUE (ISOLÉ PAR ORG) ---

# app/crud/petro.py

async def create_stock_movement(
    db: AsyncSession, 
    product_id: int, 
    org_id: int, 
    volume: float, 
    m_type: str, 
    source: str, 
    source_id: int,
    tank_id: Optional[int] = None  # <--- AJOUTE CETTE LIGNE
) -> StockMovement:
    """
    Enregistre un mouvement de stock (IN/OUT) rattaché à une organisation
    et optionnellement à une cuve spécifique.
    """
    db_obj = StockMovement(
        product_id=product_id,
        organization_id=org_id,
        tank_id=tank_id, # <--- AJOUTE CETTE LIGNE
        type=m_type,
        volume=volume,
        source=source,
        source_id=source_id
    )
    db.add(db_obj)
    # Note: On laisse le Service faire le commit final pour l'atomicité
    return db_obj

from typing import Tuple # Ajoute cet import en haut

async def get_stock_detail_by_org(
    db: AsyncSession, 
    product_id: int, 
    org_id: int
) -> Tuple[float, float, float]: # <--- ON DIT EXPLICITEMENT QUE C'EST UN TUPLE DE 3 CHIFFRES
    """Calcule In, Out et Current pour une Org précise"""
    base_filter = and_(StockMovement.product_id == product_id, StockMovement.organization_id == org_id)
    
    # Récupération IN
    res_in = await db.execute(
        select(func.sum(StockMovement.volume))
        .where(and_(base_filter, StockMovement.type == "IN"))
    )
    total_in = float(res_in.scalar() or 0.0) # On force le type float
    
    # Récupération OUT
    res_out = await db.execute(
        select(func.sum(StockMovement.volume))
        .where(and_(base_filter, StockMovement.type == "OUT"))
    )
    total_out = float(res_out.scalar() or 0.0) # On force le type float
    
    return total_in, total_out, (total_in - total_out)

# --- 7. CRUD LOGISTIQUE (STORAGE) ---

async def get_storage_by_id(db: AsyncSession, storage_id: int, org_id: int) -> Optional[Storage]:
    return await get_item_by_id_secure(db, Storage, storage_id, org_id)

async def update_storage(db: AsyncSession, storage_id: int, org_id: int, obj_in: Dict[str, Any]) -> Optional[Storage]:
    """Modifier les détails de l'entrepôt (GESTOCI)"""
    return await update_item_secure(db, Storage, storage_id, org_id, obj_in)

async def delete_storage(db: AsyncSession, storage_id: int, org_id: int) -> bool:
    """Supprimer une ligne de stockage"""
    return await delete_item_secure(db, Storage, storage_id, org_id)


# --- 8. CRUD TAXES (PURCHASE TAX) ---

async def get_tax_by_id(db: AsyncSession, tax_id: int, org_id: int) -> Optional[PurchaseTax]:
    return await get_item_by_id_secure(db, PurchaseTax, tax_id, org_id)

async def update_tax(db: AsyncSession, tax_id: int, org_id: int, obj_in: Dict[str, Any]) -> Optional[PurchaseTax]:
    """Rectifier un montant de taxe précis"""
    return await update_item_secure(db, PurchaseTax, tax_id, org_id, obj_in)

async def delete_tax(db: AsyncSession, tax_id: int, org_id: int) -> bool:
    """Supprimer une taxe spécifique"""
    return await delete_item_secure(db, PurchaseTax, tax_id, org_id)


# --- 9. CRUD CUVES (TANKS) ---

async def create_tank(db: AsyncSession, obj_in: TankBase, org_id: int) -> Tank:
    db_obj = Tank(**obj_in.model_dump(), organization_id=org_id)
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_tanks(db: AsyncSession, org_id: int) -> List[Tank]:
    """Récupère les cuves de l'org avec leurs pompes rattachées"""
    stmt = select(Tank).where(Tank.organization_id == org_id).options(selectinload(Tank.pumps))
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_tank(db: AsyncSession, tank_id: int, org_id: int, obj_in: dict) -> Optional[Tank]:
    return await update_item_secure(db, Tank, tank_id, org_id, obj_in)

async def delete_tank(db: AsyncSession, tank_id: int, org_id: int) -> bool:
    return await delete_item_secure(db, Tank, tank_id, org_id)


# --- 10. CRUD POMPES (PUMPS) ---

async def create_pump(db: AsyncSession, obj_in: PumpBase) -> Pump:
    db_obj = Pump(**obj_in.model_dump())
    db.add(db_obj)
    await db.commit()
    await db.refresh(db_obj)
    return db_obj

async def get_pumps_by_org(db: AsyncSession, org_id: int) -> List[Pump]:
    """Récupère toutes les pompes d'une organisation via ses cuves"""
    stmt = select(Pump).join(Tank).where(Tank.organization_id == org_id)
    result = await db.execute(stmt)
    return result.scalars().all()

async def update_pump(db: AsyncSession, pump_id: int, obj_in: dict) -> Optional[Pump]:
    # Ici l'update est simple car l'ID est unique
    stmt = update(Pump).where(Pump.id == pump_id).values(**obj_in)
    await db.execute(stmt)
    await db.commit()
    return await db.get(Pump, pump_id)

async def delete_pump(db: AsyncSession, pump_id: int) -> bool:
    db_obj = await db.get(Pump, pump_id)
    if db_obj:
        await db.delete(db_obj)
        await db.commit()
        return True
    return False


# --- FIX DES ACHATS ---
async def get_purchases_by_org(db: AsyncSession, org_id: int) -> List[Purchase]:
    # On force le chargement des TAXES et du STORAGE
    stmt = (
        select(Purchase)
        .where(Purchase.organization_id == org_id)
        .options(
            selectinload(Purchase.taxes),
            selectinload(Purchase.storage)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()

# --- FIX DES VENTES ---
async def get_sales_by_org(db: AsyncSession, org_id: int) -> List[Sale]:
    # On force le chargement du CLIENT et du PRODUIT
    stmt = (
        select(Sale)
        .where(Sale.organization_id == org_id)
        .options(
            selectinload(Sale.client),
            selectinload(Sale.product)
        )
    )
    result = await db.execute(stmt)
    return result.scalars().all()