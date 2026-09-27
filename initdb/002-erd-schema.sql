-- Adds the "user" (Kasir) and "game" (catalog) entities from docs/system-design.drawio,
-- and restructures transactions to use a trx_id primary key with a nullable Kasir FK
-- and a buyer_sku_code FK into the game catalog. See ppob-api/CLAUDE.md for naming notes.

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS games (
    buyer_sku_code VARCHAR(50) PRIMARY KEY,
    product_name VARCHAR(255) NOT NULL,
    brand VARCHAR(100) NOT NULL,
    buy_price NUMERIC(10,2) NOT NULL,
    sell_price NUMERIC(10,2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    "desc" VARCHAR(255)
);

-- Placeholder catalog data (not verified live Digiflazz product codes), aligned
-- with ppop-frontend/src/data/games.ts's three image-backed games.
-- sell_price seeded equal to buy_price (no markup yet) — meant to be edited manually per product.
INSERT INTO games (buyer_sku_code, product_name, brand, buy_price, sell_price, stock, "desc") VALUES
    ('ml-86', 'Mobile Legends 86 Diamonds', 'Mobile Legends', 20000, 20000, 999, 'Top up 86 Diamonds'),
    ('ml-172', 'Mobile Legends 172 Diamonds', 'Mobile Legends', 40000, 40000, 999, 'Top up 172 Diamonds'),
    ('ff-70', 'Free Fire 70 Diamonds', 'Free Fire', 10000, 10000, 999, 'Top up 70 Diamonds'),
    ('ff-140', 'Free Fire 140 Diamonds', 'Free Fire', 20000, 20000, 999, 'Top up 140 Diamonds'),
    ('pubgm-60', 'PUBG Mobile 60 UC', 'PUBG Mobile', 15000, 15000, 999, 'Top up 60 UC'),
    ('pubgm-325', 'PUBG Mobile 325 UC', 'PUBG Mobile', 75000, 75000, 999, 'Top up 325 UC'),
    ('xld10', 'XL Pulsa 10.000 (Digiflazz sandbox)', 'XL', 10000, 11000, 999, 'Digiflazz sandbox test SKU (docs/digiflazz-buyer-api.md) — deterministic test cases, not a real product')
ON CONFLICT (buyer_sku_code) DO NOTHING;

-- Existing transactions rows are disposable local test data created while
-- manually verifying the api/webhook services; truncate before restructuring
-- since the new buyer_sku_code FK can't be satisfied by ad-hoc SKUs like "xld10".
TRUNCATE TABLE transactions;

ALTER TABLE transactions
    ADD COLUMN trx_id VARCHAR(20) NOT NULL,
    ADD COLUMN user_id INT REFERENCES users(id);

ALTER TABLE transactions DROP CONSTRAINT transactions_pkey;
ALTER TABLE transactions ADD PRIMARY KEY (trx_id);
ALTER TABLE transactions ADD CONSTRAINT transactions_ref_id_key UNIQUE (ref_id);
ALTER TABLE transactions ADD CONSTRAINT transactions_buyer_sku_code_fkey
    FOREIGN KEY (buyer_sku_code) REFERENCES games(buyer_sku_code);
