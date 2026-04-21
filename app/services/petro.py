from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status
from typing import List, Dict, Any, Optional
from sqlalchemy import update, delete, select, func
from sqlalchemy.orm import selectinload

from app.crud import petro as crud_petro
from app.schemas import petro as schema_petro
from app.models.petro import Sale, Purchase, StockMovement, Product, ProductPriceConfig, PurchaseTax, Storage

class PetroleumService:
    
    # --- HELPER : RÉCUPÉRER LA CONFIGURATION DE PRIX (Isolée par Org) ---
    @staticmethod
    async def _get_active_config(db: AsyncSession, product_id: int):
        # On cherche la config 400/225/50 spécifique à cette organisation
        stmt = select(ProductPriceConfig).where(
            ProductPriceConfig.product_id == product_id,
            ProductPriceConfig.organization_id == 1,
            ProductPriceConfig.is_active == True
        )
        config = (await db.execute(stmt)).scalar_one_or_none()
        if not config:
            raise HTTPException(
                status_code=400, 
                detail=f"Configuration PLEX non trouvée pour le produit {product_id} dans votre organisation."
            )
        return config

    # --- 1. LOGIQUE ACHAT (Isolée par Org) ---
    @staticmethod
    async def process_new_purchase(db: AsyncSession, purchase_in: schema_petro.PurchaseCreate, org_id: int):
        """
        SIR -> HUB (ou) HUB -> STATION. 
        Calcule automatiquement les montants selon la config de l'organisation.
        """
        config = await PetroleumService._get_active_config(db, purchase_in.product_id)
        
        try:
            # Application de la manigance (400 + 225)
            price_sir = config.purchase_sir_unit 
            price_tax = config.taxes_unit         
            total = (price_sir + price_tax) * purchase_in.volume

            # 1. Création de l'achat marqué par l'org_id
            new_purchase = Purchase(
                organization_id=org_id,
                product_id=purchase_in.product_id,
                tank_id=purchase_in.tank_id, # Logistique cuve
                volume=purchase_in.volume,
                unit_purchase_price=price_sir,
                unit_taxes=price_tax,
                total_amount=total,
                supplier=purchase_in.supplier
            )
            db.add(new_purchase)
            await db.flush()

            # 2. Ajout automatique de la taxe de l'organisation
            db_tax = PurchaseTax(
                purchase_id=new_purchase.id,
                name=f"Taxes Plex - Org {org_id}",
                amount=(price_tax * purchase_in.volume)
            )
            db.add(db_tax)
            
            # 3. Mouvement de stock IN pour l'organisation
            await crud_petro.create_stock_movement(
                db, 
                product_id=new_purchase.product_id,
                org_id=org_id,
                tank_id=purchase_in.tank_id,
                volume=new_purchase.volume,
                m_type="IN",
                source="purchase",
                source_id=new_purchase.id
            )
            
            await db.commit()

            # Rechargement avec relations pour la réponse API (Fix Greenlet)
            stmt = select(Purchase).where(Purchase.id == new_purchase.id).options(
                selectinload(Purchase.taxes)
            )
            result = await db.execute(stmt)
            return result.scalar_one()

        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=f"Erreur achat org {org_id}: {str(e)}")

    # --- 2. LOGIQUE VENTE (Isolée par Org + Marge 50F) ---
    @staticmethod
    async def process_new_sale(db: AsyncSession, sale_in: schema_petro.SaleCreate, org_id: int):
        config = await PetroleumService._get_active_config(db, sale_in.product_id, org_id)
        
        # Vérification du stock PROPRE à l'organisation
        _, _, current_stock = await crud_petro.get_stock_detail_by_org(db, sale_in.product_id, org_id)
        
        if current_stock < sale_in.volume:
            raise HTTPException(status_code=400, detail=f"Stock insuffisant dans votre organisation ({current_stock} L dispo)")
        
        try:
            total_sale_amount = config.selling_price_unit * sale_in.volume
            total_margin_boss = config.margin_boss_unit * sale_in.volume # Les 50F

            # 1. Création de la vente
            new_sale = Sale(
                organization_id=org_id,
                client_id=sale_in.client_id,
                product_id=sale_in.product_id,
                pump_id=sale_in.pump_id, # Logistique pompe
                volume=sale_in.volume,
                unit_price=config.selling_price_unit,
                total_amount=total_sale_amount,
                margin_boss_total=total_margin_boss,
                status="delivered"
            )
            db.add(new_sale)
            await db.flush()
            
            # 2. Mouvement de stock OUT pour l'organisation
            await crud_petro.create_stock_movement(
                db,
                product_id=new_sale.product_id,
                org_id=org_id,
                volume=new_sale.volume,
                m_type="OUT",
                source="sale",
                source_id=new_sale.id
            )
            
            await db.commit()
            
            stmt = select(Sale).where(Sale.id == new_sale.id).options(
                selectinload(Sale.client), selectinload(Sale.product)
            )
            result = await db.execute(stmt)
            return result.scalar_one()

        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=f"Erreur vente: {str(e)}")
    @staticmethod
    async def update_sale(db: AsyncSession, sale_id: int, org_id: int, obj_in: dict):
        """
        Met à jour une vente et ajuste le stock OUT de l'organisation.
        """
        # 1. Vérifier l'existence et l'org
        sale = await crud_petro.get_item_by_id_secure(db, Sale, sale_id, org_id)
        if not sale:
            raise HTTPException(status_code=404, detail="Vente non trouvée")

        # 2. Récupérer la config prix (675 / 50) de l'org
        config = await PetroleumService._get_active_config(db, sale.product_id, org_id)

        try:
            # 3. Si le volume change, on vérifie le stock de l'org avant d'autoriser
            if "volume" in obj_in:
                new_v = obj_in["volume"]
                diff = new_v - sale.volume
                if diff > 0:
                    _, _, current_stock = await crud_petro.get_stock_detail_by_org(db, sale.product_id, org_id)
                    if current_stock < diff:
                        raise Exception(f"Stock insuffisant pour augmenter la vente (+{diff} L)")
                
                # Mise à jour du mouvement de stock OUT
                await db.execute(update(StockMovement).where(
                    StockMovement.source_id == sale_id,
                    StockMovement.source == "sale",
                    StockMovement.organization_id == org_id
                ).values(volume=new_v))
                
                # Recalcul automatique CA et Marge du Boss (les 50F)
                obj_in["total_amount"] = new_v * config.selling_price_unit
                obj_in["margin_boss_total"] = new_v * config.margin_boss_unit

            # 4. Exécuter l'update final
            return await crud_petro.update_item_secure(db, Sale, sale_id, org_id, obj_in)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))
        
        
    # --- 3. LOGIQUE DASHBOARD (Multi-tenant) ---
    @staticmethod
    async def get_boss_dashboard_stats(db: AsyncSession, org_id: Optional[int] = None):
        """
        Si org_id est fourni : Stats de la station.
        Si org_id est None : Stats globales (Pour le Boss Sevoil).
        """
        # Filtre par organisation si nécessaire
        filters_sm = [StockMovement.organization_id == org_id] if org_id else []
        filters_sale = [Sale.organization_id == org_id] if org_id else []
        filters_tax = [PurchaseTax.purchase_id == Purchase.id, Purchase.organization_id == org_id] if org_id else []

        # Volumes
        in_vol = (await db.execute(select(func.sum(StockMovement.volume)).where(StockMovement.type == "IN", *filters_sm))).scalar() or 0.0
        out_vol = (await db.execute(select(func.sum(StockMovement.volume)).where(StockMovement.type == "OUT", *filters_sm))).scalar() or 0.0
        
        # Financier
        revenue = (await db.execute(select(func.sum(Sale.total_amount)).where(*filters_sale))).scalar() or 0.0
        margin = (await db.execute(select(func.sum(Sale.margin_boss_total)).where(*filters_sale))).scalar() or 0.0
        
        # Produits
        products = await crud_petro.get_products(db)
        stock_report = []
        for prod in products:
            t_in, t_out, current = await crud_petro.get_stock_detail_by_org(db, prod.id, org_id) if org_id else (0,0,0)
            stock_report.append({"product_id": prod.id, "product_name": prod.name, "total_in": t_in, "total_out": t_out, "current_stock": current})
            
        return {
            "total_purchases_volume": in_vol,
            "total_sales_volume": out_vol,
            "total_revenue": revenue,
            "total_taxes_paid": 0.0, # A affiner avec jointure PurchaseTax
            "estimated_margin": margin,
            "stock_levels": stock_report
        }

    # --- 4. ANNULATIONS SÉCURISÉES (Filtre par Org) ---
    @staticmethod
    async def cancel_sale(db: AsyncSession, sale_id: int, org_id: int):
        sale = await crud_petro.get_item_by_id_secure(db, Sale, sale_id, org_id)
        if not sale: raise HTTPException(status_code=404, detail="Vente non trouvée ou accès refusé")
        
        try:
            # Supprimer le mouvement de stock
            await db.execute(delete(StockMovement).where(
                StockMovement.source_id == sale_id, 
                StockMovement.source == "sale",
                StockMovement.organization_id == org_id
            ))
            await db.delete(sale)
            await db.commit()
            return {"message": "Vente annulée, stock restauré"}
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    @staticmethod
    async def cancel_purchase(db: AsyncSession, purchase_id: int, org_id: int):
        purchase = await crud_petro.get_item_by_id_secure(db, Purchase, purchase_id, org_id)
        if not purchase: raise HTTPException(status_code=404, detail="Achat non trouvé")
        
        try:
            await db.execute(delete(PurchaseTax).where(PurchaseTax.purchase_id == purchase_id))
            await db.execute(delete(StockMovement).where(
                StockMovement.source_id == purchase_id, 
                StockMovement.source == "purchase",
                StockMovement.organization_id == org_id
            ))
            await db.delete(purchase)
            await db.commit()
            return {"message": "Achat annulé, stock déduit"}
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=str(e))

    # --- 5. MISES À JOUR SÉCURISÉES ---
    @staticmethod
    async def update_purchase(db: AsyncSession, purchase_id: int, org_id: int, obj_in: dict):
        purchase = await crud_petro.get_item_by_id_secure(db, Purchase, purchase_id, org_id)
        if not purchase: raise HTTPException(status_code=404, detail="Achat non trouvé")

        config = await PetroleumService._get_active_config(db, obj_in.get("product_id", purchase.product_id), org_id)
        
        try:
            if "volume" in obj_in or "product_id" in obj_in:
                new_v = obj_in.get("volume", purchase.volume)
                # Sync StockMovement
                await db.execute(update(StockMovement).where(
                    StockMovement.source_id == purchase_id,
                    StockMovement.source == "purchase",
                    StockMovement.organization_id == org_id
                ).values(volume=new_v, product_id=obj_in.get("product_id", purchase.product_id)))
                
                obj_in["total_amount"] = new_v * (config.purchase_sir_unit + config.taxes_unit)

            return await crud_petro.update_item_secure(db, Purchase, purchase_id, org_id, obj_in)
        except Exception as e:
            await db.rollback()
            raise HTTPException(status_code=400, detail=f"Erreur update: {str(e)}")