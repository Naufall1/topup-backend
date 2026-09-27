"""Customer-facing order routes (UC-01). Public endpoints. POST / creates a
`submitted` order with no Digiflazz call (unlike today's POST /transactions in
app.py, which still does the old merged create+submit flow — untouched).

GET /{trx_id} returns the local row as-is (no live Digiflazz sync), distinct from
today's GET /transactions/{ref_id} — reconciling the two is an open decision, see
the architecture doc's "Target endpoint catalog" section.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas import OrderCreateRequest, OrderResponse
from services.transaction_service import create_order, get_order_by_trx_id
from session import get_db

router = APIRouter(prefix="/orders", tags=["orders"])

DBSession = Annotated[Session, Depends(get_db)]


@router.post("/", response_model=OrderResponse)
def create_new_order(order: OrderCreateRequest, db: DBSession):
    """UC-01: customer places an order. Creates a `submitted` row, no Digiflazz call yet."""
    try:
        return create_order(db, order.buyer_sku_code, order.customer_no)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unknown buyer_sku_code: {order.buyer_sku_code}")


@router.get("/{trx_id}", response_model=OrderResponse)
def get_order(trx_id: str, db: DBSession):
    """UC-02 scan step: Kasir looks up the order encoded in the customer's QR."""
    order = get_order_by_trx_id(db, trx_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
