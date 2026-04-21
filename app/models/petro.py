from typing import List, Optional
import datetime
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Boolean, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.db import Base

# --- 0. MULTI-TENANCY (ORGANISATIONS) ---

class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    org_type: Mapped[str] = mapped_column(String(50), nullable=False) 
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # Relations
    tanks: Mapped[List["Tank"]] = relationship(back_populates="organization")
    clients: Mapped[List["Client"]] = relationship(back_populates="organization")

    def __repr__(self) -> str:
        return f"<Organization(id={self.id}, name='{self.name}')>"


# --- 1. RÉFÉRENTIELS (PRODUITS & CLIENTS) ---

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    unit: Mapped[str] = mapped_column(String(50), default="Litre")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

class Client(Base):
    __tablename__ = "clients"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), index=True, nullable=False)
    client_type: Mapped[str] = mapped_column(String(100))
    country: Mapped[str] = mapped_column(String(100), default="Ivory Coast")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # Relations
    organization: Mapped["Organization"] = relationship(back_populates="clients")
    sales: Mapped[List["Sale"]] = relationship(back_populates="client")


# --- 2. ASSETS LOGISTIQUES (STATIONS / DEPOTS) ---

class Tank(Base):
    __tablename__ = "tanks"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100))
    capacity: Mapped[float] = mapped_column(Float)
    current_volume: Mapped[float] = mapped_column(Float, default=0.0)

    # Relations
    organization: Mapped["Organization"] = relationship(back_populates="tanks")
    product: Mapped["Product"] = relationship()
    pumps: Mapped[List["Pump"]] = relationship(back_populates="tank")

class Pump(Base):
    __tablename__ = "pumps"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    tank_id: Mapped[int] = mapped_column(ForeignKey("tanks.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(100))
    last_index_value: Mapped[float] = mapped_column(Float, default=0.0)

    # Relations
    tank: Mapped["Tank"] = relationship(back_populates="pumps")


# --- 3. CONFIGURATION DES PRIX ---

class ProductPriceConfig(Base):
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

    product: Mapped["Product"] = relationship()


# --- 4. TRANSACTIONS (FLUX) ---

class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    tank_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tanks.id"), nullable=True)
    
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    unit_purchase_price: Mapped[float] = mapped_column(Float) 
    unit_taxes: Mapped[float] = mapped_column(Float)          
    total_amount: Mapped[float] = mapped_column(Float)        
    
    supplier: Mapped[str] = mapped_column(String(100), default="SIR")
    purchase_date: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # Relations (CRITIQUE : Ajout de storage et tank)
    product: Mapped["Product"] = relationship()
    tank: Mapped[Optional["Tank"]] = relationship()
    taxes: Mapped[List["PurchaseTax"]] = relationship(back_populates="purchase", cascade="all, delete-orphan")
    storage: Mapped[Optional["Storage"]] = relationship(back_populates="purchase", uselist=False, cascade="all, delete-orphan")

class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    client_id: Mapped[int] = mapped_column(ForeignKey("clients.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    pump_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pumps.id"), nullable=True)
    
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    unit_price: Mapped[float] = mapped_column(Float)
    total_amount: Mapped[float] = mapped_column(Float)
    margin_boss_total: Mapped[float] = mapped_column(Float) 
    
    status: Mapped[str] = mapped_column(String(50), default="delivered")
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # Relations
    client: Mapped["Client"] = relationship(back_populates="sales")
    product: Mapped["Product"] = relationship()
    pump: Mapped[Optional["Pump"]] = relationship()


# --- 5. LOGISTIQUE & TAXES ---

class PurchaseTax(Base):
    __tablename__ = "purchase_taxes"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)

    # Relation
    purchase: Mapped["Purchase"] = relationship(back_populates="taxes")

class Storage(Base):
    __tablename__ = "storages"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), nullable=False)
    location: Mapped[str] = mapped_column(String(100), default="GESTOCI")
    entry_date: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())
    storage_cost: Mapped[float] = mapped_column(Float, default=0.0)

    # Relation
    purchase: Mapped["Purchase"] = relationship(back_populates="storage")

class StockMovement(Base):
    __tablename__ = "stock_movements"
    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    organization_id: Mapped[int] = mapped_column(ForeignKey("organizations.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    tank_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tanks.id"), nullable=True)
    
    type: Mapped[str] = mapped_column(String(10), nullable=False) # "IN" / "OUT"
    volume: Mapped[float] = mapped_column(Float, nullable=False)
    source: Mapped[str] = mapped_column(String(50), nullable=False) 
    source_id: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, server_default=func.now())

    # Relations
    product: Mapped["Product"] = relationship()
    tank: Mapped[Optional["Tank"]] = relationship()