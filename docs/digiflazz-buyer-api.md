# Digiflazz Buyer API reference

Condensed from the official docs, **Buyer section only**: https://developer.digiflazz.com/api/buyer/persiapan/ (and sibling pages under `/api/buyer/`). Pulled 2026-07-28. This is our own reference copy for working on `ppob-api` — always prefer the live docs if something here seems stale or ambiguous.

This repo (`api/digiflazz.py`) only implements a subset: `cek-saldo`, `price-list` (prepaid), `transaction` (prepaid topup + status check), and `report/hooks/{id}/pings`. The postpaid (`pascabayar`) and PLN inquiry sections below are **not implemented yet** — kept here for when that's needed.

## Setup

- Base URL: `https://api.digiflazz.com/v1`
- Get `username` + API key from the Digiflazz "Pengaturan Koneksi API" page.
- Whitelist your server's IP there (dev and prod separately) — a wrong/missing whitelist entry is `rc: 45`.
- Whitelist Digiflazz's own IP `52.74.250.133` on your side (for their webhook calls).
- `Content-Type: application/json`, everything is `POST`.
- Every request includes a `sign` field: `md5(username + api_key + <action-specific string>)`. The action string differs per endpoint (see below) — for `transaction`/status-check/inquiry-pln it's not a fixed keyword but the request's own `ref_id`/`customer_no`.

## Endpoints (prepaid — what this repo implements)

### `POST /cek-saldo` — Cek Saldo
Sign string: `"depo"`.
```json
// request
{ "cmd": "deposit", "username": "...", "sign": "..." }
// response (wrapped in "data")
{ "data": { "deposit": 500000000000 } }
```

### `POST /price-list` — Daftar Harga (prepaid)
Sign string: `"pricelist"`. `cmd: "prepaid"` (use `"pasca"` for postpaid price list — different response shape, has `admin`/`commission` instead of `price`/`stock`/etc.). Optional filters: `code`, `category`, `brand`, `type` — filtered results lag live data by ~10-15 min, don't poll aggressively (rc `83` = rate-limited: max ~1x/5min for the full list, ~1x/sec per single code).
```json
// response item (data is a list)
{
  "product_name": "Xl 100.000", "category": "Pulsa", "brand": "XL", "type": "Umum",
  "seller_name": "PT. ABC", "price": 98000, "buyer_sku_code": "X100",
  "buyer_product_status": true, "seller_product_status": true,
  "unlimited_stock": true, "stock": 0, "multi": true,
  "start_cut_off": "23:45", "end_cut_off": "00:15", "desc": "Pulsa Xl Rp 100.000"
}
```

### `POST /transaction` — Topup (prepaid)
Sign string: the request's own `ref_id`. Processed **synchronously** — you always get sukses/gagal/pending back immediately (pending needs a follow-up, see Cek Status below). Extra optional fields not currently sent by this repo: `max_price` (abort if seller price exceeds this), `cb_url` (per-request webhook override), `allow_dot` (allow `.` in `customer_no`).
```json
// request
{
  "username": "...", "buyer_sku_code": "xld25", "customer_no": "087800001233",
  "ref_id": "some1d", "sign": "...",
  "testing": true   // optional, sandbox mode — this repo wires it to DIGIFLAZZ_TESTING_MODE
}
// response (wrapped in "data")
{
  "ref_id": "some1d", "customer_no": "087800001233", "buyer_sku_code": "xld25",
  "message": "Transaksi Pending", "status": "Pending", "rc": "03", "sn": "",
  "buyer_last_saldo": 100000, "price": 25000, "tele": "@telegram", "wa": "081234512345"
}
```
Matches `schemas.TransactionSchema` / `TransactionResponseSchema` exactly.

### Cek Status (prepaid)
No separate endpoint — **re-POST to `/transaction` with the exact same `ref_id`** (this is what `Digiflazz.check_transaction_status` does). Don't call this more than once per minute for the same `ref_id` (race condition risk on Digiflazz's side), and never after 90 days (creates a brand-new transaction instead of checking the old one).

### `POST /inquiry-pln` — validate a PLN customer number (not implemented here)
Sign string: the request's `customer_no`.
```json
// request
{ "username": "...", "customer_no": "1234554321", "sign": "..." }
// response
{
  "data": {
    "message": "Transaksi Sukses", "status": "Sukses", "rc": "00",
    "customer_no": "1234554321", "meter_no": "1234554321",
    "subscriber_id": "523300817840", "name": "DAVID", "segment_power": "R1 /000001300"
  }
}
```

### `POST /deposit` — request a deposit top-up ticket (not implemented here)
Sign string: `"deposit"` (note: different from `cek-saldo`'s `"depo"`). Request: `username`, `amount`, `Bank` (`Flip`/`ShopeePay` for individuals, `BCA`/`MANDIRI`/`BRI`/`BNI` for companies), `owner_name`, `sign`. Response gives you a `bank`/`account_no`/`amount`/`notes` to actually transfer.

## Postpaid (`pascabayar`) — not implemented here

Same `/transaction` endpoint, but request carries a `commands` field instead of relying on presence/absence alone, and the response's `desc` object shape is **product-category-specific** (PLN, PDAM, Internet, BPJS Kesehatan, Multifinance, PBB, Pajak Daerah Lainnya, Gas Negara/Pertagas, TV, BPJSTK, BPJSTKPU, PLN Nontaglis, E-Money, SAMSAT, HP/Lainnya each have their own `desc` sub-fields — see the live docs for the exact shape per category, they're too numerous to usefully inline here).

- **Cek Tagihan** (`commands: "inq-pasca"`) — inquire the bill amount before paying. Sign string: `ref_id`.
- **Bayar Tagihan** (`commands: "pay-pasca"`) — pay a previously-inquired bill; must be same calendar day as the inquiry, same `ref_id`. Sign string: `ref_id`.
- **Cek Status** (`commands: "status-pasca"`) — re-check a postpaid transaction by `ref_id`. Same 90-day cutoff caveat as prepaid.

Common response fields across all postpaid categories: `ref_id`, `customer_no`, `customer_name`, `buyer_sku_code`, `admin`, `message`, `status` (`Sukses`/`Gagal`), `rc`, `periode`, `sn` (payment only), `buyer_last_saldo`, `price`, `selling_price`, `desc` (category-specific object).

## Test case sandbox values (prepaid)

Use these with `"testing": true` against the real `/transaction` endpoint to get deterministic outcomes without touching real balance:

| `buyer_sku_code` | `customer_no` | Result |
|---|---|---|
| `xld10` | `087800001230` | Sukses |
| `xld10` | `087800001232` | Gagal |
| `xld10` | `087800001233` | Pending → callback Sukses |
| `xld10` | `087800001234` | Pending → callback Gagal |

`api/scripts/smoke_test.py` currently uses `customer_no="087800001234"` — i.e. it deliberately/incidentally exercises the "pending then fails" path, not a clean success.

## Response codes (`rc`)

`_post` in `api/digiflazz.py` treats `rc` outside `["00", "02", "03"]` as an error (`DigiflazzResponseError`) — those three are the only codes where a transaction actually *formed* with a normal outcome (success/failed/pending); everything else is a request-level rejection.

| rc | Message | Status | Forms a transaction? |
|---|---|---|---|
| 00 | Transaksi Sukses | Sukses | Ya |
| 01 | Timeout | Gagal | Ya |
| 02 | Transaksi Gagal | Gagal | Ya |
| 03 | Transaksi Pending | Pending | Ya |
| 40 | Payload Error | Gagal | Tidak |
| 41 | Signature tidak valid | Gagal | Tidak |
| 42 | Gagal memproses API Buyer (username salah) | Gagal | Tidak |
| 43 | SKU tidak ditemukan / non-aktif | Gagal | Tidak |
| 44 | Saldo tidak cukup | Gagal | Tidak |
| 45 | IP Anda tidak kami kenali | Gagal | Tidak |
| 47 | Transaksi sudah terjadi di buyer lain | Gagal | Tidak |
| 49 | Ref ID tidak unik | Gagal | Tidak |
| 50 | Transaksi tidak ditemukan | Gagal | Ya |
| 51 | Nomor tujuan diblokir | Gagal | Ya |
| 52 | Prefix tidak sesuai operator | Gagal | Ya |
| 53 | Produk seller tidak tersedia | Gagal | Ya |
| 54 | Nomor tujuan salah | Gagal | Ya |
| 55 | Produk sedang gangguan | Gagal | Ya |
| 57 | Jumlah digit kurang/lebih | Gagal | Ya |
| 58 | Sedang cut off | Gagal | Ya |
| 59 | Tujuan di luar wilayah/cluster | Gagal | Ya |
| 60 | Tagihan belum tersedia | Gagal | Ya |
| 61 | Belum pernah deposit | Gagal | Tidak |
| 62 | Seller sedang gangguan | Gagal | Tidak |
| 63 | Tidak support transaksi multi | Gagal | Tidak |
| 64 | Tarik tiket gagal | Gagal | Tidak |
| 66 | Cut off (perbaikan sistem seller) | Gagal | Tidak |
| 67 | Seller belum terverifikasi | Gagal | Tidak |
| 68 | Stok habis | Gagal | Tidak |
| 69 | Harga seller > ketentuan harga buyer | Gagal | Tidak |
| 70 | Timeout dari biller | Gagal | Ya |
| 71 | Produk tidak stabil | Gagal | Ya |
| 72 | Lakukan unreg paket dahulu | Gagal | Ya |
| 73 | Kwh melebihi batas | Gagal | Ya |
| 74 | Transaksi refund | Gagal | Ya |
| 80 | Akun diblokir oleh seller | Gagal | Tidak |
| 81 | Seller diblokir oleh Anda | Gagal | Tidak |
| 82 | Akun belum terverifikasi | Gagal | Tidak |
| 83 | Limitasi pengecekan pricelist | Gagal | Tidak |
| 84 | Nominal tidak valid | Gagal | Ya |
| 85 | Limitasi transaksi (coba 1 menit lagi) | Gagal | Ya |
| 86 | Limitasi pengecekan nomor PLN | Gagal | Ya |
| 87 | Transaksi e-money wajib kelipatan Rp 1.000 | Gagal | Tidak |
| 88 | Akun tidak dapat melakukan aksi ini | Gagal | Tidak |
| 99 | DF Router Issue | Pending | Ya |

(56 and 65 are deprecated codes, omitted.)
