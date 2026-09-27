from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

class SaldoSchema(BaseModel):
    deposit: float

class PriceListSchema(BaseModel):
    product_name: str
    category: str
    brand: str
    type: str
    seller_name: str
    price: float
    buyer_sku_code: str
    buyer_product_status: bool
    seller_product_status: bool
    unlimited_stock: bool
    stock: int
    multi: bool
    start_cut_off: str
    end_cut_off: str
    desc: str

class TransactionRequestSchema(BaseModel):
    buyer_sku_code: str
    customer_no: str

class TransactionSchema(BaseModel):
    ref_id: str
    buyer_sku_code: str
    customer_no: str

class TransactionResponseSchema(BaseModel):
    ref_id: str
    customer_no: str
    buyer_sku_code: str
    message: str
    status: str
    rc: str
    sn: str
    buyer_last_saldo: float
    price: float
    tele: str
    wa: str

class TransactionResponseModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trx_id: str
    ref_id: str
    buyer_sku_code: str
    customer_no: str
    price: float
    status: str

    @field_validator("ref_id", mode="before")
    @classmethod
    def _stringify_ref_id(cls, value):
        return str(value)

class KasirTransactionSummary(BaseModel):
    """Kasir dashboard row — one of this Kasir's transactions confirmed today.
    Built from a Transaction+Game join (services/transaction_service.py's
    list_today_transactions_for_kasir), not a bare from_attributes(Transaction)."""
    model_config = ConfigDict(from_attributes=True)

    trx_id: str
    ref_id: str
    product_name: str
    brand: str
    customer_no: str
    price: float
    status: str
    updated_at: datetime

class GameUsernameCheckResponse(BaseModel):
    game: str
    user_id: str
    valid: bool
    message: str
    username: str | None

# --- Kasir auth (wired — routers/kasir.py's /login, /refresh, /logout)

class KasirLoginRequest(BaseModel):
    username: str
    password: str

class KasirLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

# --- Not wired into any endpoint yet — schemas for the target architecture
# described in docs/backend-architecture.md (games catalog, UC-01/02/03 order
# flow). See that doc before using these.

class GameSchema(BaseModel):
    """Customer/Kasir-facing product view — only exposes sell_price, never buy_price."""
    model_config = ConfigDict(from_attributes=True)

    buyer_sku_code: str
    product_name: str
    brand: str
    sell_price: float
    stock: int
    desc: str | None

class OrderCreateRequest(BaseModel):
    buyer_sku_code: str
    customer_no: str

class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    trx_id: str
    ref_id: str
    buyer_sku_code: str
    customer_no: str
    price: float
    status: str
    user_id: int | None

    @field_validator("ref_id", mode="before")
    @classmethod
    def _stringify_ref_id(cls, value):
        return str(value)