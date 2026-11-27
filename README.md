# PayLedger

A double-entry payments ledger for online stores: every rupee is recorded as a
balanced journal entry, payment-gateway webhooks are processed exactly once, and
an AI agent reconciles gateway settlement reports against the books.

> Status: **Ledger core** ✅ · **Razorpay webhooks (exactly-once)** ✅ · Order state machine · Dashboard · AI reconciliation

## Why

When a customer pays ₹1,000 through Razorpay, the gateway keeps a fee, settles the
rest days later, may send the same webhook twice, and refunds can be partial. Naive
code double-counts or loses money. PayLedger makes those bugs structurally impossible.

## Core ideas

- **Double-entry:** every entry's debits equal its credits, so money is only *moved*, never created or lost.
- **Integer paise:** amounts are stored as `BIGINT` paise, never floats.
- **Idempotency keys:** the same business fact (e.g. `razorpay:payment:pay_123`) can never be posted twice.
- **Webhook inbox:** gateways deliver at-least-once. Every webhook is signature-verified (HMAC-SHA256,
  constant-time compare), stored with a unique `(provider, event_id)`, then processed in a single
  transaction with its journal entry. Duplicates are dropped; crashes roll back; a worker retries failures.

```
Razorpay ──► POST /webhooks/razorpay
               │ 1. verify HMAC signature        (reject forgeries → 400)
               │ 2. INSERT webhook_events         (duplicate event id → 200 "duplicate")
               │ 3. BEGIN
               │      post journal entry (idempotency key)
               │      mark event processed
               │    COMMIT                        (crash → rollback → worker retries)
               ▼
            200 OK
```

Example: a ₹1,000 sale with a ₹20 gateway fee:

| Account | Debit | Credit |
|---|---:|---:|
| `assets:razorpay_clearing` | 98,000 | |
| `expenses:gateway_fees` | 2,000 | |
| `revenue:sales` | | 100,000 |

## Tech stack

FastAPI · SQLAlchemy 2 · PostgreSQL 16 · Alembic · Pydantic · pytest + Hypothesis · Docker · uv

## Run it locally

Requirements: Docker Desktop, [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
make db        # start Postgres in Docker
make migrate   # create tables
make seed      # add default accounts
make dev       # API at http://localhost:8000/docs
make test      # run tests

# Try webhooks without a Razorpay account (API must be running):
make fake-payment                                                  # signed ₹1,000 payment
cd backend && uv run python scripts/fake_razorpay.py payment --amount 1000 --repeat 3  # duplicates
make retry     # reprocess failed webhook events
```

## Project layout

```
backend/
  app/
    models.py      # tables: accounts, journal_entries, postings
    ledger.py      # validate_entry, post_entry, balances (the core)
    api/routes.py  # HTTP endpoints
    seed.py        # default chart of accounts
    webhooks/
      razorpay.py  # signature check + event → journal entry mapping
      inbox.py     # store-then-process, dedup, retries
    worker.py      # retries failed webhook events
  scripts/
    fake_razorpay.py  # sends signed test webhooks locally
  migrations/      # Alembic schema migrations
  tests/           # unit, property-based and API tests
```
