-- username_cache: caches Digiflazz "Cek ID" (game-username) check results for
-- 1 day so repeated checks of the same game+user_id don't re-spend a paid
-- Digiflazz transaction, see api/services/transaction_service.py's
-- check_game_username. Keyed by (game, user_id) — not FK'd to users/games:
-- user_id here is the customer's in-game ID being checked, not a Kasir
-- account, and game is the brand code (FF/ML/PUBG), not games.buyer_sku_code.

CREATE TABLE IF NOT EXISTS username_cache (
    game VARCHAR(20) NOT NULL,
    user_id VARCHAR(50) NOT NULL,
    username VARCHAR(100),
    valid BOOLEAN NOT NULL,
    message VARCHAR(255) NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (game, user_id)
);
