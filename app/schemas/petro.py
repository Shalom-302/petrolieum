from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime

# --- CONFIGURATION COMMUNE ---
class PetroBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)

# --- 0. ORGANISATIONS ---
class OrganizationBase(PetroBase):
    name: str
    org_type: str

class OrganizationRead(OrganizationBase):
    id: int
    is_active: bool
    created_at: datetime

# --- 1. PRODUITS ---
class ProductBase(PetroBase):
    name: str = Field(..., example="Gazole")
    unit: str = Field(default="Litre")

class ProductCreate(ProductBase):
    pass

class ProductRead(ProductBase):
    id: int
    created_at: datetime

# --- 2. CUVES & POMPES ---
class PumpBase(PetroBase):
    name: str
    tank_id: int

class PumpRead(PumpBase):
    id: int
    last_index_value: float

class TankBase(PetroBase):
    name: str
    product_id: int
    capacity: float

class TankRead(TankBase):
    id: int
    organization_id: int
    current_volume: float
    pumps: List[PumpRead] = []

# --- 3. CLIENTS ---
class ClientBase(PetroBase):
    name: str
    client_type: str
    country: str = "Ivory Coast"
    is_active: bool = True

class ClientCreate(ClientBase):
    pass # organization_id est injecté par le service

class ClientRead(ClientBase):
    id: int
    organization_id: int
    created_at: datetime

# --- 4. LOGISTIQUE & TAXES (LES PIÈCES MANQUANTES) ---

class PurchaseTaxBase(PetroBase):
    name: str
    amount: float

class PurchaseTaxCreate(PurchaseTaxBase):
    pass

class PurchaseTaxRead(PurchaseTaxBase):
    id: int
    purchase_id: int

class StorageBase(PetroBase):
    location: str = "GESTOCI"
    entry_date: datetime
    storage_cost: float = 0.0

class StorageCreate(StorageBase):
    purchase_id: int

class StorageRead(StorageBase): # <--- VOICI LA CLASSE QUI MANQUAIT
    id: int
    purchase_id: int

# --- 5. ACHATS (SIR) ---
class PurchaseBase(PetroBase):
    product_id: int
    volume: float = Field(..., gt=0)
    supplier: str = "SIR"
    tank_id: Optional[int] = None

class PurchaseCreate(PurchaseBase):
    unit_price: Optional[float] = None 
    taxes: List[PurchaseTaxCreate] = [] # Permet l'ajout de taxes manuelles

class PurchaseRead(PurchaseBase):
    id: int
    organization_id: int
    unit_purchase_price: float
    unit_taxes: float
    total_amount: float
    purchase_date: datetime
    taxes: List[PurchaseTaxRead] = []
    storage: Optional[StorageRead] = None

# --- 6. VENTES ---
class SaleBase(PetroBase):
    client_id: int
    product_id: int
    volume: float = Field(..., gt=0)
    pump_id: Optional[int] = None
    status: str = "delivered"

class SaleCreate(SaleBase):
    unit_price: Optional[float] = None

class SaleRead(SaleBase):
    id: int
    organization_id: int
    unit_price: float 
    total_amount: float
    margin_boss_total: float
    created_at: datetime
    client: Optional[ClientRead] = None
    product: Optional[ProductRead] = None

# --- 7. CONFIGURATION DES PRIX ---
class PriceConfigBase(BaseModel):
    product_id: int
    purchase_sir_unit: float
    taxes_unit: float
    margin_boss_unit: float
    selling_price_unit: float

class PriceConfigCreate(PriceConfigBase):
    pass

class PriceConfigRead(PriceConfigBase):
    id: int
    organization_id: int
    is_active: bool
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)

# --- 8. DASHBOARD & STOCKS ---
class StockStatus(PetroBase):
    product_id: int
    product_name: str
    total_in: float
    total_out: float
    current_stock: float

class DashboardStats(PetroBase):
    total_purchases_volume: float
    total_sales_volume: float
    total_revenue: float
    total_taxes_paid: float
    estimated_margin: float
    stock_levels: List[StockStatus]

