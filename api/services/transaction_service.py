"""Transaction business logic — wired into the app via routers/transactions.py.

TransactionService below is the actual, currently-running logic (moved verbatim
from the old api/service.py — same behavior, just relocated per
docs/backend-architecture.md's layering).

The create_order/get_order_by_trx_id/confirm_order functions further down back
the UC-01/02/03 order split (routers/orders.py, routers/kasir.py) and are kept
separate from the class above since they don't share its Digiflazz-client state.
"""
import logging
import time
import uuid
from datetime import date, datetime, time as dtime, timedelta, timezone

from sqlalchemy.orm import Session

from digiflazz import Digiflazz, DigiflazzError, DigiflazzResponseError
from models import Game, Transaction, User, UsernameCache
from schemas import TransactionSchema

logger = logging.getLogger(__name__)

# "Cek ID"/nickname-check SKUs — deliberately excluded from the purchasable
# `games` catalog by scripts/seed_games_from_price_list.py, so they must never
# be used as Transaction.buyer_sku_code (that column has an FK to games).
GAME_ID_CHECK_SKU = {
    "FF": "FF_ID",
    "ML": "ML_ID",
    "PUBG": "PUBG_ID",
}

# check_game_username polls check_transaction_status while Digiflazz reports
# "pending", up to this many extra attempts, so a stuck check can't hang the
# request/worker thread forever.
GAME_USERNAME_CHECK_MAX_POLLS = 10

# rc codes (see docs/digiflazz-buyer-api.md's rc table) where Digiflazz is
# reporting that the customer_no/username itself is invalid — an expected
# "not found" outcome for this check. Any other rc (saldo habis, IP not
# whitelisted, seller gangguan, ...) is an account/infra problem, not a
# verdict on the ID, so it's left to propagate as a real error instead of
# being reported to the caller as "ID tidak valid".
GAME_USERNAME_INVALID_DESTINATION_RC = {"42", "54"}

# check_game_username caches its result (valid and invalid alike, since either
# outcome still costs a paid Digiflazz "Cek ID" call) in username_cache, keyed
# by (game, user_id), for this long before re-hitting Digiflazz.
GAME_USERNAME_CACHE_TTL = timedelta(days=1)


def _generate_trx_id(db: Session) -> str:
    prefix = f"TRX-{date.today():%d%m%Y}-"
    count = (
        db.query(Transaction)
        .filter(Transaction.trx_id.like(f"{prefix}%"))
        .count()
    )
    return f"{prefix}{count + 1:03d}"


class TransactionService:
    def __init__(self, db: Session, digiflazz: Digiflazz | None = None):
        self.db = db
        self.digiflazz = digiflazz or Digiflazz()

    def create_transaction(self, buyer_sku_code: str, customer_no: str):
        transaction = Transaction(
            trx_id=_generate_trx_id(self.db),
            buyer_sku_code=buyer_sku_code,
            customer_no=customer_no,
            price=0.0,
            status='pending'
        )
        self.db.add(transaction)
        self.db.commit()
        self.db.refresh(transaction)

        logger.info(
            "Creating transaction ref_id=%s buyer_sku_code=%s customer_no=%s",
            transaction.ref_id, buyer_sku_code, customer_no,
        )

        transaction_data = TransactionSchema(
            ref_id=str(transaction.ref_id), buyer_sku_code=buyer_sku_code, customer_no=customer_no
        )

        try:
            digiflazz_response = self.digiflazz.create_transaction(transaction_data)
        except DigiflazzError:
            logger.exception("Digiflazz create_transaction failed for ref_id=%s", transaction.ref_id)
            transaction.status = "failed"
            self.db.commit()
            self.db.refresh(transaction)
            raise

        transaction.status = digiflazz_response.status.lower()
        transaction.price = digiflazz_response.price
        self.db.commit()
        self.db.refresh(transaction)

        return transaction

    def check_transaction_status(self, ref_id: str):
        transaction = self.db.query(Transaction).filter(Transaction.ref_id == ref_id).first()
        if not transaction:
            return None

        try:
            digiflazz_response = self.digiflazz.check_transaction_status(ref_id)
        except DigiflazzError:
            logger.exception("Digiflazz check_transaction_status failed for ref_id=%s", ref_id)
            raise

        transaction.status = digiflazz_response.status.lower()
        transaction.price = digiflazz_response.price
        self.db.commit()
        self.db.refresh(transaction)
        logger.info("Updated transaction %s status to %s based on Digiflazz response", transaction.ref_id, transaction.status)

        return transaction

    def _cache_username_check(
        self, game: str, user_id: str, valid: bool, message: str, username: str | None
    ) -> None:
        cache_row = self.db.get(UsernameCache, (game, user_id))
        if cache_row:
            cache_row.username = username
            cache_row.valid = valid
            cache_row.message = message
        else:
            cache_row = UsernameCache(
                game=game, user_id=user_id, username=username, valid=valid, message=message
            )
            self.db.add(cache_row)
        self.db.commit()

    def check_game_username(self, game: str, user_id: str) -> tuple[bool, str, str | None]:
        """Check whether a game ID/username exists via Digiflazz's 'Cek ID' SKUs.

        Backs GET /transactions/{game}/users/{user_id}. Deliberately never touches
        the local `transactions` table: the check SKUs (FF_ID/ML_ID/PUBG_ID) aren't
        rows in `games` (excluded on purpose by seed_games_from_price_list.py), so
        persisting a Transaction against them would violate the buyer_sku_code FK —
        and a nickname check isn't a real order anyway. Uses a throwaway ref_id
        since there's no local row to key off of.

        Result is cached in `username_cache`, keyed by (game.upper(), user_id),
        for GAME_USERNAME_CACHE_TTL (1 day) — every check, valid or invalid, is a
        paid Digiflazz call, so a fresh cache row short-circuits Digiflazz
        entirely and returns the stored (valid, message, username) as-is.

        Raises ValueError for an unsupported `game`. Returns (False, reason, None)
        rather than raising when Digiflazz rejects the customer_no as invalid
        (rc in GAME_USERNAME_INVALID_DESTINATION_RC, e.g. 54 "Nomor tujuan salah")
        — that's an expected outcome for this check, not an upstream failure. Any
        other DigiflazzResponseError (account/infra issues, not a verdict on the
        ID) is re-raised. If Digiflazz's initial response is "pending", polls
        check_transaction_status (1s apart) until it resolves to a terminal status
        (sukses/gagal) or GAME_USERNAME_CHECK_MAX_POLLS is reached — a "gagal"
        result is terminal too and stops the poll immediately, it just isn't valid.
        """
        buyer_sku_code = GAME_ID_CHECK_SKU.get(game.upper())
        if buyer_sku_code is None:
            raise ValueError(f"Unsupported game: {game}")

        game_key = game.upper()
        cached = self.db.get(UsernameCache, (game_key, user_id))
        if cached and cached.checked_at > datetime.now(timezone.utc) - GAME_USERNAME_CACHE_TTL:
            logger.info(
                "Game username check cache hit game=%s user_id=%s valid=%s", game_key, user_id, cached.valid,
            )
            return cached.valid, cached.message, cached.username

        transaction_data = TransactionSchema(
            ref_id=str(uuid.uuid4()), buyer_sku_code=buyer_sku_code, customer_no=user_id
        )

        try:
            response = self.digiflazz.create_transaction(transaction_data)

            polls = 0
            while response.status.lower() == "pending" and polls < GAME_USERNAME_CHECK_MAX_POLLS:
                time.sleep(1)
                response = self.digiflazz.check_transaction_status(transaction_data.ref_id)
                polls += 1
        except DigiflazzResponseError as exc:
            if exc.rc not in GAME_USERNAME_INVALID_DESTINATION_RC:
                logger.warning(
                    "Game username check failed for game=%s user_id=%s (rc=%s): %s", game, user_id, exc.rc, exc,
                )
                raise
            logger.info("Game username check rejected for game=%s user_id=%s: %s", game, user_id, exc)
            valid, message, username = False, "Invalid user ID", None
            self._cache_username_check(game_key, user_id, valid, message, username)
            return valid, message, username

        valid = response.status.lower() == "sukses"
        username = None
        if valid:
            username = response.sn.split("/")[-1].strip()  # Digiflazz returns "ID/username" in sn, we just want the username
        logger.info("Checked game username game=%s user_id=%s valid=%s", game, user_id, valid)
        self._cache_username_check(game_key, user_id, valid, response.message, username)
        return valid, response.message, username


def create_order(db: Session, buyer_sku_code: str, customer_no: str) -> Transaction:
    """UC-01: create a `submitted` row, price copied from games.sell_price, no Digiflazz call."""
    game = db.get(Game, buyer_sku_code)
    if game is None:
        raise ValueError(f"Unknown buyer_sku_code: {buyer_sku_code}")

    order = Transaction(
        trx_id=_generate_trx_id(db),
        buyer_sku_code=buyer_sku_code,
        customer_no=customer_no,
        price=game.sell_price,
        status="submitted",
    )
    db.add(order)
    db.commit()
    db.refresh(order)

    logger.info("Created order trx_id=%s buyer_sku_code=%s customer_no=%s", order.trx_id, buyer_sku_code, customer_no)

    return order


def get_order_by_trx_id(db: Session, trx_id: str) -> Transaction | None:
    """Local lookup by trx_id (no live Digiflazz sync). Backs GET /orders/{trx_id}."""
    return db.get(Transaction, trx_id)


def confirm_order(db: Session, trx_id: str, kasir: User, digiflazz: Digiflazz | None = None) -> Transaction | None:
    """UC-02/UC-03: submit a `submitted` order to Digiflazz, set user_id, update status/price.

    Returns None if trx_id doesn't exist (routers/kasir.py turns that into a 404).
    Raises ValueError if the order exists but isn't `submitted` (routers/kasir.py
    turns that into a 409 — already confirmed or in a terminal state).

    Reuses the same Digiflazz-call-then-persist-response pattern as
    TransactionService.create_transaction — see the architecture doc's Status
    lifecycle section.
    """
    order = db.get(Transaction, trx_id)
    if order is None:
        return None
    if order.status != "submitted":
        raise ValueError(f"Order {trx_id} is not submitted (status={order.status})")

    digiflazz = digiflazz or Digiflazz()
    order.user_id = kasir.id

    transaction_data = TransactionSchema(
        ref_id=str(order.ref_id), buyer_sku_code=order.buyer_sku_code, customer_no=order.customer_no
    )

    try:
        digiflazz_response = digiflazz.create_transaction(transaction_data)
    except DigiflazzError:
        logger.exception("Digiflazz create_transaction failed for trx_id=%s ref_id=%s", trx_id, order.ref_id)
        order.status = "failed"
        db.commit()
        db.refresh(order)
        raise

    order.status = digiflazz_response.status.lower()
    order.price = digiflazz_response.price
    db.commit()
    db.refresh(order)

    logger.info("Confirmed order trx_id=%s kasir_id=%s status=%s", trx_id, kasir.id, order.status)
    return order


def list_today_transactions_for_kasir(db: Session, kasir_id: int) -> list[dict]:
    """Kasir dashboard: this Kasir's confirmed transactions today (excludes
    still-submitted orders). Filtered by updated_at — the moment confirm_order
    actually wrote status/user_id — not created_at, since for UC-02 orders
    created_at is when the Customer originally created the `submitted` row,
    possibly a different day than when the Kasir confirms it. Uses naive
    date.today() to match _generate_trx_id's convention, consistent with the
    transactions table's non-timezone-aware TIMESTAMP columns.
    """
    today = date.today()
    start = datetime.combine(today, dtime.min)
    end = datetime.combine(today, dtime.max)

    rows = (
        db.query(Transaction, Game)
        .join(Game, Transaction.buyer_sku_code == Game.buyer_sku_code)
        .filter(
            Transaction.user_id == kasir_id,
            Transaction.status != "submitted",
            Transaction.updated_at.between(start, end),
        )
        .order_by(Transaction.updated_at.desc())
        .all()
    )
    return [
        {
            "trx_id": t.trx_id,
            "ref_id": str(t.ref_id),
            "product_name": g.product_name,
            "brand": g.brand,
            "customer_no": t.customer_no,
            "price": t.price,
            "status": t.status,
            "updated_at": t.updated_at,
        }
        for t, g in rows
    ]
