from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload 
from typing import List, Optional

from app.core.db import get_async_db
from app.schemas import petro as schema
from app.services.petro import PetroleumService as service
from app.crud import petro as crud_petro
from app.models.petro import Sale, Purchase, Product,Client, ProductPriceConfig


# Sécurité et Authentification
from app.plugins.advanced_auth.utils.security import require_role, get_current_active_user
from app.plugins.advanced_auth.models.user import User

router = APIRouter(tags=["Petroleum Management"])
# --- DÉPENDANCES DE RÔLES ---
require_boss = Depends(require_role("boss"))
require_employee = Depends(require_role("boss", "employee"))
require_station = Depends(require_role("boss", "employee", "station_operator"))

# --- 1. CONFIGURATION DES PRIX (PLEX) ---

@router.post("/price-configs", response_model=schema.PriceConfigRead, dependencies=[require_boss])
async def create_price_config(obj_in: schema.PriceConfigCreate, db: AsyncSession = Depends(get_async_db)):
    # On force l'org_id à 1 (Le HUB) car c'est la config de référence
    return await crud_petro.create_price_config(db, obj_in, 1)

# TOUT LE MONDE peut VOIR les prix (require_station)
@router.get("/price-configs/{product_id}", response_model=schema.PriceConfigRead, dependencies=[require_boss])
async def get_price_config(product_id: int, db: AsyncSession = Depends(get_async_db)):
    # On renvoie toujours la config du HUB (ID 1)
    config = await crud_petro.get_active_price_config(db, product_id, 1)
    if not config: raise HTTPException(status_code=404, detail="Prix non configurés au siège.")
    return config

@router.patch("/price-configs/{id}", response_model=schema.PriceConfigRead, dependencies=[require_boss])
async def update_price_config(
    id: int, obj_in: dict, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await crud_petro.update_item_secure(db, ProductPriceConfig, id, current_user.organization_id, obj_in)

@router.delete("/price-configs/{id}", dependencies=[require_boss])
async def delete_price_config(
    id: int, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await crud_petro.delete_item_secure(db, ProductPriceConfig, id, current_user.organization_id)



# --- 2. PRODUITS (RÉFÉRENTIEL GLOBAL) ---

@router.post("/products", response_model=schema.ProductRead, dependencies=[require_employee])
async def create_product(obj_in: schema.ProductCreate, db: AsyncSession = Depends(get_async_db)):
    return await crud_petro.create_product(db, obj_in)

@router.get("/products", response_model=List[schema.ProductRead], dependencies=[require_station])
async def list_products(db: AsyncSession = Depends(get_async_db)):
    return await crud_petro.get_products(db)

@router.patch("/products/{id}", response_model=schema.ProductRead, dependencies=[require_employee])
async def update_product(id: int, obj_in: dict, db: AsyncSession = Depends(get_async_db)):
    return await crud_petro.update_product(db, id, obj_in)

@router.delete("/products/{id}", dependencies=[require_employee])
async def delete_product(id: int, db: AsyncSession = Depends(get_async_db)):
    return await crud_petro.delete_product(db, id)
# --- 3. CLIENTS (ISOLÉS PAR ORGANISATION) ---

@router.post("/clients", response_model=schema.ClientRead, dependencies=[require_employee])
async def create_client(
    obj_in: schema.ClientCreate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await crud_petro.create_client(db, obj_in, current_user.organization_id)

@router.get("/clients", response_model=List[schema.ClientRead], dependencies=[require_station])
async def list_clients(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """L'opérateur ne voit que les clients rattachés à son organisation"""
    return await crud_petro.get_clients(db, current_user.organization_id)

@router.patch("/clients/{id}", response_model=schema.ClientRead, dependencies=[require_employee])
async def update_client(
    id: int, obj_in: dict, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await crud_petro.update_client(db, id, current_user.organization_id, obj_in)

@router.delete("/clients/{id}", dependencies=[require_employee])
async def delete_client(
    id: int, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await crud_petro.delete_client(db, id, current_user.organization_id)

# --- 4. ACHATS (SIR / LOGISTIQUE) ---

@router.post("/purchases", response_model=schema.PurchaseRead, dependencies=[require_station])
async def create_purchase(
    obj_in: schema.PurchaseCreate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Bob enregistre son chargement, les prix du Boss s'appliquent automatiquement"""
    return await service.process_new_purchase(db, obj_in, current_user.organization_id)

@router.get("/purchases", response_model=List[schema.PurchaseRead], dependencies=[require_employee])
async def list_purchases(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Liste les achats de l'organisation uniquement"""
    return await crud_petro.get_purchases_by_org(db, current_user.organization_id)

@router.patch("/purchases/{id}", response_model=schema.PurchaseRead, dependencies=[require_employee])
async def update_purchase(
    id: int, 
    obj_in: dict, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await service.update_purchase(db, id, current_user.organization_id, obj_in)

@router.delete("/purchases/{id}", dependencies=[require_boss])
async def delete_purchase(
    id: int, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await service.cancel_purchase(db, id, current_user.organization_id)


# --- 5. VENTES (ISOLÉES PAR ORGANISATION) ---

@router.post("/sales", response_model=schema.SaleRead, dependencies=[require_station])
async def create_sale(
    obj_in: schema.SaleCreate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await service.process_new_sale(db, obj_in, current_user.organization_id)

@router.get("/sales", response_model=List[schema.SaleRead], dependencies=[require_station])
async def list_sales(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Chaque station ne voit que SES propres ventes"""
    return await crud_petro.get_sales_by_org(db, current_user.organization_id)

@router.patch("/sales/{id}", response_model=schema.SaleRead, dependencies=[require_station])
async def update_sale(
    id: int, obj_in: dict, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    # Utilise le service car un changement de volume de vente impacte le stock OUT
    return await service.update_sale(db, id, current_user.organization_id, obj_in)

@router.delete("/sales/{id}", dependencies=[require_employee])
async def cancel_sale(
    id: int, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    return await service.cancel_sale(db, id, current_user.organization_id)


# --- 6. STOCK & DASHBOARD (MULTI-TENANT) ---

@router.get("/stock/status", response_model=List[schema.StockStatus], dependencies=[require_station])
async def get_stock_status(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Affiche le stock réel de la station connectée"""
    products = await crud_petro.get_products(db)
    stock_list = []
    
    for p in products:
        # --- FIX PYLANCE ICI ---
        # 1. On attend (await) d'abord le résultat complet (le tuple)
        result = await crud_petro.get_stock_detail_by_org(db, p.id, current_user.organization_id)
        
        # 2. On déballe le tuple après l'avoir récupéré
        t_in, t_out, current = result
        # -----------------------

        stock_list.append({
            "product_id": p.id, 
            "product_name": p.name,
            "total_in": t_in, 
            "total_out": t_out, 
            "current_stock": current
        })
    return stock_list

@router.get("/dashboard/summary", response_model=schema.DashboardStats)
async def get_dashboard_summary(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """
    Dashboard intelligent :
    - Si l'utilisateur est Boss : Stats globales (ou de son org)
    - Si l'utilisateur est Station : Uniquement ses stats
    """
    # Si le Boss veut tout voir, on pourrait passer None, 
    # mais ici on filtre par l'org de l'utilisateur pour la sécurité
    return await service.get_boss_dashboard_stats(db, current_user.organization_id)


# --- 7. MODULE LOGISTIQUE (CUVES & POMPES) ---

# --- CUVES (TANKS) ---

@router.get("/tanks", response_model=List[schema.TankRead], dependencies=[require_station])
async def list_my_tanks(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Liste les cuves de l'organisation connectée"""
    return await crud_petro.get_tanks(db, current_user.organization_id)

@router.post("/tanks", response_model=schema.TankRead, dependencies=[require_employee])
async def create_tank(
    obj_in: schema.TankBase, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Création d'une cuve par le siège pour une station"""
    return await crud_petro.create_tank(db, obj_in, current_user.organization_id)

@router.patch("/tanks/{id}", response_model=schema.TankRead, dependencies=[require_employee])
async def update_tank(
    id: int, obj_in: dict, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Modifier les infos d'une cuve (ex: changer la capacité)"""
    return await crud_petro.update_tank(db, id, current_user.organization_id, obj_in)

@router.delete("/tanks/{id}", dependencies=[require_employee])
async def delete_tank(
    id: int, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Supprimer une cuve"""
    return await crud_petro.delete_tank(db, id, current_user.organization_id)


# --- POMPES (PUMPS) ---

@router.get("/pumps", response_model=List[schema.PumpRead], dependencies=[require_station])
async def list_my_pumps(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Bob voit ses pompes pour faire ses ventes"""
    return await crud_petro.get_pumps_by_org(db, current_user.organization_id)

@router.post("/pumps", response_model=schema.PumpRead, dependencies=[require_employee])
async def create_pump(
    obj_in: schema.PumpBase, 
    db: AsyncSession = Depends(get_async_db)
):
    """Ajouter une nouvelle pompe à une cuve"""
    return await crud_petro.create_pump(db, obj_in)

@router.patch("/pumps/{id}", response_model=schema.PumpRead, dependencies=[require_employee])
async def update_pump(
    id: int, obj_in: dict, 
    db: AsyncSession = Depends(get_async_db)
):
    """Mettre à jour les infos d'une pompe (ex: nom)"""
    return await crud_petro.update_pump(db, id, obj_in)

@router.delete("/pumps/{id}", dependencies=[require_employee])
async def delete_pump(
    id: int, 
    db: AsyncSession = Depends(get_async_db)
):
    """Supprimer une pompe"""
    return await crud_petro.delete_pump(db, id)