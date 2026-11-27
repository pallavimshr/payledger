"""FastAPI application entry point."""
from fastapi import FastAPI

from app.api.routes import router
from app.api.webhooks import router as webhooks_router

app = FastAPI(
    title="PayLedger",
    description="Double-entry payments ledger with exactly-once webhooks.",
    version="0.1.0",
)
app.include_router(router)
app.include_router(webhooks_router)
