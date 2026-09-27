"""Game catalog queries. Backs routers/games.py."""
from sqlalchemy.orm import Session

from models import Game


def list_games(db: Session) -> list[Game]:
    """Return the full games catalog. Backs GET /games."""
    return db.query(Game).order_by(Game.buyer_sku_code).all()


def get_game(db: Session, buyer_sku_code: str) -> Game | None:
    """Return a single game by buyer_sku_code, or None if not found. Backs GET /games/{buyer_sku_code}."""
    return db.query(Game).filter(Game.buyer_sku_code == buyer_sku_code).first()
