"""Seed the local `games` catalog table from a saved Digiflazz price-list JSON
(see scripts/fetch_price_list.py).

Only category == "Games" products are inserted, excluding "Cek Username"
check-nickname items (e.g. buyer_sku_code "ff_id", "ml_id", "PUBG_ID") since
those aren't purchasable topup products.

Existing rows (matched by buyer_sku_code) are upserted (buy_price/stock/etc.
refreshed) rather than duplicated. On insert, sell_price is seeded equal to
buy_price (no markup) — meant to be edited manually per product afterwards.
Re-running this script on an existing row only refreshes buy_price, never
sell_price, so manual edits aren't clobbered by a reseed.

Run from api/: python -m scripts.seed_games_from_price_list [json_path]
Default json_path: price_list.json
"""
import json
import sys

from sqlalchemy.dialects.postgresql import insert

from models import Game
from session import SessionLocal

if __name__ == "__main__":
    json_path = sys.argv[1] if len(sys.argv) > 1 else "price_list.json"

    with open(json_path, encoding="utf-8") as f:
        price_list = json.load(f)

    games = [
        item for item in price_list
        if item["category"] == "Games" and "cek username" not in item["product_name"].lower()
    ]

    db = SessionLocal()
    try:
        for item in games:
            stmt = insert(Game).values(
                buyer_sku_code=item["buyer_sku_code"],
                product_name=item["product_name"],
                brand=item["brand"],
                buy_price=item["price"],
                sell_price=item["price"],
                stock=item["stock"],
                desc=item["desc"],
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[Game.buyer_sku_code],
                set_={
                    "product_name": stmt.excluded.product_name,
                    "brand": stmt.excluded.brand,
                    "buy_price": stmt.excluded.buy_price,
                    "stock": stmt.excluded.stock,
                    "desc": stmt.excluded.desc,
                },
            )
            db.execute(stmt)
        db.commit()
    finally:
        db.close()

    print(f"Upserted {len(games)} games into the database (skipped {len(price_list) - len(games)} non-game / cek-username items)")
