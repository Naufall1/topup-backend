"""Games catalog routes. Public endpoints (no auth), read the `games` table
seeded by ppob-api/initdb/002-erd-schema.sql / scripts/seed_games_from_price_list.py.
"""
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from schemas import GameSchema
from services.game_service import get_game, list_games
from session import get_db

router = APIRouter(prefix="/games", tags=["games"])

DBSession = Annotated[Session, Depends(get_db)]


@router.get("/", response_model=list[GameSchema])
def get_games(db: DBSession):
    """List the game catalog. Used by UC-01/UC-03 to pick a product."""
    return list_games(db)


@router.get("/{buyer_sku_code}", response_model=GameSchema)
def get_game_by_sku(buyer_sku_code: str, db: DBSession):
    """Fetch a single game by buyer_sku_code, 404 if not found."""
    game = get_game(db, buyer_sku_code)
    if not game:
        raise HTTPException(status_code=404, detail="Game not found")
    return game
