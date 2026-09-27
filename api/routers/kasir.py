"""Kasir-facing routes.

Auth (login/refresh/logout) and the order routes (UC-02/03) are wired and
implemented — see docs/backend-architecture.md for the full order-split design.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from auth import get_current_kasir
from models import User
from schemas import (
    KasirLoginRequest,
    KasirLoginResponse,
    KasirTransactionSummary,
    OrderCreateRequest,
    OrderResponse,
)
from services.auth_service import issue_tokens, refresh_tokens, revoke_refresh_token, verify_kasir_credentials
from services.transaction_service import confirm_order, create_order, list_today_transactions_for_kasir
from session import get_db
from config import config

router = APIRouter(prefix="/kasir", tags=["kasir"])

DBSession = Annotated[Session, Depends(get_db)]
CurrentKasir = Annotated[User, Depends(get_current_kasir)]

REFRESH_COOKIE_NAME = "refresh_token"


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/kasir",
        max_age=config.JWT_REFRESH_EXPIRE_DAYS * 86400,
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/kasir")


def _token_response(access_token: str) -> KasirLoginResponse:
    return KasirLoginResponse(
        access_token=access_token,
        expires_in=config.JWT_ACCESS_EXPIRE_MINUTES * 60,
    )


@router.post("/login", response_model=KasirLoginResponse)
def login(credentials: KasirLoginRequest, response: Response, db: DBSession):
    """Verify Kasir credentials, issue an access+refresh token pair, and set the
    refresh token as an httpOnly cookie (never exposed to frontend JS)."""
    kasir = verify_kasir_credentials(db, credentials.username, credentials.password)
    access_token, refresh_token = issue_tokens(db, kasir)
    _set_refresh_cookie(response, refresh_token)
    return _token_response(access_token)


@router.post("/refresh", response_model=KasirLoginResponse)
def refresh(request: Request, response: Response, db: DBSession):
    """Rotate the refresh token cookie for a new access+refresh token pair."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(status_code=401, detail="Missing refresh token")

    access_token, new_refresh_token = refresh_tokens(db, refresh_token)
    _set_refresh_cookie(response, new_refresh_token)
    return _token_response(access_token)


@router.post("/logout")
def logout(request: Request, response: Response, db: DBSession):
    """Revoke the refresh token cookie and clear it."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    _clear_refresh_cookie(response)
    return {"status": "success"}


@router.post("/orders/{trx_id}/confirm", response_model=OrderResponse)
def confirm_existing_order(trx_id: str, kasir: CurrentKasir, db: DBSession):
    """UC-02: Kasir confirms a `submitted` order scanned from the customer's QR."""
    try:
        order = confirm_order(db, trx_id, kasir)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@router.post("/orders", response_model=OrderResponse)
def create_and_confirm_order(order: OrderCreateRequest, kasir: CurrentKasir, db: DBSession):
    """UC-03: Kasir creates and confirms an order in one step (walk-in/cash customer)."""
    try:
        transaction = create_order(db, order.buyer_sku_code, order.customer_no)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return confirm_order(db, transaction.trx_id, kasir)


@router.get("/orders/today", response_model=list[KasirTransactionSummary])
def list_today_orders(kasir: CurrentKasir, db: DBSession):
    """Kasir dashboard: transactions this Kasir confirmed today."""
    return list_today_transactions_for_kasir(db, kasir.id)
