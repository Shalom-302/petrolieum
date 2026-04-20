from typing import List, Optional
import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

# --- 0. MULTI-TENANCY (ORGANISATIONS) ---

class Organization(Base):
    """
    Entité centrale pour isoler les données (Multi-tenant).
    Types: 'HUB' (Sevoil), 'STATION', 'MINIER', 'SOUTE'
    """
    __tablename__ = "organizations"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    org_type: Mapped[str] = mapped_column(String(50), nullable=False) 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # Relations
    tanks: Mapped[List["Tank"]] = relationship(back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}', type='{self.org_type}')>"


# --- 1. RÉFÉRENTIELS (PRODUITS & CLIENTS) ---

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="Litre")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

class Client(Base):
    """
    Référentiel des clients. Chaque organisation gère ses propres clients.
    """
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False) # Isolation
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    client_type: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Ivory Coast")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

# --- 2. ASSETS LOGISTIQUES (STATIONS / DEPOTS) ---

class Tank(Base):
    """
    Cuves de stockage appartenant à une organisation.
    """
    __tablename__ = "tanks"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100)) # ex: Cuve Gazole A
    capacity: Mapped[float] = mapped_column(Float) # Capacité max
    current_volume: Mapped[float] = mapped_column(Float, default=0.0)

    organization: Mapped["Organization"] = relationship(back_populates="tanks")
    product: Mapped["Product"] = relationship()
    pumps: Mapped[List["Pump"]] = relationship(back_populates="tank")

class Pump(Base):
    """
    Pompes de distribution rattachées à une cuve.
    """
    __tablename__ = "pumps"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tank_id: Mapped[int] = mapped_column(ForeignKey("tanks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100)) # ex: Pompe 1
    last_index_value: Mapped[float] = mapped_column(Float, default=0.0) # Index compteur

    tank: Mapped["Tank"] = relationship(back_populates="pumps")

# --- 3. CONFIGURATION DES PRIX ---

class ProductPriceConfig(Base):
    """
    Structure des prix par produit et par organisation.
    """
    __tablename__ = "product_price_configs"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    
    purchase_sir_unit: Mapped[float] = mapped_column(Float) # 400
    taxes_unit: Mapped[float] = mapped_column(Float)        # 225
    margin_boss_unit: Mapped[float] = mapped_column(Float)  # 50
    selling_price_unit: Mapped[float] = mapped_column(Float) # 675
    
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

# --- 4. TRANSACTIONS (FLUX) ---

class Purchase(Base):
    """
    Achat de produit (SIR vers SEV OIL, ou SEV OIL vers STATION).
    """
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    tank_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tanks.id")) # Dans quelle cuve on décharge ?
    
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    unit_purchase_price: Mapped[float] = mapped_column(Float) 
    unit_taxes: Mapped[float] = mapped_column(Float)          
    total_amount: Mapped[float] = mapped_column(Float)        
    
    supplier: Mapped[str] = mapped_column(String(100), default="SIR")
    purchase_date: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    taxes: Mapped[List["PurchaseTax"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")

class Sale(Base):
    """
    Vente de produit (Vers client ou via Pompe).
    """
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    pump_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pumps.id")) # Si vente en station
    
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    margin_boss_total: Mapped[float] = mapped_column(Float) # Les 50/L
    
    status: Mapped[str] = mapped_column(String(50), default="delivered")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    client: Mapped["Client"] = relationship()
    product: Mapped["Product"] = relationship()

# --- 5. LOGISTIQUE & TAXES ---

class PurchaseTax(Base):
    __tablename__ = "purchase_taxes"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    purchase: Mapped["Purchase"] = relationship(back_populates="taxes")

class Storage(Base):
    __tablename__ = "storages"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    location: Mapped[str] = mapped_column(String(100), default="GESTOCI")
    entry_date: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    storage_cost: Mapped[float] = mapped_column(Float, default=0.0)
    purchase: Mapped["Purchase"] = relationship()

class StockMovement(Base):
    """
    Le journal de bord universel du stock. Isolé par organisation.
    """
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    tank_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tanks.id"))
    
    type: Mapped[str] = mapped_column(String(10), nullable=False) # "IN" / "OUT"
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False) # "purchase", "sale", "pump_reading"
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    product: Mapped["Product"] = relationship()