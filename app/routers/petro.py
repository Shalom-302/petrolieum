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

router = APIRouter(prefix="/petroleum", tags=["Petroleum Management"])

# --- DÉPENDANCES DE RÔLES ---
require_boss = Depends(require_role("boss"))
require_employee = Depends(require_role("boss", "employee"))
require_station = Depends(require_role("boss", "employee", "station_operator"))

# --- 1. CONFIGURATION DES PRIX (PLEX) ---

@router.post("/price-configs", response_model=schema.PriceConfigRead, dependencies=[require_boss])
async def set_product_price_structure(
    obj_in: schema.PriceConfigCreate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Définit le 400/225/50 pour l'organisation du Boss"""
    # On force l'org_id de l'utilisateur pour éviter les triches
    return await crud_petro.create_price_config(db, obj_in, current_user.organization_id)

@router.get("/price-configs/{product_id}", response_model=schema.PriceConfigRead, dependencies=[require_station])
async def get_current_price_structure(
    product_id: int, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Chaque organisation voit sa propre structure de prix"""
    config = await crud_petro.get_active_price_config(db, product_id, current_user.organization_id)
    if not config:
        raise HTTPException(status_code=404, detail="Prix non configurés pour votre station")
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

@router.post("/purchases", response_model=schema.PurchaseRead, dependencies=[require_employee])
async def create_purchase(
    obj_in: schema.PurchaseCreate, 
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    # La manigance s'applique à l'organisation de l'utilisateur
    return await service.process_new_purchase(db, obj_in, current_user.organization_id)

@router.get("/purchases", response_model=List[schema.PurchaseRead], dependencies=[require_employee])
async def list_purchases(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Liste les achats de l'organisation uniquement"""
    return await crud_petro.get_purchases(db, current_user.organization_id)

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
    return await crud_petro.get_sales(db, current_user.organization_id)

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

@router.get("/stock/status", response_model=List[schema.StockStatus])
async def get_stock_status(
    db: AsyncSession = Depends(get_async_db),
    current_user: User = Depends(get_current_active_user)
):
    """Affiche le stock réel de la station connectée"""
    products = await crud_petro.get_products(db)
    stock_list = []
    for p in products:
        t_in, t_out, current = await crud_petro.get_stock_detail_by_org(db, p.id, current_user.organization_id)
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