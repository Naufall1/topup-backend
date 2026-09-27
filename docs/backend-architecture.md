# Backend target architecture (design doc — partially implemented)

This describes where `api/` is headed to support the full flow in `docs/use-case-scenario.md` (UC-01/02/03) against the ERD already implemented in `docs/system-design.drawio` (`users`, `games`, `transactions` — see `ppob-api/CLAUDE.md`).

**Everything in this doc is now real and wired in — layering, Kasir auth, the games catalog, and all three use cases (UC-01/02/03).** `create_order`/`get_order_by_trx_id`/`confirm_order` in `api/services/transaction_service.py` are all implemented; `POST /kasir/orders` and `POST /kasir/orders/{trx_id}/confirm` require a valid Kasir JWT and are fully functional.

The one remaining open item is *not* a missing use case but an architectural decision: `POST /transactions` (`api/routers/transactions.py` → `services/transaction_service.py`) still creates a row and immediately submits it to Digiflazz in one step (no `submitted` state, no Kasir) — this legacy endpoint was deliberately left untouched rather than migrated onto the create/confirm split, and its `GET /transactions/{ref_id}` (live Digiflazz sync) still overlaps with the newer `GET /orders/{trx_id}` (local-only lookup). See "Rollout order" below.

## Layering

```
routers/   (HTTP layer — FastAPI APIRouters, request/response schemas, auth dependency)
   ↓
services/  (business logic — orchestrates DB + Digiflazz, mirrors today's TransactionService)
   ↓
models.py / session.py   (unchanged — SQLAlchemy ORM + engine/session)
```

Same shape as today's `app.py → service.py → models.py`, just split into one router/service pair per domain (transactions, kasir/auth, games) instead of one flat file. No repository layer, no DI framework — that would be over-engineering relative to this project's scale and established minimalism (see `ppob-api/CLAUDE.md`).

## Target folder structure

```
api/
  app.py                  # wired: app-level concerns only — exception handlers, GET /saldo,
                           #   app.include_router(transactions.router), app.include_router(kasir.router).
                           #   Future: + games router.
  auth.py                 # WIRED — password hashing, JWT access-token issuance/decoding,
                           #   opaque refresh-token helpers, get_current_kasir dependency
  config.py                # + JWT_SECRET, JWT_ACCESS_EXPIRE_MINUTES, JWT_REFRESH_EXPIRE_DAYS (done)
  digiflazz.py              # unchanged
  models.py                  # + RefreshToken (done); User, Game, Transaction already existed
  schemas.py                   # + request/response schemas per endpoint
  security.py                   # unchanged (Digiflazz signing — unrelated to Kasir auth)
  session.py                     # unchanged
  routers/
    transactions.py               # WIRED — POST /transactions, GET /transactions/{ref_id} (today's behavior)
    kasir.py                       # WIRED — POST /kasir/login, /refresh, /logout;
                                    #   POST /kasir/orders, /kasir/orders/{trx_id}/confirm (UC-03/UC-02,
                                    #   Kasir JWT required)
    games.py                      # WIRED — GET /games, GET /games/{buyer_sku_code}
    orders.py                      # WIRED — POST /orders, GET /orders/{trx_id}
  services/
    transaction_service.py           # WIRED — TransactionService (today's behavior, moved verbatim
                                      #   from the old api/service.py), plus create_order()/
                                      #   get_order_by_trx_id()/confirm_order() (WIRED, UC-01/02/03).
    auth_service.py                  # WIRED — verify_kasir_credentials, issue_tokens, refresh_tokens,
                                      #   revoke_refresh_token
    game_service.py                   # WIRED — list_games(db), get_game(db, buyer_sku_code)
  scripts/
    smoke_test.py                       # unchanged
```

## Target endpoint catalog

| Method & path | Auth | Request | Response | UC | Status transition |
|---|---|---|---|---|---|
| `POST /kasir/login` **(wired)** | public | `{username, password}` | `{access_token, token_type: "bearer", expires_in}` + refresh token set as an httpOnly cookie (401 on bad credentials) | — | — |
| `POST /kasir/refresh` **(wired)** | public (refresh token cookie is the credential) | — (reads the `refresh_token` cookie) | same shape as login, cookie rotated | — | — |
| `POST /kasir/logout` **(wired)** | public (refresh token cookie is the credential) | — (reads the `refresh_token` cookie) | `{status: "success"}`, idempotent | — | — |
| `GET /games` **(wired)** | public | — | list of `{buyer_sku_code, product_name, brand, sell_price, stock, desc}` | UC-01/03 (pick a product) | — |
| `GET /games/{buyer_sku_code}` **(wired)** | public | — | single game or 404 | — | — |
| `GET /transactions/{game}/users/{user_id}` **(wired)** | public | — | `{game, user_id, valid, message}` (400 empty `user_id`, 404 unsupported `game`) | UC-01 (validate destination ID before ordering) | — |
| `POST /orders` **(wired)** | public | `{buyer_sku_code, customer_no}` | `{trx_id, ref_id, buyer_sku_code, customer_no, price, status}` (404 on unknown `buyer_sku_code`) | UC-01 | *(create)* → `submitted` |
| `GET /orders/{trx_id}` **(wired)** | public/Kasir | — | local row as-is, **no live Digiflazz sync** (404 if missing) | UC-02 (Kasir scans the QR containing `trx_id`) | — |
| `POST /kasir/orders/{trx_id}/confirm` **(wired)** | Kasir JWT | — | updated order (404 unknown `trx_id`, 409 not `submitted`) | UC-02 | `submitted` → `pending`/`sukses`/`gagal` (or `failed` on `DigiflazzError`) |
| `POST /kasir/orders` **(wired)** | Kasir JWT | `{buyer_sku_code, customer_no}` | created + confirmed order (404 unknown `buyer_sku_code`) | UC-03 | *(create + confirm in one call)* → same as above |
| `POST /webhook` | signature-verified | — | — | UC-02 async finalization | `pending` → `sukses`/`gagal` |

`POST /orders` creates the row with `price` copied from `games.sell_price` (the local catalog price shown to the customer before confirmation, **not** `games.buy_price`) rather than `0.0`.

`GET /orders/{trx_id}` vs today's `GET /transactions/{ref_id}` (which does a live Digiflazz re-check by `ref_id`) are two different lookup semantics that will likely need to be reconciled — **left as an open decision for the implementation pass**, not decided here.

## Status lifecycle

```
submitted  --Kasir confirms, Digiflazz responds-->  pending | sukses | gagal   (per Digiflazz's rc)
submitted  --Kasir confirms, Digiflazz call errors-->  failed                  (DigiflazzError, as today)
pending    --webhook async update-->  sukses | gagal
```

`confirm_order()` reuses the exact same Digiflazz-call-then-persist-response pattern `TransactionService.create_transaction` uses today (`api/services/transaction_service.py`) — only the trigger moves from "on create" to "on Kasir confirm", and `user_id` gets set to the confirming Kasir at that point. Verified end-to-end against Digiflazz's documented sandbox test cases (`docs/digiflazz-buyer-api.md`, `buyer_sku_code="xld10"`): Sukses/Gagal/Pending all transition and persist correctly, a second confirm on the same `trx_id` correctly 409s, and UC-03's single-call create+confirm reaches `sukses` immediately.

## Kasir auth design (implemented)

Stateful access+refresh scheme — chosen over pure stateless JWT-for-everything specifically because refresh tokens need to be revocable/rotatable (confirmed requirement).

- **Password hashing**: `bcrypt` directly (simpler and more actively maintained than `passlib`, the common FastAPI-tutorial default which has stalled).
- **Access token**: JWT (`pyjwt`, HS256), claims `{sub: user.id, username, type: "access", iat, exp}`, 3h lifetime (`JWT_ACCESS_EXPIRE_MINUTES`, default `180`). Verified purely by signature/expiry — stateless, no DB hit beyond loading the `User` row.
- **Refresh token**: **not a JWT** — an opaque random string (`secrets.token_urlsafe(32)`). Since it's tracked server-side anyway (for revocation), a JWT's self-contained claims would be redundant complexity; an opaque string is simpler and equally secure. Only its SHA-256 hash is persisted (`refresh_tokens.token_hash`) — same reasoning as password hashing, a fast hash suffices here because the token's security comes from its own 256 bits of randomness, not from a slow/salted KDF the way a human password needs. 7-day lifetime (`JWT_REFRESH_EXPIRE_DAYS`, default `7`).
- **Validation of the refresh token has no cryptographic step at all** (unlike the JWT access token) — it's entirely DB-state-driven: hash the presented token, look up the row, reject (401) if missing, `revoked_at IS NOT NULL`, or `expires_at` in the past.
- **Rotation**: every successful `POST /kasir/refresh` immediately revokes the presented token (`revoked_at = now()`) and issues a brand-new access+refresh pair. This makes each refresh token single-use.
- **Logout**: `POST /kasir/logout` revokes a refresh token immediately; idempotent (no error re-revoking or on an unknown token) so a double-logout call can't fail. Access tokens can't be revoked early — 3h is the maximum exposure window.
- **Transport**: `fastapi.security.HTTPBearer` reading `Authorization: Bearer <token>` for the access token — not the OAuth2 password-form flow, since login takes a JSON body like every other endpoint in this API.
- **Dependency**: `get_current_kasir` in `api/auth.py`, following the same `Annotated[X, Depends(...)]` pattern `app.py` already uses for `DBSession`/`TransactionServiceDep` — decodes the access JWT, loads the `User` row by `sub`, raises 401 on any failure (missing/garbage/expired/wrong-type token, or the user no longer existing).
- **Secret**: `JWT_SECRET`, required in `config.py`'s fail-fast list and in `.env`.
- **Provisioning**: no registration endpoint exists or is planned — Kasir accounts are created manually. `initdb/003-refresh-tokens.sql` seeds a demo account (`kasir1`/`kasir123`, matching `ppop-frontend`'s existing hardcoded demo login) for local testing.
- **Deliberately not built** (flagged as future hardening): refresh-token-reuse detection (revoking *all* of a user's tokens if an already-revoked one is presented again, which would indicate the token was stolen and used twice), and rate-limiting on `/kasir/login`.

## Rollout order for the future implementation pass

1. ~~Move `api/service.py`'s `TransactionService` into `services/transaction_service.py`, wire `routers/transactions.py` into `app.py`.~~ **Done** — pure relocation, no behavior change.
2. ~~`api/auth.py`: real password hashing + JWT access-token issuance/validation. `services/auth_service.py` + `routers/kasir.py`'s login/refresh/logout, wired into `app.py`.~~ **Done** — stateful access+refresh JWT scheme, see "Kasir auth design" above.
3. ~~`services/game_service.py`, `routers/games.py` — wire into `app.py`.~~ **Done** — plain read-only queries against the seeded `games` table, no Digiflazz call.
4. ~~Implement `services/transaction_service.py`'s `create_order()`/`get_order_by_trx_id()` for real (UC-01), keeping `TransactionService`/`POST /transactions` working until the split endpoints are ready to take over.~~ **Done** — `create_order` validates the SKU against `games` (404 via `ValueError`, no unhandled `IntegrityError`), copies `price` from `sell_price`, sets `status="submitted"`, makes no Digiflazz call.
5. ~~`routers/orders.py` — wire into `app.py`.~~ **Done.**
6. Resolve the `GET /orders/{trx_id}` vs `GET /transactions/{ref_id}` overlap (decide: keep both, merge, or deprecate one). **Still open** — deliberate, not a bug; `POST /transactions` and `POST /orders` continue to coexist.
7. ~~Implement `confirm_order()` for real (UC-02/03).~~ **Done** — 404 on unknown `trx_id`, 409 if not `submitted`, otherwise submits to Digiflazz and persists `status`/`price`/`user_id`. All three use cases are now implemented.
8. ~~Update `ppob-api/CLAUDE.md` to describe the new architecture once it's fully real.~~ **Done.**

`POST /transactions` / `GET /transactions/{ref_id}` / `POST /webhook` (the legacy merged flow) keep working exactly as they do now, unaffected by the UC-01/02/03 split — only item 6 above is still an open decision.
