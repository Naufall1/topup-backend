"""Transaction routes — wired into app.py.

Moved verbatim from the old api/app.py (same behavior, same paths: POST /transactions,
GET /transactions/{ref_id}) into the routers/ + services/ layering per
docs/backend-architecture.md.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas import GameUsernameCheckResponse, TransactionRequestSchema, TransactionResponseModel
from services.transaction_service import TransactionService
from session import get_db

router = APIRouter(prefix="/transactions", tags=["transactions"])

DBSession = Annotated[Session, Depends(get_db)]


def get_transaction_service(db: DBSession) -> TransactionService:
    return TransactionService(db)


TransactionServiceDep = Annotated[TransactionService, Depends(get_transaction_service)]


@router.post("", response_model=TransactionResponseModel)
def create_transaction(transaction: TransactionRequestSchema, service: TransactionServiceDep):
    return service.create_transaction(transaction.buyer_sku_code, transaction.customer_no)


@router.get("/{ref_id}", response_model=TransactionResponseModel)
def check_transaction_status(ref_id: str, service: TransactionServiceDep):
    transaction = service.check_transaction_status(ref_id)
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return transaction


@router.get("/{game}/users/{user_id}", response_model=GameUsernameCheckResponse)
def check_game_username(game: str, user_id: str, service: TransactionServiceDep):
    if not user_id.strip():
        raise HTTPException(status_code=400, detail="user_id must not be empty")

    try:
        valid, message, username = service.check_game_username(game, user_id)
    except ValueError:
        raise HTTPException(status_code=404, detail=f"Unsupported game: {game}")

    return GameUsernameCheckResponse(game=game.upper(), user_id=user_id, valid=valid, message=message, username=username)